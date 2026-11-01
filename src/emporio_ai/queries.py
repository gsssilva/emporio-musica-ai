"""Read-only data access with a deliberately small, explicit response surface."""

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from contextlib import closing
from pathlib import Path

from emporio_ai.commerce import discounted_price, quote_payment


class OrderAccessError(LookupError):
    pass


class AuthenticationRequired(PermissionError):
    pass


class ProductUnavailable(ValueError):
    pass


def _positive_integer(value: int) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError("Identificador deve ser um inteiro positivo.")
    return value


def _terms(text: str) -> list[str]:
    text = "".join(char for char in unicodedata.normalize("NFKD", text.casefold())
                   if not unicodedata.combining(char))
    aliases = {"violoes": "violao", "guitarras": "guitarra", "baixos": "baixo",
               "ukuleles": "ukulele", "baterias": "bateria", "teclados": "teclado"}
    return [aliases.get(term, term) for term in re.findall(r"[a-z0-9]+", text)]


class StoreQueries:
    def __init__(self, database: Path):
        self.database = database.resolve()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database.as_uri() + "?mode=ro", uri=True, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        return connection

    @staticmethod
    def _source(connection: sqlite3.Connection) -> dict:
        metadata = connection.execute(
            "SELECT imported_at FROM import_metadata WHERE singleton=1"
        ).fetchone()
        return {"kind": "local_snapshot", "imported_at": metadata["imported_at"],
                "live_external_integration": False}

    @staticmethod
    def _product(row: sqlite3.Row) -> dict:
        promotion_bps = row["discount_bps"] or 0
        return {
            "product_id": row["product_id"], "name": row["name"],
            "category_id": row["category_id"], "category": row["category_name"],
            "description": row["description"], "specs": json.loads(row["specs_json"]),
            "stock_quantity": row["stock_quantity"], "status": row["status"],
            "available": row["status"] == "active" and row["stock_quantity"] > 0,
            "table_price_cents": row["price_cents"],
            "current_price_cents": discounted_price(row["price_cents"], promotion_bps),
            "promotion_bps": promotion_bps, "promotion": row["promotion_description"],
            "pricing_basis": "current_price_before_payment_conditions",
        }

    @staticmethod
    def _product_query() -> str:
        return """SELECT p.*, c.name AS category_name, pr.discount_bps,
            pr.description AS promotion_description FROM products p
            JOIN categories c ON c.category_id=p.category_id
            LEFT JOIN promotions pr ON pr.product_id=p.product_id AND pr.is_active=1"""

    def search_products(self, *, query: str = "", category_id: int | None = None,
                        max_price_cents: int | None = None, available_only: bool = True,
                        limit: int = 5) -> dict:
        if not isinstance(query, str) or len(query) > 200:
            raise ValueError("Consulta deve ter até 200 caracteres.")
        if type(available_only) is not bool or type(limit) is not int or not 1 <= limit <= 10:
            raise ValueError("Filtros de disponibilidade ou limite inválidos.")
        if category_id is not None:
            _positive_integer(category_id)
        if max_price_cents is not None and (
            type(max_price_cents) is not int or max_price_cents < 0
        ):
            raise ValueError("Orçamento inválido.")
        requested = _terms(query)
        sql, params = self._product_query(), []
        if category_id is not None:
            sql += " WHERE p.category_id=?"
            params.append(category_id)
        with closing(self._connect()) as connection:
            if category_id is None and requested:
                categories = connection.execute("SELECT category_id,name FROM categories").fetchall()
                exact = [category["category_id"] for category in categories
                         if _terms(category["name"]) == requested]
                if len(exact) == 1:
                    sql += " WHERE p.category_id=?"
                    params.append(exact[0])
            products = [self._product(row) for row in connection.execute(sql, params)]
            matches = []
            for product in products:
                if available_only and not product["available"]:
                    continue
                if max_price_cents is not None and product["current_price_cents"] > max_price_cents:
                    continue
                terms = _terms(" ".join(product[key] for key in ("name", "category", "description")))
                if all(any(term in candidate for candidate in terms) for term in requested):
                    matches.append(product)
            matches.sort(key=lambda product: (product["current_price_cents"], product["product_id"]))
            return {"products": matches[:limit], "matched_count": len(matches),
                    "truncated": len(matches) > limit, "source": self._source(connection)}

    def list_categories(self) -> dict:
        with closing(self._connect()) as connection:
            categories = connection.execute("SELECT category_id,name FROM categories ORDER BY category_id").fetchall()
            return {"categories": [dict(row) for row in categories], "source": self._source(connection)}

    def get_product(self, product_id: int) -> dict:
        _positive_integer(product_id)
        with closing(self._connect()) as connection:
            row = connection.execute(
                self._product_query() + " WHERE p.product_id=?", (product_id,)
            ).fetchone()
            return {"product": self._product(row) if row else None,
                    "source": self._source(connection)}

    def quote_product(self, product_id: int, *, method: str, installments: int = 1) -> dict:
        result = self.get_product(product_id)
        product = result["product"]
        if product is None or not product["available"]:
            raise ProductUnavailable("Produto não disponível para uma nova compra.")
        return {"product_id": product_id, "product_name": product["name"],
                "quote": quote_payment(product["table_price_cents"],
                                       promotion_bps=product["promotion_bps"],
                                       method=method, installments=installments),
                "source": result["source"]}

    def get_order(self, order_id: int, *, authorized_customer_id: int | None) -> dict:
        """Customer context must come from the server, never model-provided arguments."""
        _positive_integer(order_id)
        if authorized_customer_id is None:
            raise AuthenticationRequired("É necessário um contexto de cliente autorizado pelo servidor.")
        _positive_integer(authorized_customer_id)
        with closing(self._connect()) as connection:
            row = connection.execute(
                """SELECT order_id,order_date,status,total_cents,payment_method,
                tracking_code,estimated_delivery FROM orders WHERE order_id=? AND customer_id=?""",
                (order_id, authorized_customer_id),
            ).fetchone()
            if row is None:
                raise OrderAccessError("Pedido não encontrado para o cliente autorizado.")
            items = connection.execute(
                """SELECT i.product_id,p.name,i.quantity FROM order_items i
                JOIN products p ON p.product_id=i.product_id WHERE i.order_id=?
                ORDER BY i.product_id""", (order_id,),
            ).fetchall()
            order = dict(row)
            order["items"] = [dict(item) for item in items]
            order["actual_received_at"] = None
            order["purchase_channel"] = None
            return {"order": order, "source": self._source(connection)}
