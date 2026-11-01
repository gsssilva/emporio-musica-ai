"""Audit the supplied CSV snapshot without exposing customer records.

Uses only the Python standard library. Run from any directory; --data-dir defaults
to the project's data/ directory. Comparisons use current prices, not historical ones.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


SCHEMAS = {
    "categories": "category_id name description",
    "customers": "customer_id name phone email city",
    "products": "product_id price_brl name category_id description stock_quantity status specs created_at",
    "orders": "order_id customer_id order_date status total_brl payment_method tracking_code estimated_delivery notes",
    "order_items": "order_id quantity product_id",
    "promotions": "promotion_id product_id discount_percent description is_active",
}
PRIMARY_KEYS = {
    "categories": "category_id", "customers": "customer_id",
    "products": "product_id", "orders": "order_id", "promotions": "promotion_id",
}
RELATIONS = [
    ("products", "category_id", "categories", "category_id"),
    ("orders", "customer_id", "customers", "customer_id"),
    ("order_items", "order_id", "orders", "order_id"),
    ("order_items", "product_id", "products", "product_id"),
    ("promotions", "product_id", "products", "product_id"),
]


def decimal_value(value: str) -> Decimal:
    number = Decimal(value)
    if not number.is_finite() or number < 0:
        raise ValueError("Expected a finite nonnegative number")
    return number


def require(condition: bool) -> None:
    if not condition:
        raise ValueError("Invalid domain value")


def audit(data_dir: Path) -> dict:
    report = {"files": {}, "errors": [], "warnings": [], "summary": {}}
    tables = {}
    for name, schema in SCHEMAS.items():
        path = data_dir / f"desafio_tecnico_ai_eng - {name}.csv"
        try:
            raw = path.read_bytes()
            with path.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                if reader.fieldnames != schema.split():
                    report["errors"].append(f"{name}: unexpected column schema")
                    continue
                rows = list(reader)
        except (OSError, UnicodeError, csv.Error):
            report["errors"].append(f"{name}: missing or unreadable CSV")
            continue
        if any(None in row or any(v is None for v in row.values()) for row in rows):
            report["errors"].append(f"{name}: malformed CSV row")
            continue
        tables[name] = rows
        report["files"][name] = {
            "filename": path.name, "sha256": hashlib.sha256(raw).hexdigest(),
            "rows": len(rows), "columns": schema.split(),
            "empty_values": {column: sum(row[column] == "" for row in rows)
                             for column in schema.split()},
        }
        if not rows:
            report["errors"].append(f"{name}: empty table")
        nullable = {"tracking_code", "estimated_delivery", "notes"} if name == "orders" else set()
        for column in schema.split():
            if column not in nullable and any(not row[column].strip() for row in rows):
                report["errors"].append(f"{name}.{column}: required value missing")
        if key := PRIMARY_KEYS.get(name):
            if any(count > 1 for count in Counter(row[key] for row in rows).values()):
                report["errors"].append(f"{name}: duplicate primary key")

    if report["errors"]:
        return report

    for name, column, target, key in RELATIONS:
        known = {row[key] for row in tables[target]}
        if any(row[column] not in known for row in tables[name]):
            report["errors"].append(f"{name}.{column}: orphan reference")

    for name, rows in tables.items():
        for index, row in enumerate(rows, start=2):
            try:
                for column in SCHEMAS[name].split():
                    if column.endswith("_id") and int(row[column]) <= 0:
                        raise ValueError("Nonpositive identifier")
                if name == "products":
                    decimal_value(row["price_brl"])
                    require(int(row["stock_quantity"]) >= 0)
                    require(row["status"] in {"active", "discontinued", "coming_soon"})
                    require(isinstance(json.loads(row["specs"]), dict))
                    date.fromisoformat(row["created_at"])
                elif name == "orders":
                    decimal_value(row["total_brl"])
                    require(row["status"] in {"pending", "confirmed", "shipped", "delivered", "cancelled"})
                    date.fromisoformat(row["order_date"])
                    if row["estimated_delivery"]:
                        date.fromisoformat(row["estimated_delivery"])
                elif name == "order_items":
                    require(int(row["quantity"]) > 0)
                elif name == "promotions":
                    require(Decimal(0) < decimal_value(row["discount_percent"]) <= Decimal(100))
                    require(row["is_active"] in {"0", "1"})
            except (ValueError, TypeError, InvalidOperation):
                report["errors"].append(f"{name}: invalid domain value at CSV line {index}")
    if report["errors"]:
        return report

    products = {row["product_id"]: row for row in tables["products"]}
    orders_with_items = {row["order_id"] for row in tables["order_items"]}
    if any(row["order_id"] not in orders_with_items for row in tables["orders"]):
        report["warnings"].append("Some orders have no order items")
    active_promotions = [row for row in tables["promotions"] if row["is_active"] == "1"]
    if any(count > 1 for count in Counter(row["product_id"] for row in active_promotions).values()):
        report["warnings"].append("Multiple active promotions for a product require clarification")
    mismatches = []
    for order in tables["orders"]:
        items = [row for row in tables["order_items"] if row["order_id"] == order["order_id"]]
        total = sum((Decimal(products[item["product_id"]]["price_brl"]) * int(item["quantity"])
                     for item in items), Decimal(0))
        if items and total != Decimal(order["total_brl"]):
            mismatches.append({"order_id": int(order["order_id"]),
                               "current_catalog_sum_brl": str(total),
                               "recorded_total_brl": order["total_brl"]})
    if mismatches:
        report["warnings"].append(
            "Current catalog sums differ from some recorded order totals; historical unit prices are absent"
        )
    report["summary"] = {
        "product_statuses": dict(sorted(Counter(row["status"] for row in products.values()).items())),
        "available_products": sum(row["status"] == "active" and int(row["stock_quantity"]) > 0
                                  for row in products.values()),
        "products_by_category": dict(sorted(Counter(row["category_id"] for row in products.values()).items())),
        "nonactive_with_positive_stock": [int(row["product_id"]) for row in products.values()
                                          if row["status"] != "active" and int(row["stock_quantity"]) > 0],
        "order_statuses": dict(sorted(Counter(row["status"] for row in tables["orders"]).items())),
        "order_date_range": [min(row["order_date"] for row in tables["orders"]),
                             max(row["order_date"] for row in tables["orders"])],
        "active_promotions": len(active_promotions),
        "inactive_promotions": len(tables["promotions"]) - len(active_promotions),
        "active_promotion_product_ids": sorted(int(row["product_id"]) for row in active_promotions),
        "current_price_comparison": mismatches,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(args.data_dir)
    content = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return int(bool(report["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
