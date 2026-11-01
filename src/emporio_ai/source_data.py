"""Parse and validate one immutable CSV snapshot before opening the database."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

SCHEMAS = {
    "categories": "category_id name description",
    "customers": "customer_id name phone email city",
    "products": "product_id price_brl name category_id description stock_quantity status specs created_at",
    "orders": "order_id customer_id order_date status total_brl payment_method tracking_code estimated_delivery notes",
    "order_items": "order_id quantity product_id",
    "promotions": "promotion_id product_id discount_percent description is_active",
}
KEYS = {
    "categories": ("category_id",),
    "customers": ("customer_id",),
    "products": ("product_id",),
    "orders": ("order_id",),
    "order_items": ("order_id", "product_id"),
    "promotions": ("promotion_id",),
}
RELATIONS = (
    ("products", "category_id", "categories", "category_id"),
    ("orders", "customer_id", "customers", "customer_id"),
    ("order_items", "order_id", "orders", "order_id"),
    ("order_items", "product_id", "products", "product_id"),
    ("promotions", "product_id", "products", "product_id"),
)
PRODUCT_STATUSES = {"active", "discontinued", "coming_soon"}
ORDER_STATUSES = {"pending", "confirmed", "shipped", "delivered", "cancelled"}
MAX_INTEGER = 2**63 - 1


class DataValidationError(ValueError):
    """Safe diagnostic containing a source location, never its personal values."""


@dataclass(frozen=True)
class SourceSnapshot:
    tables: dict[str, list[dict]]
    manifest: dict[str, dict]

    @property
    def row_counts(self) -> dict[str, int]:
        return {name: len(rows) for name, rows in self.tables.items()}


def _integer(value: str, *, minimum: int = 1) -> int:
    number = int(value)
    if not minimum <= number <= MAX_INTEGER:
        raise ValueError("Integer outside supported range")
    return number


def _hundredths(value: str) -> int:
    """Convert currency to cents, or percentage to basis points, without rounding."""
    number = Decimal(value)
    if not number.is_finite() or not Decimal(0) <= number <= Decimal(MAX_INTEGER) / 100:
        raise ValueError("Number outside supported range")
    with localcontext() as context:
        context.prec = max(28, len(number.as_tuple().digits) + 2)
        scaled = number * 100
    if scaled != scaled.to_integral_value():
        raise ValueError("More than two meaningful decimal places")
    return int(scaled)


def _date(value: str) -> str:
    return date.fromisoformat(value).isoformat()


def _convert(table: str, column: str, value: str):
    if not value.strip():
        if table == "orders" and column in {"tracking_code", "estimated_delivery", "notes"}:
            return None
        raise ValueError("Required value missing")
    if column.endswith("_id") or column == "quantity":
        return _integer(value)
    if column == "stock_quantity":
        return _integer(value, minimum=0)
    if column in {"price_brl", "total_brl"}:
        return _hundredths(value)
    if column == "discount_percent":
        number = _hundredths(value)
        if not 0 < number <= 10000:
            raise ValueError("Invalid discount")
        return number
    if column == "is_active":
        if value not in {"0", "1"}:
            raise ValueError("Invalid active flag")
        return int(value)
    if column == "status":
        allowed = PRODUCT_STATUSES if table == "products" else ORDER_STATUSES
        if value not in allowed:
            raise ValueError("Unknown status")
    if column in {"created_at", "order_date", "estimated_delivery"}:
        return _date(value)
    if column == "specs":
        def reject_constant(_value: str):
            raise ValueError("Nonstandard JSON constant")

        specs = json.loads(value, parse_constant=reject_constant)
        if not isinstance(specs, dict):
            raise ValueError("Expected JSON object")
        return json.dumps(specs, ensure_ascii=False, sort_keys=True, allow_nan=False)
    return value


def _parse_table(table: str, raw: bytes) -> list[dict]:
    try:
        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        if reader.fieldnames != SCHEMAS[table].split():
            raise DataValidationError(f"{table}: colunas diferentes do esquema esperado.")
        rows = []
        keys = set()
        for source in reader:
            line = reader.line_num
            if None in source or any(value is None for value in source.values()):
                raise DataValidationError(f"{table}, linha {line}: quantidade de campos inválida.")
            row = {}
            for column, value in source.items():
                try:
                    row[column] = _convert(table, column, value)
                except (ValueError, TypeError, InvalidOperation, OverflowError, RecursionError):
                    raise DataValidationError(
                        f"{table}, linha {line}, campo {column}: valor inválido."
                    ) from None
            key = tuple(row[column] for column in KEYS[table])
            if key in keys:
                raise DataValidationError(f"{table}, linha {line}: chave duplicada.")
            keys.add(key)
            rows.append(row)
    except (UnicodeError, csv.Error):
        raise DataValidationError(f"{table}: CSV inválido ou codificação diferente de UTF-8.") from None
    if not rows:
        raise DataValidationError(f"{table}: tabela vazia.")
    return rows


def load_snapshot(data_dir: Path) -> SourceSnapshot:
    tables, manifest = {}, {}
    for table in SCHEMAS:
        path = data_dir / f"desafio_tecnico_ai_eng - {table}.csv"
        try:
            raw = path.read_bytes()
        except OSError:
            raise DataValidationError(f"{table}: arquivo ausente ou sem acesso de leitura.") from None
        tables[table] = _parse_table(table, raw)
        manifest[table] = {
            "filename": path.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "rows": len(tables[table]),
        }
    for table, column, target, key in RELATIONS:
        known = {row[key] for row in tables[target]}
        if any(row[column] not in known for row in tables[table]):
            raise DataValidationError(f"{table}.{column}: referência não encontrada em {target}.")
    order_ids = {row["order_id"] for row in tables["order_items"]}
    if any(row["order_id"] not in order_ids for row in tables["orders"]):
        raise DataValidationError("orders: pedido sem itens associados.")
    active_products = [row["product_id"] for row in tables["promotions"] if row["is_active"]]
    if len(active_products) != len(set(active_products)):
        raise DataValidationError("promotions: múltiplas promoções ativas para o mesmo produto.")
    return SourceSnapshot(tables=tables, manifest=manifest)
