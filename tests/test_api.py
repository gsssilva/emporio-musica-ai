import csv
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from test_ingestion import sample_rows

from emporio_ai.api import create_app
from emporio_ai.source_data import SCHEMAS
from emporio_ai.storage import ingest


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        rows = sample_rows()
        for table, schema in SCHEMAS.items():
            with (self.root / f"desafio_tecnico_ai_eng - {table}.csv").open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(schema.split())
                writer.writerows(rows[table])
        database = self.root / "store.sqlite3"
        ingest(self.root, database)
        self.client = TestClient(create_app(database))
        self.addCleanup(self.client.close)

    def test_home_and_health(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertIn("text/html", self.client.get("/").headers["content-type"])
        self.assertEqual(self.client.get("/health").json()["status"], "ready")

    def test_filtered_catalog_and_categories(self):
        self.assertEqual(self.client.get("/api/categories").json()["categories"][0]["category_id"], 5)
        response = self.client.get("/api/products", params={"query": "violoes", "max_price_brl": "90.00"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["products"][0]["current_price_cents"], 8959)

    def test_invalid_filters_are_rejected(self):
        for params in [{"max_price_brl": "NaN"}, {"max_price_brl": "1.005"}, {"limit": "100"}, {"category_id": "-1"}]:
            self.assertEqual(self.client.get("/api/products", params=params).status_code, 422)

    def test_product_not_found_and_invalid_identifier(self):
        self.assertEqual(self.client.get("/api/products/999").status_code, 404)
        self.assertEqual(self.client.get("/api/products/-1").status_code, 422)

    def test_quote_and_invalid_payment_combination(self):
        result = self.client.get("/api/products/81/quote").json()["quote"]
        self.assertEqual(result["total_cents"], 8959)
        self.assertFalse(result["pix_discount_applied"])
        self.assertEqual(self.client.get("/api/products/81/quote?method=pix&installments=2").status_code, 422)

    def test_private_order_routes_are_not_publicly_exposed(self):
        self.assertEqual(self.client.get("/api/orders/1").status_code, 404)

    def test_missing_database_returns_safe_service_error(self):
        with TestClient(create_app(self.root / "absent.sqlite3")) as client:
            response = client.get("/health")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(str(self.root), response.text)


if __name__ == "__main__":
    unittest.main()
