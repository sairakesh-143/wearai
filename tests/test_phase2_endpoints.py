import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from main import app, create_access_token

client = TestClient(app)
token = create_access_token({"sub": "1", "role": "admin"})
headers = {"Authorization": f"Bearer {token}"}

def test_root_html_accessibility():
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    # Verify semantic elements
    assert "<header" in html
    assert "<nav" in html
    assert "<main" in html
    assert "<footer" in html
    # Verify skip to content link
    assert "Skip to main" in html
    # Verify ARIA landmarks and focus visible styles
    assert ":focus-visible" in html
    assert "aria-live" in html

def test_orders_pagination_and_search():
    res = client.get("/api/orders?page=1&page_size=2", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert "totalPages" in data
    assert len(data["items"]) <= 2

    # Test search query
    res_search = client.get("/api/orders?search=TechCorp", headers=headers)
    assert res_search.status_code == 200
    orders = res_search.json()
    assert all("TechCorp" in o["customer"] or "TechCorp" in o["id"] for o in orders)

def test_inventory_pagination_and_filter():
    res = client.get("/api/inventory?page=1&page_size=5", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert len(data["items"]) <= 5

    # Test category filter
    res_cat = client.get("/api/inventory?category=Tools", headers=headers)
    assert res_cat.status_code == 200
    tools = res_cat.json()
    assert all(p["category"] == "Tools" for p in tools)

def test_exceptions_pagination():
    res = client.get("/api/exceptions?page=1&page_size=5", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data

def test_activity_logs_pagination():
    res = client.get("/api/activity-logs?page=1&page_size=5", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
