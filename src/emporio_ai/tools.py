"""Closed registry: model arguments cannot select customer identity or execute SQL."""

from __future__ import annotations

import sqlite3
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from emporio_ai.commerce import PaymentRuleError
from emporio_ai.policies import PolicySearch
from emporio_ai.queries import AuthenticationRequired, OrderAccessError, ProductUnavailable, StoreQueries


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SearchProducts(Arguments):
    query: str = Field(default="", max_length=200)
    category_id: int | None = Field(default=None, gt=0)
    max_price_cents: int | None = Field(default=None, ge=0)
    available_only: bool = True
    limit: int = Field(default=5, ge=1, le=5)


class Product(Arguments):
    product_id: int = Field(gt=0)


class Quote(Product):
    method: Literal["pix", "credit", "debit", "boleto"]
    installments: int = Field(default=1, ge=1, le=12)


class Policies(Arguments):
    query: str = Field(min_length=1, max_length=500)


class Order(Arguments):
    order_id: int = Field(gt=0)


DEFINITIONS = {
    "search_products": (SearchProducts, "Buscar instrumentos. Orçamento em centavos: R$ 1000 = 100000. Use categoria e estoque. O preço retornado já considera promoção ativa, sem desconto adicional PIX."),
    "get_product": (Product, "Consultar preço, especificações, promoção, estoque e status de um produto, inclusive indisponíveis."),
    "quote_payment": (Quote, "Calcular valor final e parcelas de um produto disponível. Não calcule descontos por conta própria. Pode exigir confirmação humana."),
    "search_policies": (Policies, "Buscar políticas e informações da loja no manual com páginas e seções. Use para horário, endereço, pagamentos, trocas, garantia, frete e escopo."),
    "get_order_status": (Order, "Consultar pedido somente no contexto de cliente autorizado pelo servidor. Não recebe identidade, email ou customer_id."),
}


class ToolRegistry:
    def __init__(self, store: StoreQueries, policies: PolicySearch):
        self.store, self.policies = store, policies

    def specifications(self) -> list[dict]:
        return [{"type": "function", "function": {"name": name, "description": description,
                "parameters": model.model_json_schema()}} for name, (model, description) in DEFINITIONS.items()]

    @staticmethod
    def _catalog_sources(products: list[dict], source: dict) -> list[dict]:
        return [{**source, "id": f"catalog:{product['product_id']}", "kind": "catalog", "title": product["name"],
                 "product_id": product["product_id"]} for product in products]

    def execute(self, name: str, arguments: dict, *, customer_id: int | None) -> dict:
        if not isinstance(name, str) or name not in DEFINITIONS:
            return {"ok": False, "error": "unknown_tool"}
        try:
            args = DEFINITIONS[name][0].model_validate(arguments).model_dump()
        except (ValidationError, TypeError):
            return {"ok": False, "error": "invalid_arguments"}
        try:
            sources = []
            if name == "search_products":
                result = self.store.search_products(**args)
                sources = self._catalog_sources(result["products"], result["source"])
            elif name == "get_product":
                result = self.store.get_product(**args)
                sources = self._catalog_sources([result["product"]] if result["product"] else [], result["source"])
            elif name == "quote_payment":
                result = self.store.quote_product(**args)
                sources = [{**result["source"], "id": f"catalog:{args['product_id']}", "kind": "catalog",
                            "title": result["product_name"], "product_id": args["product_id"]}]
                sources += self.policies.search("parcelamento pagamento PIX cumulatividade")["sources"]
            elif name == "search_policies":
                result = self.policies.search(**args)
                sources = result["sources"]
            else:
                result = self.store.get_order(args["order_id"], authorized_customer_id=customer_id)
                sources = [{**result["source"], "id": f"order:{args['order_id']}", "kind": "order",
                            "title": f"Pedido {args['order_id']}"}]
            return {"ok": True, "data": result, "sources": sources}
        except AuthenticationRequired:
            return {"ok": False, "error": "authentication_required", "message": "Pedido requer contexto de cliente definido pelo servidor; dados no chat não autenticam o cliente."}
        except OrderAccessError:
            return {"ok": False, "error": "order_not_found_for_customer"}
        except ProductUnavailable:
            return {"ok": False, "error": "product_unavailable", "message": "Busque alternativas ativas com estoque, sem prometer reposição."}
        except PaymentRuleError as error:
            return {"ok": False, "error": "payment_rule", "message": str(error)}
        except (sqlite3.Error, OSError):
            return {"ok": False, "error": "data_unavailable"}
        except ValueError:
            return {"ok": False, "error": "invalid_arguments"}
