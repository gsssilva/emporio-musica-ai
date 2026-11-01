"""Run the actual local LLM; never substitutes a scripted provider on failure."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from emporio_ai.agent import CustomerAgent, PROMPT_VERSION
from emporio_ai.policies import PolicySearch, normalize
from emporio_ai.provider import OllamaProvider, ProviderUnavailable
from emporio_ai.queries import StoreQueries
from emporio_ai.settings import Settings
from emporio_ai.tools import ToolRegistry

EXAMPLES = {"catalogue": "01-catalogo.md", "pix_promotion": "02-promocao-pix.md",
            "regret": "03-devolucao.md", "order_authorized": "04-pedido-demo.md",
            "out_of_scope": "05-fora-de-escopo.md"}


def check_result(case: dict, result: dict, store: StoreQueries) -> dict[str, bool]:
    sources = {source["id"] for source in result.get("sources", [])}
    successful_tools = {tool["tool"] for tool in result.get("tool_trace", []) if tool["ok"]}
    answer = normalize(result.get("answer", ""))
    checks = {"completed": result.get("status") == "completed",
              "kind": result.get("kind") in case["kinds"]}
    if case.get("tools_any"):
        # An authorization refusal is successful enforcement even when the tool returns ok=false.
        actual = {tool["tool"] for tool in result.get("tool_trace", [])} if case["id"] == "order_unauthorized" else successful_tools
        checks["tool_selection"] = bool(actual.intersection(case["tools_any"]))
    if case.get("source_ids"):
        checks["expected_sources"] = set(case["source_ids"]).issubset(sources)
    if case.get("forbid_order_sources"):
        checks["no_private_order_sources"] = not any(source.startswith("order:") for source in sources)
    if case.get("source_prefix"):
        checks["source_type"] = any(source.startswith(case["source_prefix"]) for source in sources)
    if case.get("terms_any"):
        checks["expected_content_signal"] = any(normalize(term) in answer for term in case["terms_any"])
    if case.get("required_terms"):
        checks["required_content_signals"] = all(normalize(term) in answer for term in case["required_terms"])
    if case.get("forbidden"):
        checks["forbidden_content_absent"] = not any(normalize(term) in answer for term in case["forbidden"])
    if case.get("quote_product_id"):
        quote = store.quote_product(case["quote_product_id"], method="pix")["quote"]
        cents = quote["total_cents"]
        expected = f"{cents // 100:,}".replace(",", ".") + f",{cents % 100:02d}"
        checks["calculated_total_present"] = expected in result["answer"]
    return checks


def revision() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path("evals/cases.json"))
    parser.add_argument("--output", type=Path, default=Path("runtime/evaluation.json"))
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--examples", type=Path)
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if args.only:
        cases = [case for case in cases if case["id"] in args.only]
    if not cases:
        parser.error("Nenhum cenário selecionado.")
    if args.examples and not set(EXAMPLES).issubset({case["id"] for case in cases}):
        parser.error("Para gerar os cinco exemplos, selecione todos os cenários correspondentes.")
    config = Settings.from_env()
    provider = OllamaProvider(config.ollama_url, config.model)
    if not provider.ready():
        parser.error("Ollama/modelo local não está disponível. Nenhum resultado simulado será gerado.")
    store = StoreQueries(config.database)
    reference_time = datetime.now(ZoneInfo("America/Campo_Grande"))
    agent = CustomerAgent(provider, ToolRegistry(store, PolicySearch(config.policies_database)), clock=lambda: reference_time)
    with httpx.Client(timeout=5, trust_env=False) as client:
        tags = client.get(provider.base_url + "/api/tags").json()
        version = client.get(provider.base_url + "/api/version").json()
    model_info = next(model for model in tags["models"] if model["name"] == provider.model)
    report = {"provider": "ollama", "model": provider.model, "model_digest": model_info["digest"],
              "ollama_version": version["version"], "prompt_version": PROMPT_VERSION,
              "decoding_options": provider.options, "reference_time": reference_time.isoformat(),
              "source_revision": revision(), "started_at": datetime.now(timezone.utc).isoformat(),
              "evaluation_type": "real_local_llm", "paid_api_calls": 0,
              "limitations": "Verificações automáticas de protocolo, fontes e sinais textuais; não substituem revisão semântica humana.",
              "cases": []}
    for case in cases:
        started = time.monotonic()
        try:
            result = agent.respond(case["message"], customer_id=case.get("customer_id"))
            checks = check_result(case, result, store)
        except ProviderUnavailable as error:
            result = {"answer": str(error), "status": "provider_error", "sources": [], "tool_trace": []}
            checks = {"provider_available": False}
        record = {"id": case["id"], "message": case["message"],
                  "simulated_customer_id": case.get("customer_id"), "result": result,
                  "seconds": round(time.monotonic() - started, 2), "checks": checks,
                  "passed_automatic_checks": all(checks.values())}
        report["cases"].append(record)
        print(case["id"], "PASS" if record["passed_automatic_checks"] else "REVIEW", record["seconds"], checks, flush=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    passed = sum(record["passed_automatic_checks"] for record in report["cases"])
    report["summary"] = {"cases": len(cases), "passed_automatic_checks": passed,
                         "requires_review": len(cases) - passed}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.examples:
        args.examples.mkdir(parents=True, exist_ok=True)
        for record in report["cases"]:
            if record["id"] not in EXAMPLES:
                continue
            result = record["result"]
            lines = ["# Conversa executada com o agente local", "", "Modelo: `" + provider.model + "`.",
                     "Prompt: `" + PROMPT_VERSION + "`. Tipo: LLM real local, sem chamada paga.",
                     "Identidade: " + ("cliente fictício simulado no servidor para esta demonstração." if record["simulated_customer_id"] else "sem autenticação de cliente."),
                     "", "**Cliente:** " + record["message"], "", "**Assistente:** " + result["answer"], "", "Fontes consultadas:", ""]
            lines += ["- `" + source["id"] + "`: " + source.get("title", "")
                      + ("; páginas " + ", ".join(map(str, source["pages"])) if source.get("pages") else "") for source in result.get("sources", [])]
            if not result.get("sources"):
                lines.append("- Nenhuma fonte factual necessária para esta resposta, ou consulta não concluída; conferir status abaixo.")
            lines += ["", "Ferramentas: " + ", ".join(tool["tool"] for tool in result.get("tool_trace", [])),
                      "Status: `" + result["status"] + "`. Verificações automáticas: " + ("aprovadas" if record["passed_automatic_checks"] else "revisão necessária") + ".", ""]
            (args.examples / EXAMPLES[record["id"]]).write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False), flush=True)
    return int(passed != len(cases))


if __name__ == "__main__":
    raise SystemExit(main())
