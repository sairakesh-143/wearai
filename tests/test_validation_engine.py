import pytest
from fastapi.testclient import TestClient
from main import app, products_col, orders_col, calc_priority_engine, check_allocation_conflict

client = TestClient(app)

# ==================== VALIDATION TESTS ====================
def test_invalid_sku_validation():
    """Test that invalid SKU formats are rejected with 422 Unprocessable Entity."""
    payload = {
        "customer": "Test Customer",
        "items": [{"sku": "INVALID_SKU_FORMAT", "qty": 2}],
        "warehouse": "WH-01 Seattle Central"
    }
    response = client.post("/api/orders", json=payload)
    assert response.status_code == 422
    assert "Invalid SKU format" in response.json()["detail"]

def test_nonexistent_sku_validation():
    """Test that a well-formatted SKU that doesn't exist in inventory returns 404 Not Found."""
    payload = {
        "customer": "Test Customer",
        "items": [{"sku": "SKU-999", "qty": 2}],
        "warehouse": "WH-01 Seattle Central"
    }
    response = client.post("/api/orders", json=payload)
    assert response.status_code == 404
    assert "not registered in the inventory database" in response.json()["detail"]

def test_invalid_quantity_validation():
    """Test that non-positive quantities (<= 0) are rejected."""
    payload = {
        "customer": "Test Customer",
        "items": [{"sku": "SKU-101", "qty": 0}],
        "warehouse": "WH-01 Seattle Central"
    }
    response = client.post("/api/orders", json=payload)
    assert response.status_code == 422
    assert "positive integer greater than 0" in response.json()["detail"]

def test_insufficient_inventory_validation():
    """Test that ordering more than available stock triggers clear user-friendly error message."""
    # SKU-101 has 7 units in stock
    payload = {
        "customer": "Test Customer",
        "items": [{"sku": "SKU-101", "qty": 999}],
        "warehouse": "WH-01 Seattle Central"
    }
    response = client.post("/api/orders", json=payload)
    assert response.status_code == 400
    assert "Insufficient inventory" in response.json()["detail"]
    assert "only" in response.json()["detail"]
    assert "units are available" in response.json()["detail"]

def test_duplicate_order_detection():
    """Test that submitting an existing order ID returns 409 Conflict."""
    payload = {
        "id": "ORD-1001", # Existing order
        "customer": "Test Customer",
        "items": [{"sku": "SKU-102", "qty": 1}],
        "warehouse": "WH-01 Seattle Central"
    }
    response = client.post("/api/orders", json=payload)
    assert response.status_code == 409
    assert "Duplicate order ID" in response.json()["detail"]

def test_missing_required_fields_validation():
    """Test that missing required customer name returns 422."""
    payload = {
        "customer": "",
        "items": [{"sku": "SKU-102", "qty": 1}],
        "warehouse": "WH-01 Seattle Central"
    }
    response = client.post("/api/orders", json=payload)
    assert response.status_code == 422
    assert "Missing required field" in response.json()["detail"]

def test_invalid_warehouse_location():
    """Test that an unknown warehouse location returns 422."""
    payload = {
        "customer": "Test Customer",
        "items": [{"sku": "SKU-102", "qty": 1}],
        "warehouse": "WH-99 Mars Base"
    }
    response = client.post("/api/orders", json=payload)
    assert response.status_code == 422
    assert "Invalid warehouse location" in response.json()["detail"]

# ==================== ENGINE & LOGIC TESTS ====================
def test_priority_engine_math():
    """Test priority engine score calculation for VIP customer past deadline."""
    order = {
        "deadline": main_deadline_past(),
        "customerTier": "VIP",
        "shipMethod": "Express",
        "total": 600,
        "exceptionStatus": "None"
    }
    pri = calc_priority_engine(order)
    assert pri["priority"] in ["High", "Critical"]
    assert pri["score"] >= 70

def test_allocation_contention_solver():
    """Test stock allocation engine correctly detects SKU-101 contention."""
    conflict = check_allocation_conflict("SKU-101")
    assert conflict is not None
    assert conflict["sku"] == "SKU-101"
    assert conflict["shortfall"] > 0

# ==================== HEALTH & TEST RUNNER ENDPOINTS ====================
def test_health_check_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["HEALTHY", "UNHEALTHY"]
    assert "apiHealth" in data
    assert "dbHealth" in data

def test_system_tests_runner_endpoint():
    response = client.post("/api/tests/run")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "passed" in data
    assert data["passed"] == data["total"]
    assert "successRate" in data

def main_deadline_past():
    from datetime import datetime, timedelta
    return datetime.utcnow() - timedelta(hours=2)
