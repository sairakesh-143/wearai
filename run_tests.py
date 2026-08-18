import unittest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from main import app, seed_database, create_access_token, calc_priority_engine, products_col, orders_col

class TestValidationAndEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_database()
        cls.client = TestClient(app)
        cls.token = create_access_token({"sub": "1", "role": "admin"})
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    def test_invalid_sku_validation(self):
        payload = {
            "customer": "Test Customer",
            "items": [{"sku": "INVALID_SKU_FORMAT", "qty": 2}],
            "warehouse": "WH-01 Seattle Central"
        }
        res = self.client.post("/api/orders", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 422)
        self.assertIn("Invalid SKU format", res.json()["detail"])

    def test_nonexistent_sku_validation(self):
        payload = {
            "customer": "Test Customer",
            "items": [{"sku": "SKU-999", "qty": 2}],
            "warehouse": "WH-01 Seattle Central"
        }
        res = self.client.post("/api/orders", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 404)
        self.assertIn("not registered in the inventory database", res.json()["detail"])

    def test_invalid_quantity_validation(self):
        payload = {
            "customer": "Test Customer",
            "items": [{"sku": "SKU-101", "qty": 0}],
            "warehouse": "WH-01 Seattle Central"
        }
        res = self.client.post("/api/orders", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 422)
        self.assertIn("positive integer greater than 0", res.json()["detail"])

    def test_insufficient_inventory_validation(self):
        payload = {
            "customer": "Test Customer",
            "items": [{"sku": "SKU-101", "qty": 999}],
            "warehouse": "WH-01 Seattle Central"
        }
        res = self.client.post("/api/orders", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Insufficient inventory", res.json()["detail"])
        self.assertIn("only", res.json()["detail"])

    def test_duplicate_order_detection(self):
        payload = {
            "id": "ORD-1001",
            "customer": "Test Customer",
            "items": [{"sku": "SKU-102", "qty": 1}],
            "warehouse": "WH-01 Seattle Central"
        }
        res = self.client.post("/api/orders", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 409)
        self.assertIn("Duplicate order ID", res.json()["detail"])

    def test_missing_required_fields_validation(self):
        payload = {
            "customer": "",
            "items": [{"sku": "SKU-102", "qty": 1}],
            "warehouse": "WH-01 Seattle Central"
        }
        res = self.client.post("/api/orders", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 422)
        self.assertIn("Missing required field", res.json()["detail"])

    def test_invalid_warehouse_location(self):
        payload = {
            "customer": "Test Customer",
            "items": [{"sku": "SKU-102", "qty": 1}],
            "warehouse": "WH-99 Mars Base"
        }
        res = self.client.post("/api/orders", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 422)
        self.assertIn("Invalid warehouse location", res.json()["detail"])

    def test_priority_engine_math(self):
        order = {
            "deadline": datetime.utcnow() - timedelta(hours=2),
            "customerTier": "VIP",
            "shipMethod": "Express",
            "total": 600,
            "exceptionStatus": "None"
        }
        pri = calc_priority_engine(order)
        self.assertIn(pri["priority"], ["High", "Critical"])
        self.assertGreaterEqual(pri["score"], 70)

    def test_health_check_endpoint(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("apiHealth", data)

    def test_system_tests_runner_endpoint(self):
        res = self.client.post("/api/tests/run")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["passed"], data["total"])

if __name__ == "__main__":
    unittest.main()
