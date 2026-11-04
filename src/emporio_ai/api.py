"""Local customer-service chat and documented API."""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from emporio_ai.commerce import PaymentRuleError
from emporio_ai.queries import ProductUnavailable, StoreQueries
from emporio_ai.agent import CustomerAgent
from emporio_ai.chat_api import conversation_router
from emporio_ai.policies import PolicySearch
from emporio_ai.provider import OllamaProvider, ProviderUnavailable
from emporio_ai.sessions import SessionStore, SessionExpired, SessionBusy, SessionLimit
from emporio_ai.settings import Settings
from emporio_ai.tools import ToolRegistry


def create_app(database: Path | None = None, *, agent=None, sessions=None) -> FastAPI:
    config = Settings.from_env()
    store = StoreQueries(database or config.database)
    customer_agent = agent or CustomerAgent(OllamaProvider(config.ollama_url, config.model),
                                           ToolRegistry(store, PolicySearch(config.policies_database)))
    session_store = sessions or SessionStore(database.parent / "sessions.sqlite3" if database is not None else config.sessions_database)
    app = FastAPI(title="Empório da Música", version="0.1.0",
                  description="Agente de atendimento gratuito com modelo local. Crie uma sessão, copie session_id para Authorize (Bearer) e envie mensagens em POST /chat. Não requer chave de API paga.")
    app.mount("/assets", StaticFiles(directory=Path(__file__).parent / "web"), name="assets")
    app.include_router(conversation_router(customer_agent, session_store, demo_customer_id=config.demo_customer_id))

    @app.exception_handler(ProviderUnavailable)
    async def provider_error(_request, error):
        return JSONResponse(status_code=503, content={"detail": str(error)})

    @app.exception_handler(SessionExpired)
    async def session_expired(_request, error):
        return JSONResponse(status_code=401, content={"detail": str(error)}, headers={"WWW-Authenticate": "Bearer"})

    @app.exception_handler(SessionBusy)
    async def session_busy(_request, error):
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.exception_handler(SessionLimit)
    async def session_limit(_request, error):
        return JSONResponse(status_code=429, content={"detail": str(error)})

    @app.exception_handler(sqlite3.Error)
    async def database_error(_request, _error):
        return JSONResponse(status_code=503, content={"detail": "Base local indisponível. Execute a ingestão dos dados."})

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(Path(__file__).parent / "web" / "chat.html")

    @app.get("/catalogo", include_in_schema=False)
    def catalog_preview():
        return FileResponse(Path(__file__).parent / "web" / "index.html")

    @app.get("/health")
    def health():
        source = store.search_products(limit=1)["source"]
        return {"status": "ready", "source": source}

    @app.get("/api/categories")
    def categories():
        return store.list_categories()

    @app.get("/api/products")
    def products(query: str = Query(default="", max_length=200),
                 category_id: int | None = Query(default=None, gt=0),
                 max_price_brl: Decimal | None = Query(default=None, ge=0, decimal_places=2),
                 available_only: bool = True, limit: int = Query(default=10, ge=1, le=10)):
        return store.search_products(query=query, category_id=category_id,
                                     max_price_cents=int(max_price_brl * 100) if max_price_brl is not None else None,
                                     available_only=available_only, limit=limit)

    @app.get("/api/products/{product_id}")
    def product(product_id: int):
        if product_id <= 0:
            raise HTTPException(422, "Identificador inválido.")
        result = store.get_product(product_id)
        if result["product"] is None:
            raise HTTPException(404, "Produto não encontrado.")
        return result

    @app.get("/api/products/{product_id}/quote")
    def quote(product_id: int, method: Literal["pix", "credit", "debit", "boleto"] = "pix",
              installments: int = Query(default=1, ge=1, le=12)):
        if product_id <= 0:
            raise HTTPException(422, "Identificador inválido.")
        try:
            return store.quote_product(product_id, method=method, installments=installments)
        except ProductUnavailable as error:
            raise HTTPException(409, str(error)) from None
        except PaymentRuleError as error:
            raise HTTPException(422, str(error)) from None

    return app


app = create_app()
