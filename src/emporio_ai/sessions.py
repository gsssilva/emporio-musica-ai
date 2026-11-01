"""Expiring capability sessions, with transactional leases for concurrent turns."""

from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3
import time
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path


class SessionExpired(PermissionError):
    pass


class SessionBusy(RuntimeError):
    pass


class SessionLimit(RuntimeError):
    pass


@dataclass(frozen=True)
class SessionTurn:
    token_hash: str
    lease_id: str
    customer_id: int | None
    history: list[dict]


class SessionStore:
    def __init__(self, database: Path, *, ttl_seconds: int = 86400, max_turns: int = 20,
                 max_sessions: int = 500, clock=time.time):
        self.database, self.ttl_seconds, self.max_turns = database, ttl_seconds, max_turns
        self.max_sessions, self.clock = max_sessions, clock
        database.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            if tables and tables != {"sessions", "turns"}:
                raise ValueError("Banco de sessões não reconhecido; use um caminho dedicado.")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS sessions(
                    token_hash TEXT PRIMARY KEY,customer_id INTEGER,expires_at REAL NOT NULL,
                    busy_until REAL NOT NULL DEFAULT 0,lease_id TEXT);
                CREATE TABLE IF NOT EXISTS turns(
                    id INTEGER PRIMARY KEY,session_hash TEXT NOT NULL REFERENCES sessions(token_hash) ON DELETE CASCADE,
                    user_text TEXT NOT NULL,assistant_text TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS turns_session ON turns(session_hash,id);
            """)

    def _connect(self):
        connection = sqlite3.connect(self.database, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _hash(token: str) -> str:
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise SessionExpired("Sessão inválida ou expirada.")
        return hashlib.sha256(token.encode()).hexdigest()

    def create(self, customer_id: int | None = None) -> dict:
        if customer_id is not None and (type(customer_id) is not int or customer_id <= 0):
            raise ValueError("Identidade simulada inválida.")
        token, now = secrets.token_urlsafe(32), self.clock()
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM sessions WHERE expires_at<=?", (now,))
            if connection.execute("SELECT count(*) FROM sessions").fetchone()[0] >= self.max_sessions:
                raise SessionLimit("Limite de sessões locais atingido.")
            connection.execute("INSERT INTO sessions(token_hash,customer_id,expires_at) VALUES (?,?,?)",
                               (self._hash(token), customer_id, now + self.ttl_seconds))
        return {"session_id": token, "expires_in_seconds": self.ttl_seconds,
                "demo_identity": customer_id is not None}

    @contextmanager
    def claim(self, token: str):
        token_hash, now, lease = self._hash(token), self.clock(), secrets.token_hex(16)
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM sessions WHERE token_hash=? AND expires_at>?", (token_hash, now)).fetchone()
            if row is None:
                raise SessionExpired("Sessão inválida ou expirada.")
            if row["busy_until"] > now:
                raise SessionBusy("Esta sessão já possui uma resposta em processamento.")
            if connection.execute("SELECT count(*) FROM turns WHERE session_hash=?", (token_hash,)).fetchone()[0] >= self.max_turns:
                raise SessionLimit("Limite de mensagens atingido. Crie uma nova sessão.")
            connection.execute("UPDATE sessions SET busy_until=?,lease_id=? WHERE token_hash=?", (now + 300, lease, token_hash))
            rows = connection.execute("SELECT user_text,assistant_text FROM turns WHERE session_hash=? ORDER BY id DESC LIMIT 3", (token_hash,)).fetchall()
            history = []
            for turn in reversed(rows):
                history.extend([{"role": "user", "content": turn["user_text"]},
                                {"role": "assistant", "content": turn["assistant_text"]}])
            session = SessionTurn(token_hash, lease, row["customer_id"], history)
        try:
            yield session
        finally:
            with closing(self._connect()) as connection, connection:
                connection.execute("UPDATE sessions SET busy_until=0,lease_id=NULL WHERE token_hash=? AND lease_id=?", (token_hash, lease))

    def append(self, session: SessionTurn, user: str, answer: str):
        with closing(self._connect()) as connection, connection:
            row = connection.execute("SELECT 1 FROM sessions WHERE token_hash=? AND lease_id=? AND expires_at>?",
                                     (session.token_hash, session.lease_id, self.clock())).fetchone()
            if row is None:
                raise SessionExpired("Sessão inválida ou expirada.")
            connection.execute("INSERT INTO turns(session_hash,user_text,assistant_text) VALUES (?,?,?)", (session.token_hash, user, answer))

    def delete(self, token: str):
        token_hash = self._hash(token)
        with closing(self._connect()) as connection, connection:
            row = connection.execute("SELECT busy_until FROM sessions WHERE token_hash=?", (token_hash,)).fetchone()
            if row is None:
                raise SessionExpired("Sessão inválida ou expirada.")
            if row["busy_until"] > self.clock():
                raise SessionBusy("Aguarde a resposta em processamento antes de excluir a sessão.")
            connection.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))
