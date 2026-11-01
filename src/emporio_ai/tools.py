"""Closed registry: model arguments cannot select customer identity or execute SQL."""

from __future__ import annotations

import sqlite3
import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from emporio_ai.commerce import PaymentRuleError, brl_to_cents
from emporio_ai.policies import PolicySearch
from emporio_ai.queries import AuthenticationRequired, OrderAccessError, ProductUnavailable, StoreQueries


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SearchProducts(Arguments):
    query: str = Field(default="", max_length=200)
    max_price_brl: int | float | str | None = Field(default=None, description="Orçamento máximo em reais, por exemplo 1000.50. Não converta para centavos.")
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
    "search_products": (SearchProducts, "Buscar instrumentos. Orçamento de entrada em REAIS. query contém nome ou categoria em palavras naturais, por exemplo Takamine GD20 ou violões. Não use IDs de categoria nem inclua o orçamento em query. O preço retornado já considera promoção ativa, sem desconto adicional PIX."),
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
        except ValidationError as error:
            fields = [{"field": ".".join(map(str, item["loc"])), "type": item["type"]}
                      for item in error.errors(include_input=False)]
            return {"ok": False, "error": "invalid_arguments", "fields": fields,
                    "message": "Corrija os argumentos conforme o esquema. Identificadores e limite devem ser inteiros; orçamento de entrada está em reais; campos opcionais podem ser null."}
        except TypeError:
            return {"ok": False, "error": "invalid_arguments"}
        try:
            sources = []
            if name == "search_products":
                budget = args.pop("max_price_brl")
                result = self.store.search_products(**args, max_price_cents=brl_to_cents(budget) if budget is not None else None)
                sources = self._catalog_sources(result["products"], result["source"])
                if not sources:
                    lookup = hashlib.sha256(json.dumps({"filters": args, "budget_brl": budget}, sort_keys=True).encode()).hexdigest()[:12]
                    sources = [{**result["source"], "id": "catalog_search:" + lookup, "kind": "catalog_lookup", "title": "Consulta de catálogo sem resultados"}]
            elif name == "get_product":
                result = self.store.get_product(**args)
                sources = self._catalog_sources([result["product"]] if result["product"] else [], result["source"])
                if not sources:
                    sources = [{**result["source"], "id": f"catalog_lookup:{args['product_id']}", "kind": "catalog_lookup", "product_id": args["product_id"], "title": "Consulta de produto sem resultado"}]
            elif name == "quote_payment":
                result = self.store.quote_product(**args)
                sources = [{**result["source"], "id": f"catalog:{args['product_id']}", "kind": "catalog",
                            "title": result["product_name"], "product_id": args["product_id"]}]
                sources += self.policies.search("parcelamento pagamento PIX cumulatividade")["sources"]
            elif name == "search_policies":
                result = self.policies.search(**args)
                sources = result["sources"]
                result = {"matched": result["matched"], "source_ids": [source["id"] for source in sources]}
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
