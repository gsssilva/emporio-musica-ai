from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from emporio_ai.provider import validate_local_url


@dataclass(frozen=True)
class Settings:
    database: Path = Path("runtime/emporio.sqlite3")
    policies_database: Path = Path("runtime/policies.sqlite3")
    sessions_database: Path = Path("runtime/sessions.sqlite3")
    ollama_url: str = "http://127.0.0.1:11434"
    model: str = "qwen3:8b"
    demo_customer_id: int | None = None

    def __post_init__(self):
        validate_local_url(self.ollama_url)
        paths = [self.database, self.policies_database, self.sessions_database]
        if len({path.resolve() for path in paths}) != 3:
            raise ValueError("Catálogo, políticas e sessões precisam de bancos separados.")
        if self.demo_customer_id is not None and (type(self.demo_customer_id) is not int or self.demo_customer_id <= 0):
            raise ValueError("Identidade simulada inválida.")

    @classmethod
    def from_env(cls):
        load_dotenv(override=False)
        customer = os.getenv("EMPORIO_DEMO_CUSTOMER_ID", "").strip()
        return cls(
            database=Path(os.getenv("EMPORIO_DATABASE", "runtime/emporio.sqlite3")),
            policies_database=Path(os.getenv("EMPORIO_POLICIES_DATABASE", "runtime/policies.sqlite3")),
            sessions_database=Path(os.getenv("EMPORIO_SESSIONS_DATABASE", "runtime/sessions.sqlite3")),
            ollama_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            model=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
            demo_customer_id=int(customer) if customer else None,
        )
