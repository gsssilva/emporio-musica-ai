"""Conversation endpoints shared by the documented API and local evaluation."""

from __future__ import annotations

from threading import BoundedSemaphore

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from emporio_ai.sessions import SessionStore


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=2000)


def conversation_router(agent, sessions: SessionStore, *, demo_customer_id: int | None = None):
    router = APIRouter(tags=["Atendimento"])
    bearer = HTTPBearer(description="Token de conversa retornado por POST /sessions. Não é uma chave de API paga.")
    inference_slot = BoundedSemaphore(1)

    @router.post("/sessions", status_code=201, summary="1. Criar uma conversa local")
    def create_session(payload: SessionCreate | None = None):
        return sessions.create(customer_id=demo_customer_id)

    @router.post("/chat", summary="2. Enviar mensagem ao agente")
    def chat(payload: ChatMessage, credentials: HTTPAuthorizationCredentials = Depends(bearer)):
        with sessions.claim(credentials.credentials) as session:
            if not inference_slot.acquire(blocking=False):
                raise HTTPException(429, "O modelo local está atendendo outra conversa. Tente novamente em instantes.")
            try:
                result = agent.respond(payload.message, history=session.history, customer_id=session.customer_id)
                sessions.append(session, payload.message, result["answer"])
                return result
            finally:
                inference_slot.release()

    @router.delete("/sessions/current", status_code=204, summary="3. Excluir conversa e histórico")
    def delete_session(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
        sessions.delete(credentials.credentials)
        return Response(status_code=204)

    @router.get("/chat/health", summary="Verificar o modelo local")
    def chat_health():
        if hasattr(agent.provider, "ready") and not agent.provider.ready():
            raise HTTPException(503, "Modelo local não disponível. Inicie o Ollama e baixe o modelo configurado.")
        return {"status": "ready", "provider": "ollama", "model": agent.provider.model,
                "paid_api": False, "demo_identity": demo_customer_id is not None}

    return router
