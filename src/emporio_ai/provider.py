"""Local-only Ollama adapter. No API keys, cloud models or paid fallbacks."""

from __future__ import annotations

from urllib.parse import urlparse

import httpx


class ProviderUnavailable(RuntimeError):
    pass


def validate_local_url(url: str) -> str:
    parsed = urlparse(url)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"}):
        raise ValueError("O provedor deve ser um Ollama local, sem credenciais ou endpoints de nuvem.")
    return url.rstrip("/")


class OllamaProvider:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "qwen3:8b"):
        self.base_url = validate_local_url(base_url)
        if not model or "cloud" in model.casefold() or "/" in model or len(model) > 100:
            raise ValueError("Selecione um modelo instalado localmente, sem tag de nuvem.")
        self.model = model
        self.options = {"temperature": 0, "seed": 42, "num_ctx": 8192, "num_predict": 1200}

    def ready(self) -> bool:
        try:
            with httpx.Client(timeout=2, trust_env=False) as client:
                response = client.get(self.base_url + "/api/tags")
                response.raise_for_status()
                return self.model in {model["name"] for model in response.json().get("models", [])}
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return False

    def chat(self, messages: list[dict], *, tools: list[dict] | None = None,
             schema: dict | None = None, timeout: float = 60) -> dict:
        payload = {"model": self.model, "messages": messages, "stream": False, "think": False,
                   "keep_alive": "10m", "options": dict(self.options)}
        if tools:
            payload["tools"] = tools
        if schema:
            payload["format"] = schema
        try:
            with httpx.Client(timeout=timeout, trust_env=False) as client:
                response = client.post(self.base_url + "/api/chat", json=payload)
                response.raise_for_status()
                result = response.json()
            if not result.get("done") or result.get("done_reason") == "length":
                raise ProviderUnavailable("O modelo não concluiu a resposta no limite configurado.")
            message = result["message"]
            if not isinstance(message, dict) or message.get("role") != "assistant" or not isinstance(message.get("content", ""), str):
                raise ValueError("Invalid message")
            return {"message": message,
                    "usage": {"input_tokens": result.get("prompt_eval_count", 0),
                              "output_tokens": result.get("eval_count", 0)}}
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise ProviderUnavailable("Modelo local indisponível. Verifique o Ollama e o modelo instalado.") from None
