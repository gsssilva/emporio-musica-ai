import csv
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from test_agent import ScriptedProvider, final
from test_ingestion import sample_rows

from emporio_ai.api import create_app
from emporio_ai.provider import ProviderUnavailable
from emporio_ai.sessions import SessionStore
from emporio_ai.source_data import SCHEMAS
from emporio_ai.storage import ingest


class FakeAgent:
    provider = ScriptedProvider([])

    def __init__(self):
        self.received = []
        self.failure = False

    def respond(self, message, *, history, customer_id):
        self.received.append((message, history, customer_id))
        if self.failure:
            raise ProviderUnavailable("Modelo local indisponível.")
        return {"answer": "Como posso ajudar?", "kind": "greeting", "sources": [],
                "provider": "test-double", "status": "completed"}


class ChatApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for table, rows in sample_rows().items():
            with (self.root / f"desafio_tecnico_ai_eng - {table}.csv").open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(SCHEMAS[table].split())
                writer.writerows(rows)
        database = self.root / "catalog.sqlite3"
        ingest(self.root, database)
        self.agent = FakeAgent()
        self.store = SessionStore(self.root / "sessions.sqlite3")
        self.client = TestClient(create_app(database, agent=self.agent, sessions=self.store))
        self.addCleanup(self.client.close)

    def headers(self):
        response = self.client.post("/sessions")
        self.assertEqual(response.status_code, 201)
        return {"Authorization": "Bearer " + response.json()["session_id"]}

    def test_conversation_flow_and_isolation(self):
        first, second = self.headers(), self.headers()
        self.assertEqual(self.client.post("/chat", json={"message": "oi"}, headers=first).status_code, 200)
        self.client.post("/chat", json={"message": "continuação"}, headers=first)
        self.assertEqual(self.agent.received[-1][1][0]["content"], "oi")
        self.client.post("/chat", json={"message": "outra conversa"}, headers=second)
        self.assertEqual(self.agent.received[-1][1], [])
        self.assertIsNone(self.agent.received[-1][2])

    def test_authorization_required_unknown_token_rejected(self):
        self.assertIn(self.client.post("/chat", json={"message": "oi"}).status_code, [401, 403])
        response = self.client.post("/chat", json={"message": "oi"}, headers={"Authorization": "Bearer guessed"})
        self.assertEqual(response.status_code, 401)

    def test_identity_and_history_cannot_be_set_by_client(self):
        self.assertEqual(self.client.post("/sessions", json={"customer_id": 1}).status_code, 422)
        headers = self.headers()
        for payload in [{"message": "oi", "customer_id": 1}, {"message": "oi", "history": []}, {"message": " "}, {"message": "x" * 2001}]:
            self.assertEqual(self.client.post("/chat", json=payload, headers=headers).status_code, 422)

    def test_delete_session_prevents_reuse(self):
        headers = self.headers()
        self.client.post("/chat", json={"message": "oi"}, headers=headers)
        self.assertEqual(self.client.delete("/sessions/current", headers=headers).status_code, 204)
        self.assertEqual(self.client.post("/chat", json={"message": "oi"}, headers=headers).status_code, 401)

    def test_provider_failure_does_not_persist_failed_turn_or_leave_lock(self):
        headers = self.headers()
        self.agent.failure = True
        self.assertEqual(self.client.post("/chat", json={"message": "erro"}, headers=headers).status_code, 503)
        self.agent.failure = False
        self.assertEqual(self.client.post("/chat", json={"message": "oi"}, headers=headers).status_code, 200)
        self.assertEqual(self.agent.received[-1][1], [])

    def test_openapi_documents_chat_authorization(self):
        schema = self.client.get("/openapi.json").json()
        self.assertIn("/chat", schema["paths"])
        self.assertTrue(schema["paths"]["/chat"]["post"]["security"])


if __name__ == "__main__":
    unittest.main()
