"""Transactional import of a validated snapshot; no commercial mutations."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from emporio_ai.source_data import DataValidationError, SourceSnapshot, load_snapshot

SCHEMA_VERSION = 1
SCHEMA = (
    """CREATE TABLE IF NOT EXISTS import_metadata (
        singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
        schema_version INTEGER NOT NULL, imported_at TEXT NOT NULL,
        source_manifest TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS categories (
        category_id INTEGER PRIMARY KEY CHECK(category_id > 0),
        name TEXT NOT NULL, description TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS customers (
        customer_id INTEGER PRIMARY KEY CHECK(customer_id > 0),
        name TEXT NOT NULL, phone TEXT NOT NULL, email TEXT NOT NULL, city TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS products (
        product_id INTEGER PRIMARY KEY CHECK(product_id > 0),
        price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
        name TEXT NOT NULL, category_id INTEGER NOT NULL REFERENCES categories(category_id),
        description TEXT NOT NULL, stock_quantity INTEGER NOT NULL CHECK(stock_quantity >= 0),
        status TEXT NOT NULL CHECK(status IN ('active','discontinued','coming_soon')),
        specs_json TEXT NOT NULL, created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS orders (
        order_id INTEGER PRIMARY KEY CHECK(order_id > 0),
        customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
        order_date TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('pending','confirmed','shipped','delivered','cancelled')),
        total_cents INTEGER NOT NULL CHECK(total_cents >= 0),
        payment_method TEXT NOT NULL, tracking_code TEXT, estimated_delivery TEXT, notes TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS order_items (
        order_id INTEGER NOT NULL REFERENCES orders(order_id),
        quantity INTEGER NOT NULL CHECK(quantity > 0),
        product_id INTEGER NOT NULL REFERENCES products(product_id),
        PRIMARY KEY(order_id, product_id)
    )""",
    """CREATE TABLE IF NOT EXISTS promotions (
        promotion_id INTEGER PRIMARY KEY CHECK(promotion_id > 0),
        product_id INTEGER NOT NULL REFERENCES products(product_id),
        discount_bps INTEGER NOT NULL CHECK(discount_bps > 0 AND discount_bps <= 10000),
        description TEXT NOT NULL, is_active INTEGER NOT NULL CHECK(is_active IN (0,1))
    )""",
    "CREATE UNIQUE INDEX IF NOT EXISTS one_active_promotion ON promotions(product_id) WHERE is_active=1",
    "CREATE INDEX IF NOT EXISTS products_category ON products(category_id)",
    "CREATE INDEX IF NOT EXISTS orders_customer ON orders(customer_id)",
)
RENAMES = {
    "price_brl": "price_cents", "total_brl": "total_cents",
    "discount_percent": "discount_bps", "specs": "specs_json",
}


def _validate_existing_database(connection: sqlite3.Connection) -> None:
    tables = {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )}
    if not tables:
        return
    expected = {"import_metadata", "categories", "customers", "products", "orders", "order_items", "promotions"}
    if tables != expected:
        raise DataValidationError("Banco não reconhecido; use um caminho dedicado ao projeto.")
    version = connection.execute(
        "SELECT schema_version FROM import_metadata WHERE singleton=1"
    ).fetchone()
    if version is None or version[0] != SCHEMA_VERSION:
        raise DataValidationError("Versão do banco incompatível; migração explícita necessária.")


def _write_snapshot(connection: sqlite3.Connection, snapshot: SourceSnapshot) -> str:
    for statement in SCHEMA:
        connection.execute(statement)
    for table in ("promotions", "order_items", "orders", "products", "customers", "categories"):
        connection.execute(f"DELETE FROM {table}")
    # Table and column names come exclusively from the application's closed schemas.
    for table, rows in snapshot.tables.items():
        columns = [RENAMES.get(column, column) for column in rows[0]]
        placeholders = ",".join("?" for _ in columns)
        statement = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
        connection.executemany(statement, [tuple(row.values()) for row in rows])
    imported_at = datetime.now(timezone.utc).isoformat()
    connection.execute(
        """INSERT INTO import_metadata(singleton, schema_version, imported_at, source_manifest)
        VALUES (1, ?, ?, ?) ON CONFLICT(singleton) DO UPDATE SET
        schema_version=excluded.schema_version, imported_at=excluded.imported_at,
        source_manifest=excluded.source_manifest""",
        (SCHEMA_VERSION, imported_at, json.dumps(snapshot.manifest, sort_keys=True)),
    )
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise DataValidationError("A carga produziu relacionamentos inconsistentes.")
    return imported_at


def ingest(data_dir: Path, database: Path) -> dict:
    snapshot = load_snapshot(data_dir)
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database, timeout=10)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        _validate_existing_database(connection)
        imported_at = _write_snapshot(connection, snapshot)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return {"schema_version": SCHEMA_VERSION, "imported_at": imported_at,
            "row_counts": snapshot.row_counts, "source_manifest": snapshot.manifest}
