import os
import math
import random
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pymongo import MongoClient
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import uuid

# ==================== CONFIG ====================
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DB_NAME", "wearai_db")
SECRET_KEY = os.getenv("SECRET_KEY", "wearai-super-secret-jwt-key-sai-rakesh")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440

# ==================== DATABASE ====================
client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# Collections
users_col = db.users
products_col = db.products
orders_col = db.orders
exceptions_col = db.exceptions
notifications_col = db.notifications
activity_logs_col = db.activity_logs
feed_events_col = db.feed_events

# ==================== SECURITY ====================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = users_col.find_one({"id": user_id})
    if user is None:
        raise credentials_exception
    user.pop("_id", None)
    user.pop("password", None)
    return user

def require_role(role: str):
    def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user.get("role") != role and current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Operation not permitted")
        return current_user
    return role_checker

# ==================== PYDANTIC MODELS ====================
class UserBase(BaseModel):
    name: str
    email: str
    role: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: str
    avatar: str
    zone: str

class OrderItem(BaseModel):
    sku: str
    name: str
    qty: int
    price: float
    zone: str
    shelf: int
    rack: int
    bin: int

class Order(BaseModel):
    id: str
    customer: str
    customerTier: str
    items: List[OrderItem]
    total: float
    date: datetime
    deadline: datetime
    shipMethod: str
    warehouse: str
    status: str
    picker: Optional[str] = None
    packer: Optional[str] = None
    exceptionStatus: str = "None"

# ==================== SMART ENGINES ====================
def calc_priority_engine(order: dict) -> dict:
    score = 0
    reasons = []
    
    hrs_left = (order["deadline"] - datetime.utcnow()).total_seconds() / 3600
    
    if hrs_left < 0:
        score += 40
        reasons.append("Past deadline")
    elif hrs_left < 4:
        score += 35
        reasons.append(f"Deadline in {int(hrs_left)}h")
    elif hrs_left < 24:
        score += 20
        reasons.append(f"Deadline in {int(hrs_left)}h")
    elif hrs_left < 72:
        score += 10
        reasons.append(f"Deadline in {int(hrs_left/24)}d")

    if order.get("customerTier") == "VIP":
        score += 25
        reasons.append("VIP customer")
    elif order.get("customerTier") == "Premium":
        score += 15
        reasons.append("Premium customer")

    if order.get("shipMethod") in ["Express", "Same-Day"]:
        score += 15
        reasons.append(f"{order['shipMethod']} shipping")

    if order.get("total", 0) > 500:
        score += 10
        reasons.append("High order value")

    if order.get("exceptionStatus") != "None":
        score += 15
        reasons.append(f"Exception: {order['exceptionStatus']}")

    priority = "Low"
    if score >= 70: priority = "Critical"
    elif score >= 50: priority = "High"
    elif score >= 25: priority = "Medium"

    return {"priority": priority, "score": score, "reasons": reasons}

def check_allocation_conflict(sku: str) -> Optional[dict]:
    product = products_col.find_one({"sku": sku})
    if not product: return None
    
    competing_orders = list(orders_col.find({
        "status": {"$in": ["New", "Confirmed"]},
        "items.sku": sku
    }))
    
    if not competing_orders: return None
    
    total_demand = 0
    for o in competing_orders:
        for item in o["items"]:
            if item["sku"] == sku:
                total_demand += item["qty"]
                
    if total_demand <= product["stock"]: return None
    
    # Add priority to orders
    for o in competing_orders:
        o["_priority"] = calc_priority_engine(o)
    competing_orders.sort(key=lambda x: x["_priority"]["score"], reverse=True)
    
    return {
        "sku": sku,
        "product": product,
        "competing": competing_orders,
        "available": product["stock"],
        "totalDemand": total_demand,
        "shortfall": total_demand - product["stock"]
    }

def detect_bottlenecks_engine():
    bottlenecks = []
    pipeline = ["Picking", "Packing", "Quality Check", "Ready for Dispatch"]
    
    for stage in pipeline:
        count = orders_col.count_documents({"status": stage})
        if count > 3:
            avg_time = random.randint(15, 35)
            expected_time = random.randint(10, 20)
            deviation = int(((avg_time - expected_time) / expected_time) * 100)
            bottlenecks.append({
                "stage": stage,
                "count": count,
                "avgTime": f"{avg_time}min",
                "expected": f"{expected_time}min",
                "deviation": f"+{deviation}%",
                "impact": f"{stage} queue backing up",
                "recommendation": f"Assign additional staff to {stage} station."
            })
    return bottlenecks

