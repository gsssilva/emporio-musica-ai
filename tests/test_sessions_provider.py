import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from emporio_ai.provider import OllamaProvider, ProviderUnavailable
from emporio_ai.sessions import SessionBusy, SessionExpired, SessionLimit, SessionStore
from emporio_ai.settings import Settings


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = [1000.0]
        self.database = Path(self.temp.name) / "sessions.sqlite3"
        self.store = SessionStore(self.database, ttl_seconds=10, max_turns=2, clock=lambda: self.now[0])

    def test_tokens_are_random_and_stored_as_hashes(self):
        first, second = self.store.create()["session_id"], self.store.create()["session_id"]
        self.assertNotEqual(first, second)
        self.assertNotIn(first.encode(), self.database.read_bytes())

    def test_history_and_identity_are_isolated(self):
        first, second = self.store.create(customer_id=1)["session_id"], self.store.create()["session_id"]
        with self.store.claim(first) as session:
            self.assertEqual(session.customer_id, 1)
            self.store.append(session, "pergunta privada", "resposta")
        with self.store.claim(second) as session:
            self.assertIsNone(session.customer_id)
            self.assertEqual(session.history, [])
        with self.store.claim(first) as session:
            self.assertEqual(session.history[0]["content"], "pergunta privada")

    def test_expiration_invalid_token_and_turn_limit(self):
        token = self.store.create()["session_id"]
        for _ in range(2):
            with self.store.claim(token) as session:
                self.store.append(session, "oi", "olá")
        with self.assertRaises(SessionLimit):
            with self.store.claim(token):
                pass
        self.now[0] += 11
        for invalid in [token, "guessed-session"]:
            with self.assertRaises(SessionExpired):
                with self.store.claim(invalid):
                    pass

    def test_concurrent_turn_is_rejected_and_lease_is_released_after_failure(self):
        token = self.store.create()["session_id"]
        with self.store.claim(token):
            with self.assertRaises(SessionBusy):
                with self.store.claim(token):
                    pass
            with self.assertRaises(SessionBusy):
                self.store.delete(token)
        with self.assertRaisesRegex(RuntimeError, "test"):
            with self.store.claim(token):
                raise RuntimeError("test")
        with self.store.claim(token) as session:
            self.assertEqual(session.history, [])

    def test_delete_removes_history_and_rejects_reuse(self):
        token = self.store.create()["session_id"]
        with self.store.claim(token) as session:
            self.store.append(session, "oi", "olá")
        self.store.delete(token)
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM turns").fetchone()[0], 0)
        with self.assertRaises(SessionExpired):
            with self.store.claim(token):
                pass

    def test_capacity_and_unrecognized_database(self):
        store = SessionStore(self.database, max_sessions=1)
        store.create()
        with self.assertRaises(SessionLimit):
            store.create()
        unrelated = Path(self.temp.name) / "unrelated.sqlite3"
        with closing(sqlite3.connect(unrelated)) as connection:
            connection.execute("CREATE TABLE unrelated(data TEXT)")
            connection.commit()
        with self.assertRaises(ValueError):
            SessionStore(unrelated)


class ProviderTests(unittest.TestCase):
    def test_only_local_endpoints_and_models_are_accepted(self):
        for url in ["https://api.openai.com", "http://example.com", "http://127.0.0.1/remote", "http://user:pass@localhost:11434"]:
            with self.assertRaises(ValueError):
                OllamaProvider(url)
        with self.assertRaises(ValueError):
            OllamaProvider(model="paid:cloud")
        with self.assertRaises(ValueError):
            Settings(database=Path("same"), policies_database=Path("same"))

    def test_local_request_uses_no_proxy_no_cloud_key_and_bounded_output(self):
        response = httpx.Response(200, json={"done": True, "message": {"role": "assistant", "content": "olá"}}, request=httpx.Request("POST", "http://127.0.0.1:11434/api/chat"))
        client = MagicMock()
        client.__enter__.return_value = client
        client.post.return_value = response
        with patch("emporio_ai.provider.httpx.Client", return_value=client) as constructor:
            result = OllamaProvider().chat([{"role": "user", "content": "oi"}])
        self.assertFalse(constructor.call_args.kwargs["trust_env"])
        payload = client.post.call_args.kwargs["json"]
        self.assertFalse(payload["stream"])
        self.assertFalse(payload["think"])
        self.assertNotIn("api_key", payload)
        self.assertEqual(result["message"]["content"], "olá")

    def test_provider_errors_are_controlled(self):
        client = MagicMock()
        client.__enter__.return_value = client
        client.post.side_effect = httpx.ConnectError("private diagnostic")
        with patch("emporio_ai.provider.httpx.Client", return_value=client):
            with self.assertRaises(ProviderUnavailable) as caught:
                OllamaProvider().chat([])
        self.assertNotIn("private diagnostic", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
