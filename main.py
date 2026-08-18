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
    categories = ['Electronics','Office Supplies','Home & Living','Tools']
    zones = ['A','B','C','D']
    suppliers = ['TechSource Inc','GlobalGoods Co','PrimeSupply Ltd']
    
    products_data = []
    for i in range(50):
        sku = f"SKU-{101+i}"
        stock = 7 if i == 2 else random.choice([0, 5, 12, 15, 50, 100, 150])
        reorder_level = 25
        status = "In Stock"
        if stock == 0: status = "Out of Stock"
        elif stock <= 10: status = "Critical Stock"
        elif stock <= reorder_level: status = "Low Stock"
        
        products_data.append({
            "id": i+1, "sku": sku, "name": f"Product {i+1}",
            "category": categories[i % 4], "price": round(random.uniform(10, 150), 2),
            "zone": zones[i % 4], "shelf": random.randint(1,9), "rack": random.randint(1,9), "bin": random.randint(1,8),
            "stock": stock, "reserved": 0, "reorderLevel": reorder_level, "reorderQty": 100,
            "dailyDemand": random.randint(2, 15), "supplier": suppliers[i % 3], "status": status
        })
    products_col.insert_many(products_data)

    # Orders
    customers = [
        {"name":"TechCorp Industries","tier":"VIP"},{"name":"RetailCo Stores","tier":"Regular"},
        {"name":"PrimeMart Chain","tier":"VIP"},{"name":"CityTech Solutions","tier":"Premium"}
    ]
    ship_methods = ['Express','Standard','Same-Day','Economy']
    order_statuses = ['New','Confirmed','Picking','Packing','Quality Check','Ready for Dispatch','Dispatched']
    
    orders_data = []
    # Specific demo scenario order 1
    orders_data.append({
        "id":"ORD-1001","customer":"TechCorp Industries","customerTier":"VIP",
        "items":[{"sku":"SKU-103","name":"Wireless Headphones Pro","qty":10,"price":89.99,"zone":"A","shelf":1,"rack":5,"bin":3}],
        "total":899.90,"date":datetime.utcnow()-timedelta(hours=3),"deadline":datetime.utcnow()+timedelta(hours=2),
        "shipMethod":"Express","warehouse":"WH-01","status":"New","picker":None,"packer":None,"exceptionStatus":"None"
    })
    # Specific demo scenario order 2
    orders_data.append({
        "id":"ORD-1002","customer":"RetailCo Stores","customerTier":"Regular",
        "items":[{"sku":"SKU-103","name":"Wireless Headphones Pro","qty":5,"price":89.99,"zone":"A","shelf":1,"rack":5,"bin":3}],
        "total":449.95,"date":datetime.utcnow()-timedelta(hours=5),"deadline":datetime.utcnow()+timedelta(days=5),
        "shipMethod":"Standard","warehouse":"WH-01","status":"New","picker":None,"packer":None,"exceptionStatus":"None"
    })
    
    for i in range(3, 31):
        items = []
        for _ in range(random.randint(1,4)):
            p = random.choice(products_data)
            qty = random.randint(1,8)
            items.append({"sku":p["sku"],"name":p["name"],"qty":qty,"price":p["price"],"zone":p["zone"],"shelf":p["shelf"],"rack":p["rack"],"bin":p["bin"]})
        
        total = sum(it["qty"]*it["price"] for it in items)
        cust = random.choice(customers)
        status = random.choice(order_statuses)
        
        orders_data.append({
            "id":f"ORD-{1000+i}","customer":cust["name"],"customerTier":cust["tier"],
            "items":items,"total":total,"date":datetime.utcnow()-timedelta(hours=random.randint(1,48)),
            "deadline":datetime.utcnow()+timedelta(days=random.randint(-1,7)),
            "shipMethod":random.choice(ship_methods),"warehouse":"WH-01",
            "status":status,"picker":None,"packer":None,"exceptionStatus": "None"
        })
    orders_col.insert_many(orders_data)

    # Exceptions
    exceptions_col.insert_many([
        {"id":"EX-101","type":"Insufficient Stock","order":"ORD-1001","sku":"SKU-103","severity":"Critical","status":"Open","created":datetime.utcnow()-timedelta(minutes=30),"assigned":"Vikram Patel","recommendation":"Allocate available 7 units to ORD-1001 (Critical priority)."}
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