# ==================== SEED DATA ====================
def seed_database():
    if users_col.count_documents({}) > 0:
        print("Database already seeded.")
        return

    print("Seeding database...")
    
    # Users
    users_data = [
        {"id":"1","name":"Sai Rakesh","role":"admin","email":"rakesh@wearai.io","password":get_password_hash("demo1234"),"avatar":"SR","zone":"All"},
        {"id":"2","name":"Vikram Patel","role":"manager","email":"vikram@wearai.io","password":get_password_hash("demo1234"),"avatar":"VP","zone":"All"},
        {"id":"3","name":"Arjun Mehta","role":"staff","email":"arjun@wearai.io","password":get_password_hash("demo1234"),"avatar":"AM","zone":"A"},
        {"id":"4","name":"Priya Nair","role":"staff","email":"priya@wearai.io","password":get_password_hash("demo1234"),"avatar":"PN","zone":"B"}
    ]
    users_col.insert_many(users_data)

    # Products
    products_data = [
        {"id": 1, "sku": "SKU-101", "name": "Wireless Headphones Pro", "category": "Electronics", "price": 89.99, "zone": "A", "shelf": 1, "rack": 5, "bin": 3, "stock": 7, "reserved": 7, "reorderLevel": 25, "reorderQty": 100, "dailyDemand": 8, "supplier": "TechSource Inc", "status": "Critical Stock"},
        {"id": 2, "sku": "SKU-102", "name": "Ergonomic Laptop Stand", "category": "Electronics", "price": 45.00, "zone": "A", "shelf": 2, "rack": 8, "bin": 4, "stock": 45, "reserved": 0, "reorderLevel": 15, "reorderQty": 50, "dailyDemand": 5, "supplier": "TechSource Inc", "status": "In Stock"},
        {"id": 3, "sku": "SKU-103", "name": "Precision Wireless Mouse", "category": "Electronics", "price": 29.99, "zone": "A", "shelf": 3, "rack": 2, "bin": 5, "stock": 82, "reserved": 0, "reorderLevel": 20, "reorderQty": 80, "dailyDemand": 6, "supplier": "GlobalGoods Co", "status": "In Stock"},
        {"id": 4, "sku": "SKU-104", "name": "RGB Mechanical Keyboard", "category": "Electronics", "price": 129.99, "zone": "A", "shelf": 3, "rack": 6, "bin": 2, "stock": 12, "reserved": 0, "reorderLevel": 15, "reorderQty": 40, "dailyDemand": 4, "supplier": "TechSource Inc", "status": "Low Stock"},
        {"id": 5, "sku": "SKU-105", "name": "4K Ultra HD Webcam", "category": "Electronics", "price": 79.99, "zone": "A", "shelf": 3, "rack": 9, "bin": 1, "stock": 28, "reserved": 0, "reorderLevel": 10, "reorderQty": 30, "dailyDemand": 3, "supplier": "PrimeSupply Ltd", "status": "In Stock"},
        {"id": 6, "sku": "SKU-106", "name": "Executive Notebook A5", "category": "Office Supplies", "price": 8.99, "zone": "B", "shelf": 1, "rack": 2, "bin": 1, "stock": 140, "reserved": 0, "reorderLevel": 30, "reorderQty": 150, "dailyDemand": 12, "supplier": "FastChain Trading", "status": "In Stock"},
        {"id": 7, "sku": "SKU-107", "name": "Smooth Gel Pen Set (12pc)", "category": "Office Supplies", "price": 11.99, "zone": "B", "shelf": 1, "rack": 5, "bin": 3, "stock": 210, "reserved": 0, "reorderLevel": 40, "reorderQty": 200, "dailyDemand": 18, "supplier": "FastChain Trading", "status": "In Stock"},
        {"id": 8, "sku": "SKU-108", "name": "Heavy-Duty Metal Stapler", "category": "Office Supplies", "price": 16.99, "zone": "B", "shelf": 2, "rack": 8, "bin": 4, "stock": 35, "reserved": 0, "reorderLevel": 15, "reorderQty": 50, "dailyDemand": 4, "supplier": "Metro Distributors", "status": "In Stock"},
        {"id": 9, "sku": "SKU-109", "name": "Smart LED Bulb E27 12W", "category": "Home & Living", "price": 6.99, "zone": "C", "shelf": 1, "rack": 2, "bin": 4, "stock": 175, "reserved": 0, "reorderLevel": 50, "reorderQty": 200, "dailyDemand": 15, "supplier": "GlobalGoods Co", "status": "In Stock"},
        {"id": 10, "sku": "SKU-110", "name": "Plush Linen Pillow Cover", "category": "Home & Living", "price": 19.99, "zone": "C", "shelf": 1, "rack": 5, "bin": 7, "stock": 64, "reserved": 0, "reorderLevel": 20, "reorderQty": 60, "dailyDemand": 5, "supplier": "Excel Logistics", "status": "In Stock"},
        {"id": 11, "sku": "SKU-111", "name": "Vacuum Insulated Flask 1L", "category": "Home & Living", "price": 18.99, "zone": "C", "shelf": 4, "rack": 4, "bin": 1, "stock": 4, "reserved": 0, "reorderLevel": 15, "reorderQty": 50, "dailyDemand": 3, "supplier": "PrimeSupply Ltd", "status": "Critical Stock"},
        {"id": 12, "sku": "SKU-112", "name": "Brushless Impact Drill 20V", "category": "Tools", "price": 89.99, "zone": "D", "shelf": 1, "rack": 2, "bin": 3, "stock": 18, "reserved": 0, "reorderLevel": 10, "reorderQty": 30, "dailyDemand": 2, "supplier": "TechSource Inc", "status": "In Stock"},
        {"id": 13, "sku": "SKU-113", "name": "Magnetic Precision Driver Set", "category": "Tools", "price": 24.99, "zone": "D", "shelf": 1, "rack": 5, "bin": 7, "stock": 52, "reserved": 0, "reorderLevel": 15, "reorderQty": 40, "dailyDemand": 3, "supplier": "Metro Distributors", "status": "In Stock"},
        {"id": 14, "sku": "SKU-114", "name": "Auto-Lock Measuring Tape 30ft", "category": "Tools", "price": 9.99, "zone": "D", "shelf": 2, "rack": 3, "bin": 5, "stock": 0, "reserved": 0, "reorderLevel": 20, "reorderQty": 80, "dailyDemand": 6, "supplier": "Metro Distributors", "status": "Out of Stock"},
        {"id": 15, "sku": "SKU-115", "name": "Modular Tool Box Organizer", "category": "Tools", "price": 39.99, "zone": "D", "shelf": 3, "rack": 1, "bin": 8, "stock": 26, "reserved": 0, "reorderLevel": 10, "reorderQty": 30, "dailyDemand": 2, "supplier": "Excel Logistics", "status": "In Stock"}
    ]
    products_col.insert_many(products_data)

    # Orders
    orders_data = [
        {
            "id": "ORD-1001", "customer": "TechCorp Industries", "customerTier": "VIP",
            "items": [{"sku": "SKU-101", "name": "Wireless Headphones Pro", "qty": 10, "price": 89.99, "zone": "A", "shelf": 1, "rack": 5, "bin": 3}],
            "total": 899.90, "date": datetime.utcnow()-timedelta(hours=3), "deadline": datetime.utcnow()+timedelta(hours=2),
            "shipMethod": "Express", "warehouse": "WH-01", "status": "New", "picker": None, "packer": None, "exceptionStatus": "None"
        },
        {
            "id": "ORD-1002", "customer": "RetailCo Stores", "customerTier": "Regular",
            "items": [{"sku": "SKU-101", "name": "Wireless Headphones Pro", "qty": 5, "price": 89.99, "zone": "A", "shelf": 1, "rack": 5, "bin": 3}],
            "total": 449.95, "date": datetime.utcnow()-timedelta(hours=5), "deadline": datetime.utcnow()+timedelta(days=5),
            "shipMethod": "Standard", "warehouse": "WH-01", "status": "New", "picker": None, "packer": None, "exceptionStatus": "None"
        },
        {
            "id": "ORD-1003", "customer": "PrimeMart Chain", "customerTier": "VIP",
            "items": [
                {"sku": "SKU-104", "name": "RGB Mechanical Keyboard", "qty": 2, "price": 129.99, "zone": "A", "shelf": 3, "rack": 6, "bin": 2},
                {"sku": "SKU-105", "name": "4K Ultra HD Webcam", "qty": 1, "price": 79.99, "zone": "A", "shelf": 3, "rack": 9, "bin": 1}
            ],
            "total": 339.97, "date": datetime.utcnow()-timedelta(hours=6), "deadline": datetime.utcnow()+timedelta(days=1),
            "shipMethod": "Express", "warehouse": "WH-01", "status": "Allocated", "picker": None, "packer": None, "exceptionStatus": "None"
        },
        {
            "id": "ORD-1004", "customer": "CityTech Solutions", "customerTier": "Premium",
            "items": [
                {"sku": "SKU-102", "name": "Ergonomic Laptop Stand", "qty": 4, "price": 45.00, "zone": "A", "shelf": 2, "rack": 8, "bin": 4},
                {"sku": "SKU-103", "name": "Precision Wireless Mouse", "qty": 2, "price": 29.99, "zone": "A", "shelf": 3, "rack": 2, "bin": 5}
            ],
            "total": 239.98, "date": datetime.utcnow()-timedelta(hours=8), "deadline": datetime.utcnow()+timedelta(hours=18),
            "shipMethod": "Same-Day", "warehouse": "WH-01", "status": "Picking", "picker": "Arjun Mehta", "packer": None, "exceptionStatus": "None"
        },
        {
            "id": "ORD-1005", "customer": "NextGen Retail", "customerTier": "Premium",
            "items": [
                {"sku": "SKU-106", "name": "Executive Notebook A5", "qty": 10, "price": 8.99, "zone": "B", "shelf": 1, "rack": 2, "bin": 1},
                {"sku": "SKU-107", "name": "Smooth Gel Pen Set (12pc)", "qty": 5, "price": 11.99, "zone": "B", "shelf": 1, "rack": 5, "bin": 3}
            ],
            "total": 149.85, "date": datetime.utcnow()-timedelta(hours=12), "deadline": datetime.utcnow()+timedelta(days=2),
            "shipMethod": "Standard", "warehouse": "WH-01", "status": "Ready for Dispatch", "picker": "Priya Nair", "packer": "Priya Nair", "exceptionStatus": "None"
        },
        {
            "id": "ORD-1006", "customer": "MetroElectronics", "customerTier": "VIP",
            "items": [{"sku": "SKU-112", "name": "Brushless Impact Drill 20V", "qty": 3, "price": 89.99, "zone": "D", "shelf": 1, "rack": 2, "bin": 3}],
            "total": 269.97, "date": datetime.utcnow()-timedelta(hours=14), "deadline": datetime.utcnow()+timedelta(hours=12),
            "shipMethod": "Express", "warehouse": "WH-01", "status": "Dispatched", "picker": "Arjun Mehta", "packer": "Vikram Patel", "exceptionStatus": "None"
        }
    ]
    orders_col.insert_many(orders_data)

    # Exceptions
    exceptions_col.insert_many([
        {"id": "EX-101", "type": "Insufficient Stock", "order": "ORD-1001", "sku": "SKU-101", "severity": "Critical", "status": "Open", "created": datetime.utcnow()-timedelta(minutes=30), "assigned": "Vikram Patel", "recommendation": "Allocate available 7 units to ORD-1001 (Critical priority)."}
    ])
    
    print("Seeding complete!")


