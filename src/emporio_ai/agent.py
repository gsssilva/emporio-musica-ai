"""Bounded tool-calling loop and validation of evidence identifiers."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from emporio_ai.provider import ProviderUnavailable
from emporio_ai.tools import ToolRegistry

SYSTEM = (Path(__file__).parent / "prompts/system.txt").read_text(encoding="utf-8")
PROMPT_VERSION = hashlib.sha256(SYSTEM.encode()).hexdigest()[:12]
logger = logging.getLogger("emporio.agent")


class FinalAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    answer: str = Field(min_length=1, max_length=6000)
    source_ids: list[str] = Field(max_length=20)
    kind: Literal["grounded", "clarification", "greeting", "out_of_scope", "needs_human"]


class CustomerAgent:
    def __init__(self, provider, tools: ToolRegistry, *, max_rounds: int = 4,
                 max_tool_calls: int = 8, deadline_seconds: float = 240):
        self.provider, self.tools = provider, tools
        self.max_rounds, self.max_tool_calls = max_rounds, max_tool_calls
        self.deadline_seconds = deadline_seconds

    def respond(self, message: str, *, history: list[dict] | None = None,
                customer_id: int | None = None) -> dict:
        if not isinstance(message, str) or not message.strip() or len(message) > 2000:
            raise ValueError("Mensagem deve ter entre 1 e 2000 caracteres.")
        started, request_id = time.monotonic(), uuid4().hex
        now = datetime.now(ZoneInfo("America/Campo_Grande")).isoformat()
        context = f"\nData e hora local da loja: {now}. Contexto de pedido autorizado: {'sim, demonstração local' if customer_id is not None else 'não'}."
        safe_history = [{"role": item["role"], "content": item["content"]}
                        for item in (history or [])[-6:] if item.get("role") in {"user", "assistant"}]
        messages = [{"role": "system", "content": SYSTEM + context}, *safe_history,
                    {"role": "user", "content": message.strip()}]
        sources, trace, usage = {}, [], {"input_tokens": 0, "output_tokens": 0}
        calls_count, requires_confirmation = 0, False

        def call(*, tools=None, schema=None):
            remaining = self.deadline_seconds - (time.monotonic() - started)
            if remaining <= 0 or len(json.dumps(messages, ensure_ascii=False)) > 28000:
                raise ProviderUnavailable("Limite de tempo ou contexto atingido. Inicie uma nova conversa ou reduza a pergunta.")
            result = self.provider.chat(messages, tools=tools, schema=schema, timeout=min(90, remaining))
            for key in usage:
                usage[key] += result.get("usage", {}).get(key, 0)
            return result["message"]

        def finish(answer, selected, kind, status):
            logger.info("request=%s provider=ollama model=%s prompt=%s status=%s calls=%d duration_ms=%d",
                        request_id, self.provider.model, PROMPT_VERSION, status, calls_count,
                        int((time.monotonic() - started) * 1000))
            return {"answer": answer, "kind": kind, "sources": selected, "tool_trace": trace,
                    "request_id": request_id, "provider": "ollama", "model": self.provider.model,
                    "prompt_version": PROMPT_VERSION, "usage": usage, "status": status}

        for _round in range(self.max_rounds):
            assistant = call(tools=self.tools.specifications())
            calls = assistant.get("tool_calls") or []
            messages.append({key: value for key, value in assistant.items()
                             if key in {"role", "content", "tool_calls"}})
            if not calls:
                break
            if not isinstance(calls, list) or calls_count + len(calls) > self.max_tool_calls:
                return finish("Não consegui concluir a consulta dentro do limite. Podemos dividir a pergunta?", [], "needs_human", "tool_limit")
            for tool_call in calls:
                calls_count += 1
                function = tool_call.get("function", {}) if isinstance(tool_call, dict) else {}
                if not isinstance(function, dict):
                    function = {}
                name, arguments = function.get("name", ""), function.get("arguments", {})
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except ValueError:
                        arguments = None
                result = self.tools.execute(name, arguments, customer_id=customer_id)
                if len(json.dumps(result, ensure_ascii=False)) > 18000:
                    result = {"ok": False, "error": "result_too_large"}
                trace.append({"tool": name, "ok": result["ok"]})
                if result["ok"]:
                    for source in result["sources"]:
                        sources[source["id"]] = source
                    if name == "quote_payment" and result["data"]["quote"]["status"] == "needs_confirmation":
                        requires_confirmation = True
                messages.append({"role": "tool", "tool_name": name,
                                 "content": json.dumps(result, ensure_ascii=False)})
        else:
            return finish("Não consegui concluir a consulta dentro do limite. Podemos tratar uma dúvida por vez?", [], "needs_human", "round_limit")

        allowed_ids = list(sources)
        messages.append({"role": "system", "content": "Finalize em JSON conforme o esquema. Use apenas estes source_ids realmente consultados: "
                         + json.dumps(allowed_ids) + ". Se faltar evidência, peça esclarecimento. Não use ferramentas nesta etapa."})
        final_message = call(schema=FinalAnswer.model_json_schema())
        try:
            final = FinalAnswer.model_validate_json(final_message["content"])
            if any(source_id not in sources for source_id in final.source_ids):
                raise ValueError("Unknown citation")
            if final.kind == "grounded" and not final.source_ids:
                raise ValueError("Missing evidence")
            if not final.source_ids and re.search(r"R\$|\breais\b|\bem estoque\b|\bdisponíveis\b", final.answer, re.I):
                raise ValueError("Commercial claim without evidence")
        except (ValidationError, ValueError, KeyError):
            return finish("Não consegui confirmar uma resposta com as fontes disponíveis. Pode detalhar sua dúvida para eu consultar novamente?", [], "needs_human", "response_guard")
        answer, kind = final.answer, final.kind
        if requires_confirmation:
            kind = "needs_human"
            answer += " Essa condição precisa ser confirmada com a equipe antes de concluir a compra."
        selected = [sources[source_id] for source_id in dict.fromkeys(final.source_ids)]
        return finish(answer, selected, kind, "completed")
