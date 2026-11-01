"""Local commands. No provider credentials or network connection are required."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from emporio_ai.source_data import DataValidationError, load_snapshot
from emporio_ai.storage import ingest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="emporio-ai")
    subparsers = parser.add_subparsers(dest="command", required=True)
    ingest_parser = subparsers.add_parser("ingest", help="Validar CSVs e atualizar a base local")
    ingest_parser.add_argument("--data-dir", type=Path, default=Path("data"))
    ingest_parser.add_argument("--database", type=Path, default=Path("runtime/emporio.sqlite3"))
    check_parser = subparsers.add_parser("check-data", help="Validar CSVs sem criar um banco")
    check_parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args(argv)
    try:
        if args.command == "ingest":
            result = ingest(args.data_dir, args.database)
        else:
            snapshot = load_snapshot(args.data_dir)
            result = {"row_counts": snapshot.row_counts, "source_manifest": snapshot.manifest}
    except DataValidationError as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError):
        print(json.dumps({"error": "Falha de acesso ao banco ou ao diretório de destino."},
                         ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