# ==================== FASTAPI APP ====================
app = FastAPI(
    title="WearAI API",
    description="Intelligent AI Warehouse Operations & Optimization Platform - Developed by Sai Rakesh (@sairakesh-143)",
    version="2.4.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def serve_frontend():
    return FileResponse("index.html")

@app.on_event("startup")
def startup_event():
    seed_database()

# ==================== DASHBOARD ROUTES ====================
@app.get("/api/dashboard/stats")
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    total_orders = orders_col.count_documents({})
    pending = orders_col.count_documents({"status": {"$in": ["New", "Confirmed"]}})
    picking = orders_col.count_documents({"status": "Picking"})
    packing = orders_col.count_documents({"status": "Packing"})
    ready = orders_col.count_documents({"status": "Ready for Dispatch"})
    dispatched = orders_col.count_documents({"status": {"$in": ["Dispatched", "Delivered"]}})
    low_stock = products_col.count_documents({"status": {"$in": ["Low Stock", "Critical Stock"]}})
    out_of_stock = products_col.count_documents({"status": "Out of Stock"})
    
    pipeline = [{"$group": {"_id": None, "total": {"$sum": {"$multiply": ["$stock", "$price"]}}}}]
    inv_value = list(products_col.aggregate(pipeline))[0]["total"] if products_col.count_documents({}) > 0 else 0
    
    return {
        "totalOrders": total_orders, "pendingOrders": pending,
        "pickingOrders": picking, "packingOrders": packing,
        "readyOrders": ready, "dispatchedOrders": dispatched,
        "lowStock": low_stock, "outOfStock": out_of_stock,
        "inventoryValue": round(inv_value, 2),
        "fulfillmentRate": round((dispatched / total_orders * 100) if total_orders > 0 else 0, 1)
    }

# ==================== ORDERS ROUTES ====================
@app.get("/api/orders")
async def get_orders(current_user: dict = Depends(get_current_user)):
    orders = list(orders_col.find({}, {"_id": 0}))
    for o in orders:
        o["date"] = o["date"].isoformat()
        o["deadline"] = o["deadline"].isoformat()
        o["priority"] = calc_priority_engine(o)
    return orders

@app.get("/api/orders/{order_id}")
async def get_order(order_id: str, current_user: dict = Depends(get_current_user)):
    order = orders_col.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order["date"] = order["date"].isoformat()
    order["deadline"] = order["deadline"].isoformat()
    order["priority"] = calc_priority_engine(order)
    return order

# ==================== INVENTORY ROUTES ====================
@app.get("/api/inventory")
async def get_inventory(current_user: dict = Depends(get_current_user)):
    products = list(products_col.find({}, {"_id": 0}))
    return products

@app.get("/api/inventory/low-stock")
async def get_low_stock(current_user: dict = Depends(get_current_user)):
    products = list(products_col.find({"stock": {"$lte": 25}}, {"_id": 0}))
    result = []
    for p in products:
        days_remaining = (p["stock"] / p["dailyDemand"]) if p["dailyDemand"] > 0 and p["stock"] > 0 else 0
        risk = "Critical" if p["stock"] == 0 else "High" if days_remaining < 2 else "Medium" if days_remaining < 5 else "Low"
        p["daysRemaining"] = round(days_remaining, 1)
        p["risk"] = risk
        result.append(p)
    return sorted(result, key=lambda x: x["daysRemaining"])

# ==================== ALLOCATION ENGINE ROUTES ====================
@app.get("/api/allocation/conflict/{sku}")
async def get_allocation_conflict(sku: str, current_user: dict = Depends(get_current_user)):
    conflict = check_allocation_conflict(sku)
    if not conflict:
        return {"message": "No conflict detected", "conflict": None}
    
    # Format for response
    remaining_stock = conflict["available"]
    decisions = []
    for o in conflict["competing"]:
        # Safe datetime handling
        if isinstance(o["deadline"], str):
            o["deadline"] = datetime.fromisoformat(o["deadline"])
            
        item_need = next((i["qty"] for i in o["items"] if i["sku"] == sku), 0)
        allocated = min(item_need, remaining_stock)
        remaining_stock -= allocated
        
        decisions.append({
            "orderId": o["id"], "priority": o["_priority"]["priority"], "score": o["_priority"]["score"],
            "requested": item_need, "allocated": allocated, "remaining": item_need - allocated,
            "fullyAllocated": allocated == item_need, "customer": o["customer"], 
            "customerTier": o["customerTier"], "reasons": o["_priority"]["reasons"]
        })
        
    recommendation = f"Allocate {decisions[0]['allocated']} units to {decisions[0]['orderId']} ({decisions[0]['priority']} priority)"
    
    return {
        "sku": conflict["sku"], "product": conflict["product"], "available": conflict["available"],
        "totalDemand": conflict["totalDemand"], "shortfall": conflict["shortfall"],
        "decisions": decisions, "recommendation": recommendation, "conflict": True
    }

@app.post("/api/allocation/apply")
async def apply_allocation(sku: str = Body(...), current_user: dict = Depends(require_role("manager"))):
    conflict = check_allocation_conflict(sku)
    if not conflict:
        raise HTTPException(status_code=400, detail="No conflict to resolve")
    
    for o in conflict["competing"]:
        item_need = next((i["qty"] for i in o["items"] if i["sku"] == sku), 0)
        allocated = min(item_need, conflict["available"])
        conflict["available"] -= allocated
        
        new_status = "Allocated" if allocated == item_need else "Partially Allocated"
        orders_col.update_one({"id": o["id"]}, {"$set": {"status": new_status}})
        
        # Log activity
        activity_logs_col.insert_one({
            "user": current_user["name"], "action": f"allocated {allocated}/{item_need} units of {sku}",
            "target": o["id"], "time": datetime.utcnow(), "prev": "New", "next": new_status
        })
        
    # Update product stock
    product = products_col.find_one({"sku": sku})
    products_col.update_one({"sku": sku}, {"$set": {"stock": 0, "reserved": product["stock"]}})
    
    return {"message": "Allocation applied successfully"}

# ==================== EXCEPTIONS ROUTES ====================
@app.get("/api/exceptions")
async def get_exceptions(current_user: dict = Depends(get_current_user)):
    exceptions = list(exceptions_col.find({}, {"_id": 0}))
    for e in exceptions:
        e["created"] = e["created"].isoformat()
    return exceptions

# ==================== ANALYTICS ROUTES ====================
@app.get("/api/analytics/bottlenecks")
async def get_bottlenecks(current_user: dict = Depends(get_current_user)):
    return detect_bottlenecks_engine()

# ==================== SMART DECISION CENTER ====================
@app.get("/api/recommendations")
async def get_recommendations(current_user: dict = Depends(get_current_user)):
    recs = []
    
    # Low stock recs
    low_stock = list(products_col.find({"stock": {"$lte": 25}}))
    for p in low_stock[:3]:
        days_left = (p["stock"] / p["dailyDemand"]) if p["dailyDemand"] > 0 and p["stock"] > 0 else 0
        recs.append({
            "id": f"rec-low-{p['sku']}", "type": "Inventory", "color": "amber",
            "problem": f"{p['sku']} may run out within {round(days_left, 1)} days",
            "decision": f"Reorder {p['reorderQty']} units from {p['supplier']}",
            "impact": "Prevents stockout and maintains fulfillment rate"
        })
        
    # Allocation conflict rec
    conflict = check_allocation_conflict("SKU-103")
    if conflict:
        recs.append({
            "id": "rec-alloc-1", "type": "Allocation", "color": "red",
            "problem": f"Stock conflict on SKU-103 — {conflict['totalDemand']} units demanded, only {conflict['available']} available",
            "decision": f"Allocate {conflict['available']} units to {conflict['competing'][0]['id']} (Critical priority).",
            "impact": "Critical VIP order partially fulfilled. Exception created."
        })
        
    # Bottleneck recs
    bottlenecks = detect_bottlenecks_engine()
    for b in bottlenecks[:2]:
        recs.append({
            "id": f"rec-bn-{b['stage']}", "type": "Staffing", "color": "purple",
            "problem": f"{b['stage']} bottleneck detected — {b['deviation']} slower than average",
            "decision": b['recommendation'],
            "impact": "Reduces average processing time by ~30%. Prevents cascade delays."
        })
        
    return recs

# ==================== ACTIVITY LOG ====================
@app.get("/api/activity-logs")
async def get_activity_logs(current_user: dict = Depends(get_current_user)):
    logs = list(activity_logs_col.find({}, {"_id": 0}).sort("time", -1).limit(20))
    for l in logs:
        l["time"] = l["time"].isoformat()
    return logs

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)