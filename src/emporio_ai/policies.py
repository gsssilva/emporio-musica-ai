"""Section-aware lexical retrieval with page-level provenance."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from pypdf import PdfReader

STOPWORDS = set("a o as os de da do das dos em no na nos nas um uma e ou que qual quais como para por com se eu me meu minha posso tem sobre voce voces sao ao ate ja foi mais uma quero saber loja musica emporio todos todas produto produtos".split())
EXPANSIONS = {
    "errado": "reclamacao", "errada": "reclamacao",
    "insatisfeito": "reclamacao", "insatisfeita": "reclamacao",
    "reclamar": "reclamacao", "reclamacoes": "reclamacao",
    "clientes": "privacidade", "emails": "email mail", "telefones": "telefone",
    "devolver": "devolucoes arrependimento", "devolucao": "devolucoes arrependimento",
    "devolucoes": "arrependimento", "arrependi": "arrependimento",
    "trocar": "trocas preferencia", "troca": "trocas", "quebrou": "defeito garantia",
    "defeito": "garantia fabricacao", "garantia": "defeito fabricante",
    "abre": "horario funcionamento", "aberto": "horario funcionamento",
    "funciona": "horario funcionamento", "horarios": "horario funcionamento",
    "localizacao": "endereco", "contato": "telefone whatsapp endereco",
    "parcelar": "parcelamento pagamento", "parcelas": "parcelamento pagamento",
    "pagar": "pagamento", "desconto": "promocoes cumulatividade",
    "acessorios": "cordas cabos palhetas escopo", "dados": "privacidade protecao",
}
RELATED = {
    "4.1": ["4.4"], "4.2": ["8.1", "8.2", "8.3"],
    "4.3": ["4.4"], "4.4": ["4.1"], "8.1": ["4.2"],
    "8.2": ["8.1", "4.2"], "8.3": ["8.1", "4.2"],
    "3": ["3.1", "6.2"], "3.1": ["3", "6.2"], "6.2": ["3.1"],
    "7.3": ["7.2", "7"],
    "1.2": ["cover", "7"], "7": ["1.2", "cover"],
}


def normalize(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold())
                   if not unicodedata.combining(c))


def parse_sections(pages: list[str]) -> list[dict]:
    chunks, current = [], None
    heading = re.compile(r"^(\d{1,2}(?:\.\d{1,2})?)\.?\s+(.+)$")
    for page_number, text in enumerate(pages, 1):
        if page_number == 1:
            chunks.append({"section": "cover", "title": "Capa e contatos institucionais",
                           "pages": [1], "text": "\n".join(line.strip() for line in text.splitlines() if line.strip())})
            continue
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith(("Empório da Música Manual", "Página ", "Última atualização:", "Empório da Música —")):
                continue
            match = heading.match(line) if raw_line and not raw_line[0].isspace() else None
            if match:
                current = {"section": match[1], "title": match[2], "pages": [], "text": ""}
                chunks.append(current)
            if current is not None:
                if page_number not in current["pages"]:
                    current["pages"].append(page_number)
                current["text"] += line + "\n"
    if len(chunks) < 2 or len({chunk["section"] for chunk in chunks}) != len(chunks):
        raise ValueError("Não foi possível extrair seções únicas do manual; revise o PDF.")
    return chunks


def index_policies(pdf: Path, database: Path) -> dict:
    raw = pdf.read_bytes()
    if len(raw) > 25_000_000:
        raise ValueError("Manual excede o limite de 25 MB.")
    reader = PdfReader(pdf)
    if len(reader.pages) > 64:
        raise ValueError("Manual excede o limite de 64 páginas.")
    chunks = parse_sections([page.extract_text(extraction_mode="layout") or "" for page in reader.pages])
    digest = hashlib.sha256(raw).hexdigest()
    database.parent.mkdir(parents=True, exist_ok=True)
    temporary = database.with_name(database.name + "." + uuid4().hex + ".tmp")
    try:
        with closing(sqlite3.connect(temporary)) as connection:
            connection.executescript("""
                CREATE TABLE metadata(document TEXT NOT NULL,sha256 TEXT NOT NULL,index_version INTEGER NOT NULL);
                CREATE TABLE chunks(id INTEGER PRIMARY KEY,section TEXT UNIQUE NOT NULL,title TEXT NOT NULL,pages TEXT NOT NULL,text TEXT NOT NULL);
                CREATE VIRTUAL TABLE chunks_fts USING fts5(title,text,tokenize='unicode61 remove_diacritics 2');
            """)
            with connection:
                connection.execute("INSERT INTO metadata VALUES (?,?,1)", (pdf.name, digest))
                for index, chunk in enumerate(chunks, 1):
                    connection.execute("INSERT INTO chunks VALUES (?,?,?,?,?)",
                                       (index, chunk["section"], chunk["title"], json.dumps(chunk["pages"]), chunk["text"].strip()))
                    connection.execute("INSERT INTO chunks_fts(rowid,title,text) VALUES (?,?,?)",
                                       (index, normalize(chunk["title"]), normalize(chunk["text"])))
        temporary.replace(database)
    finally:
        temporary.unlink(missing_ok=True)
    return {"document": pdf.name, "sha256": digest, "sections": len(chunks), "pages": len(reader.pages)}


class PolicySearch:
    def __init__(self, database: Path):
        self.database = database.resolve()

    def search(self, query: str, limit: int = 3) -> dict:
        if not isinstance(query, str) or not query.strip() or len(query) > 500:
            raise ValueError("Consulta de políticas deve ter entre 1 e 500 caracteres.")
        if type(limit) is not int or not 1 <= limit <= 5:
            raise ValueError("Limite de políticas deve estar entre 1 e 5.")
        terms = [word for word in re.findall(r"[a-z0-9]+", normalize(query)) if word not in STOPWORDS]
        expanded = set(terms)
        for word in terms:
            expanded.update(EXPANSIONS.get(word, "").split())
        if not expanded:
            return {"sources": [], "matched": False}
        expression = " OR ".join('"' + term + '"' for term in sorted(expanded))
        with closing(sqlite3.connect(self.database.as_uri() + "?mode=ro", uri=True)) as connection:
            connection.row_factory = sqlite3.Row
            primary = connection.execute("""SELECT c.* FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.rowid
                WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts,8.0,1.0),c.id LIMIT ?""", (expression, limit)).fetchall()
            rows = list(primary)
            seen = {row["section"] for row in rows}
            for row in primary:
                for section in RELATED.get(row["section"], []):
                    if section not in seen and len(rows) < 10:
                        related = connection.execute("SELECT * FROM chunks WHERE section=?", (section,)).fetchone()
                        if related:
                            rows.append(related)
                            seen.add(section)
            metadata = connection.execute("SELECT * FROM metadata").fetchone()
            sources = [{"id": "policy:" + row["section"], "kind": "policy", "section": row["section"],
                        "title": row["title"], "pages": json.loads(row["pages"]), "text": row["text"],
                        "document": metadata["document"], "sha256": metadata["sha256"]} for row in rows]
            return {"sources": sources, "matched": bool(sources)}
