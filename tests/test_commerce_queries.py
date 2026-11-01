from __future__ import annotations

import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from test_ingestion import sample_rows

from emporio_ai.commerce import PaymentRuleError, discounted_price, quote_payment
from emporio_ai.queries import (
    AuthenticationRequired, OrderAccessError, ProductUnavailable, StoreQueries,
)
from emporio_ai.source_data import SCHEMAS
from emporio_ai.storage import ingest


class CommerceTests(unittest.TestCase):
    def test_rounding_uses_cents_and_half_up(self):
        self.assertEqual(discounted_price(101, 5000), 51)
        result = quote_payment(10001, method="credit", installments=3)
        self.assertEqual(result["installment_amounts_cents"], [3334, 3334, 3333])
        self.assertEqual(sum(result["installment_amounts_cents"]), result["total_cents"])

    def test_pix_does_not_stack_with_promotion(self):
        result = quote_payment(10000, promotion_bps=1000, method="pix")
        self.assertEqual(result["total_cents"], 9000)
        self.assertFalse(result["pix_discount_applied"])
        self.assertEqual(quote_payment(10000, method="pix")["total_cents"], 9500)

    def test_installment_minimum_boundaries(self):
        for total, installments in [(48000, 6), (120000, 12)]:
            with self.subTest(total=total):
                self.assertEqual(quote_payment(total, method="credit", installments=installments)["status"], "quoted")
                with self.assertRaises(PaymentRuleError):
                    quote_payment(total - 1, method="credit", installments=installments)

    def test_ambiguous_small_installments_require_confirmation(self):
        self.assertEqual(quote_payment(9999, method="credit", installments=2)["status"], "needs_confirmation")
        self.assertEqual(quote_payment(10000, method="credit", installments=2)["status"], "quoted")

    def test_rejects_invalid_methods_installments_and_financial_types(self):
        for method, installments in [("pix", 2), ("credit", 13), ("credit", True), ("unknown", 1)]:
            with self.assertRaises(PaymentRuleError):
                quote_payment(10000, method=method, installments=installments)
        for price, discount in [(True, 0), (10000, -1), (-1, 0), (10000, 10001)]:
            with self.assertRaises(ValueError):
                discounted_price(price, discount)


class QueryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        rows = sample_rows()
        for product_id, status, stock in [(82, "active", 0), (83, "discontinued", 13),
                                          (84, "coming_soon", 2), (85, "active", 3)]:
            product = rows["products"][0].copy()
            product[0], product[6], product[5] = str(product_id), status, str(stock)
            product[2] = f"Violão Exemplo {product_id}"
            rows["products"].append(product)
        rows["orders"][0][-1] = "Observação interna que não deve chegar ao modelo"
        for table, schema in SCHEMAS.items():
            with (self.root / f"desafio_tecnico_ai_eng - {table}.csv").open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(schema.split())
                writer.writerows(rows[table])
        self.database = self.root / "store.sqlite3"
        ingest(self.root, self.database)
        self.store = StoreQueries(self.database)

    def test_search_filters_status_stock_accents_and_current_price(self):
        result = self.store.search_products(query="violoes", max_price_cents=9000)
        self.assertEqual([product["product_id"] for product in result["products"]], [81])
        self.assertEqual(result["products"][0]["current_price_cents"], 8959)
        self.assertEqual(result["products"][0]["table_price_cents"], 10010)
        self.assertFalse(result["source"]["live_external_integration"])
        self.assertTrue(result["source"]["imported_at"])

    def test_exact_category_does_not_match_other_instrument_descriptions(self):
        connection = sqlite3.connect(self.database)
        try:
            connection.execute("INSERT INTO categories VALUES (9,'Ukuleles','Example')")
            connection.execute("""INSERT INTO products VALUES
                (86,5000,'Ukulele',9,'Similar a um violao',3,'active','{}','2025-01-01')""")
            connection.commit()
        finally:
            connection.close()
        products = self.store.search_products(query="violoes")["products"]
        self.assertTrue(products)
        self.assertTrue(all(product["category_id"] == 5 for product in products))

    def test_search_has_explicit_bounded_results(self):
        result = self.store.search_products(limit=1)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["matched_count"], 2)
        self.assertEqual(len(result["products"]), 1)
        with self.assertRaises(ValueError):
            self.store.search_products(limit=100)

    def test_queries_do_not_interpret_sql_from_user(self):
        self.assertEqual(self.store.search_products(query="'; DROP TABLE products; --")["products"], [])
        self.assertIsNotNone(self.store.get_product(81)["product"])
        with self.assertRaises(ValueError):
            self.store.get_product("81 OR 1=1")

    def test_product_details_explain_unavailability_and_missing_product(self):
        for product_id in [82, 83, 84]:
            self.assertFalse(self.store.get_product(product_id)["product"]["available"])
            with self.assertRaises(ProductUnavailable):
                self.store.quote_product(product_id, method="pix")
        self.assertIsNone(self.store.get_product(999)["product"])

    def test_payment_quote_uses_live_local_promotion(self):
        result = self.store.quote_product(81, method="pix")
        self.assertEqual(result["quote"]["total_cents"], 8959)
        self.assertFalse(result["quote"]["pix_discount_applied"])

    def test_inactive_promotion_is_not_applied_and_pix_uses_table_price(self):
        from contextlib import closing
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("UPDATE promotions SET is_active=0")
            connection.commit()
        product = self.store.get_product(81)["product"]
        self.assertEqual(product["promotion_bps"], 0)
        self.assertEqual(product["current_price_cents"], 10010)
        quote = self.store.quote_product(81, method="pix")["quote"]
        self.assertTrue(quote["pix_discount_applied"])
        self.assertEqual(quote["total_cents"], 9510)

    def test_order_context_is_required_and_other_clients_are_denied(self):
        with self.assertRaises(AuthenticationRequired):
            self.store.get_order(1, authorized_customer_id=None)
        for order_id, customer in [(1, 2), (999, 1)]:
            with self.assertRaisesRegex(OrderAccessError, "Pedido não encontrado para o cliente autorizado"):
                self.store.get_order(order_id, authorized_customer_id=customer)

    def test_order_preserves_total_and_does_not_expose_private_fields(self):
        order = self.store.get_order(1, authorized_customer_id=1)["order"]
        self.assertEqual(order["total_cents"], 8990)
        self.assertIsNone(order["tracking_code"])
        self.assertIsNone(order["actual_received_at"])
        self.assertIsNone(order["purchase_channel"])
        for field in ["customer_id", "notes", "email", "phone"]:
            self.assertNotIn(field, order)

    def test_query_connections_are_read_only(self):
        connection = self.store._connect()
        try:
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("DELETE FROM products")
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
