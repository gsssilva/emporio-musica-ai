from __future__ import annotations

import contextlib
import csv
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from emporio_ai.cli import main
from emporio_ai.source_data import DataValidationError, SCHEMAS, load_snapshot
from emporio_ai.storage import ingest


def sample_rows() -> dict:
    """Synthetic records; no customer information copied from the challenge."""
    return {
        "categories": [["5", "Violões", "Instrumentos de demonstração"]],
        "customers": [["1", "Cliente Exemplo", "000000000", "cliente@example.invalid", "Campo Grande"]],
        "products": [["81", "100.10", "Violão Exemplo", "5", "Modelo de teste", "12", "active",
                      '{"strings":"nylon"}', "2025-01-01"]],
        "orders": [["1", "1", "2026-03-01", "confirmed", "89.90", "pix", "", "", ""]],
        "order_items": [["1", "1", "81"]],
        "promotions": [["1", "81", "10.5", "Exemplo", "1"]],
    }


class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.data = self.root / "data"
        self.data.mkdir()
        self.database = self.root / "runtime/store.sqlite3"
        self.rows = sample_rows()
        self.write_sources()

    def write_sources(self):
        for table, schema in SCHEMAS.items():
            with (self.data / f"desafio_tecnico_ai_eng - {table}.csv").open(
                "w", encoding="utf-8", newline=""
            ) as stream:
                writer = csv.writer(stream)
                writer.writerow(schema.split())
                writer.writerows(self.rows[table])

    def query(self, statement):
        connection = sqlite3.connect(self.database)
        try:
            return connection.execute(statement).fetchall()
        finally:
            connection.close()

    def test_import_preserves_money_history_nulls_and_unicode(self):
        result = ingest(self.data, self.database)
        self.assertEqual(result["row_counts"], {name: 1 for name in SCHEMAS})
        self.assertEqual(self.query("SELECT price_cents,name FROM products"), [(10010, "Violão Exemplo")])
        self.assertEqual(self.query("SELECT total_cents,tracking_code,estimated_delivery,notes FROM orders"),
                         [(8990, None, None, None)])
        self.assertEqual(self.query("SELECT discount_bps FROM promotions"), [(1050,)])
        manifest = json.loads(self.query("SELECT source_manifest FROM import_metadata")[0][0])
        self.assertEqual(manifest, result["source_manifest"])
        self.assertEqual(self.query("PRAGMA foreign_key_check"), [])

    def test_repeated_import_replaces_instead_of_appending(self):
        ingest(self.data, self.database)
        self.rows["products"][0][1] = "199.99"
        self.write_sources()
        ingest(self.data, self.database)
        ingest(self.data, self.database)
        self.assertEqual(self.query("SELECT price_cents FROM products"), [(19999,)])
        self.assertEqual(self.query("SELECT COUNT(*) FROM order_items"), [(1,)])
        self.assertEqual(self.query("SELECT total_cents FROM orders"), [(8990,)])

    def test_validation_failure_preserves_database(self):
        ingest(self.data, self.database)
        before = self.database.read_bytes()
        self.rows["products"][0][5] = "-1"
        self.write_sources()
        with self.assertRaises(DataValidationError):
            ingest(self.data, self.database)
        self.assertEqual(before, self.database.read_bytes())

    def test_database_write_failure_rolls_back_rows_and_metadata(self):
        ingest(self.data, self.database)
        original_metadata = self.query("SELECT * FROM import_metadata")
        connection = sqlite3.connect(self.database)
        try:
            connection.execute("""CREATE TRIGGER fail_import BEFORE INSERT ON products
                BEGIN SELECT RAISE(ABORT, 'simulated failure'); END""")
            connection.commit()
        finally:
            connection.close()
        self.rows["products"][0][1] = "199.99"
        self.write_sources()
        with self.assertRaises(sqlite3.IntegrityError):
            ingest(self.data, self.database)
        self.assertEqual(self.query("SELECT price_cents FROM products"), [(10010,)])
        self.assertEqual(self.query("SELECT * FROM import_metadata"), original_metadata)
        self.assertEqual(self.query("SELECT COUNT(*) FROM customers"), [(1,)])

    def test_invalid_input_never_creates_database(self):
        self.rows["products"][0][1] = "NaN"
        self.write_sources()
        with self.assertRaises(DataValidationError):
            ingest(self.data, self.database)
        self.assertFalse(self.database.exists())

    def test_unknown_database_is_not_overwritten(self):
        self.database.parent.mkdir()
        connection = sqlite3.connect(self.database)
        connection.execute("CREATE TABLE unrelated(secret TEXT)")
        connection.execute("INSERT INTO unrelated VALUES ('preserve')")
        connection.commit()
        connection.close()
        with self.assertRaises(DataValidationError):
            ingest(self.data, self.database)
        self.assertEqual(self.query("SELECT secret FROM unrelated"), [("preserve",)])

    def test_future_schema_requires_explicit_migration(self):
        ingest(self.data, self.database)
        connection = sqlite3.connect(self.database)
        connection.execute("UPDATE import_metadata SET schema_version=999")
        connection.commit()
        connection.close()
        with self.assertRaises(DataValidationError):
            ingest(self.data, self.database)
        self.assertEqual(self.query("SELECT schema_version FROM import_metadata"), [(999,)])

    def test_rejects_invalid_scalar_values(self):
        cases = [
            ("products", 1, "1.005"), ("products", 1, "Infinity"),
            ("products", 1, "100.1000000000000000000000000000000000000001"),
            ("products", 1, "-0.01"), ("products", 1, "999999999999999999999"),
            ("products", 5, "-1"), ("products", 6, "available"),
            ("products", 7, "[]"), ("products", 7, '{"x":NaN}'),
            ("products", 7, "{broken"), ("products", 8, "2026-02-30"),
            ("customers", 0, "0"), ("customers", 2, ""),
            ("order_items", 1, "0"), ("orders", 3, "unknown"),
            ("orders", 7, "not-a-date"), ("promotions", 2, "101"),
            ("promotions", 2, "0"), ("promotions", 4, "true"),
        ]
        for table, column, value in cases:
            with self.subTest(table=table, column=column, value=value):
                self.rows = sample_rows()
                self.rows[table][0][column] = value
                self.write_sources()
                with self.assertRaises(DataValidationError):
                    load_snapshot(self.data)

    def test_missing_file_empty_table_duplicate_keys_and_orphan_references(self):
        for table, modify in [
            ("products", lambda rows: rows.append(rows[0].copy())),
            ("order_items", lambda rows: rows.append(rows[0].copy())),
            ("categories", lambda rows: rows.clear()),
            ("products", lambda rows: rows[0].__setitem__(3, "999")),
        ]:
            with self.subTest(table=table):
                self.rows = sample_rows()
                modify(self.rows[table])
                self.write_sources()
                with self.assertRaises(DataValidationError):
                    load_snapshot(self.data)
        (self.data / "desafio_tecnico_ai_eng - customers.csv").unlink()
        with self.assertRaises(DataValidationError):
            load_snapshot(self.data)

    def test_ambiguous_active_promotions_are_rejected(self):
        self.rows["promotions"].append(["2", "81", "20", "Outra", "1"])
        self.write_sources()
        with self.assertRaisesRegex(DataValidationError, "múltiplas promoções"):
            load_snapshot(self.data)

    def test_bom_is_supported_but_malformed_columns_are_rejected(self):
        path = self.data / "desafio_tecnico_ai_eng - categories.csv"
        path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
        self.assertEqual(load_snapshot(self.data).row_counts["categories"], 1)
        path.write_text("category_id,name\n5,Example\n", encoding="utf-8")
        with self.assertRaises(DataValidationError):
            load_snapshot(self.data)

    def test_extra_csv_field_is_rejected(self):
        self.rows["products"][0].append("unexpected")
        self.write_sources()
        with self.assertRaises(DataValidationError):
            load_snapshot(self.data)

    def test_error_diagnostics_do_not_echo_personal_values(self):
        self.rows["customers"][0][0] = "private@example.invalid"
        self.write_sources()
        with self.assertRaises(DataValidationError) as caught:
            load_snapshot(self.data)
        self.assertNotIn("private@example.invalid", str(caught.exception))
        self.assertIn("customer_id", str(caught.exception))

    def test_failed_sql_constraints_preserve_referential_integrity(self):
        ingest(self.data, self.database)
        connection = sqlite3.connect(self.database)
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE products SET category_id=999")
            connection.rollback()
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE products SET stock_quantity=-1")
        finally:
            connection.close()

    def test_check_command_does_not_create_database_or_print_customer_data(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["check-data", "--data-dir", str(self.data)])
        self.assertEqual(code, 0)
        self.assertNotIn("cliente@example.invalid", output.getvalue())
        self.assertFalse(self.database.exists())

    def test_cli_failure_is_nonzero_and_has_safe_diagnostic(self):
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            code = main(["check-data", "--data-dir", str(self.root / "missing")])
        self.assertEqual(code, 1)
        self.assertIn("arquivo ausente", json.loads(errors.getvalue())["error"])

    def test_cli_handles_storage_failure(self):
        errors = io.StringIO()
        with patch("emporio_ai.cli.ingest", side_effect=sqlite3.OperationalError("locked")):
            with contextlib.redirect_stderr(errors):
                code = main(["ingest", "--data-dir", str(self.data)])
        self.assertEqual(code, 1)
        self.assertIn("Falha de acesso", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
