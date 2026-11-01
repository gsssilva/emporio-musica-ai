from contextlib import closing

import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from emporio_ai.policies import PolicySearch, index_policies, parse_sections

PDF = Path(__file__).resolve().parents[1] / "data" / "políticas_da_loja.pdf"


class PolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.database = Path(cls.temp.name) / "policies.sqlite3"
        cls.report = index_policies(PDF, cls.database)
        cls.search = PolicySearch(cls.database)

    def test_source_provenance_and_sections(self):
        self.assertEqual(self.report["sections"], 29)
        self.assertEqual(self.report["pages"], 8)
        self.assertEqual(self.report["sha256"], hashlib.sha256(PDF.read_bytes()).hexdigest())

    def test_section_continues_across_pages(self):
        sources = self.search.search("entregas outras cidades PAC SEDEX")["sources"]
        section = next(source for source in sources if source["section"] == "5.2")
        self.assertEqual(section["pages"], [4, 5])
        self.assertIn("Jadlog", section["text"])

    def test_numbered_procedure_is_not_a_new_section(self):
        with closing(sqlite3.connect(self.database)) as connection:
            row = connection.execute("SELECT text,pages FROM chunks WHERE section='7.2'").fetchone()
        self.assertIn("5.", row[0])
        self.assertEqual(row[1], "[6, 7]")

    def test_returns_related_exceptions_for_regret(self):
        ids = {source["section"] for source in self.search.search("me arrependi quero devolver")["sources"]}
        self.assertIn("4.1", ids)
        self.assertIn("4.4", ids)

    def test_defects_retrieve_warranty_and_procedure(self):
        ids = {source["section"] for source in self.search.search("defeito garantia")["sources"]}
        self.assertIn("4.2", ids)
        self.assertIn("8.1", ids)

    def test_contacts_preserve_conflicting_sources(self):
        ids = {source["section"] for source in self.search.search("endereco telefone contato")["sources"]}
        self.assertTrue({"1.2", "7", "cover"}.issubset(ids))

    def test_installments_retrieve_specific_rules(self):
        ids = {source["section"] for source in self.search.search("parcelar pagamento pix")["sources"]}
        self.assertIn("3.1", ids)
        self.assertIn("6.2", ids)

    def test_hours_and_unsupported_question(self):
        sources = self.search.search("que horas abre sabado")["sources"]
        self.assertIn("2", {source["section"] for source in sources})
        self.assertFalse(self.search.search("fotossintese planetas quasar")["matched"])

    def test_query_is_not_fts_syntax(self):
        self.assertIsInstance(self.search.search('" OR *); DROP TABLE chunks; --')["sources"], list)
        self.assertTrue(self.search.search("horario")["matched"])

    def test_invalid_inputs_and_absent_text(self):
        for query in ["", "a" * 501]:
            with self.assertRaises(ValueError):
                self.search.search(query)
        with self.assertRaises(ValueError):
            self.search.search("horario", limit=100)
        with self.assertRaises(ValueError):
            parse_sections(["capa", "nenhum título reconhecido"])

    def test_rebuild_does_not_duplicate_sections(self):
        index_policies(PDF, self.database)
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM chunks").fetchone()[0], 29)
