# Evaluation and limitations

I distinguish three kinds of evidence: deterministic tests, recorded conversations with the real local model, and semantic inspection of those answers. A provider test double checks protocol behavior; it does not measure LLM quality. Source and keyword checks alone do not establish complete semantic correctness.

## Deterministic checks

The current Python suite has 93 tests covering ingestion and rollback, money, status/stock, promotions, order authorization, retrieval, sessions, HTTP behavior, assets, limits, provider failures, and safeguards. Ten JavaScript tests check client behavior with DOM and HTTP doubles. The latest local execution passed both suites. Tests use synthetic CSVs and temporary databases; policy tests also use the supplied manual.

The framework emits a test-client deprecation warning. It does not fail the suite, but I would update that integration when adopting a newer dependency set.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
node --test tests/test_chat_ui.cjs
.\.venv\Scripts\python.exe scripts/evaluate_agent.py --output runtime/evaluation.json
```

## Recorded real-model run

I retain `evals/results.json` as the original evaluation record. It contains 13 scenarios executed with real local Ollama, without substituting scripted answers on failure. The evaluator records full messages, sources, trace, checks, timings, and generation modes. It calls the agent service directly; HTTP integration is tested separately.

The recorded environment was Windows, 16 GB RAM, RTX 4060 8 GB, Ollama 0.40.13, and `qwen3:8b`. Settings were temperature zero, seed 42, an 8,192-token context, and a 1,200-token output limit. Model digest:

```text
500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41
```

The run began at `2026-11-01T20:55:51.208910+00:00`, at source revision `986e4e63339539b80168e2d969af94bfc48eee27`. The JSON records a fixed reference clock and prompt version. All 13 scenarios passed their specified automatic checks. Among the 12 responses that used inference, median latency was 5.72 seconds, with a 2.69-14.31-second range. The authorization block occurred before inference and is excluded from that estimate. This was not a separate cold-start benchmark.

I do not describe this historical run as a new measurement of subsequent regression fixes or interface changes. Nor do I equate 13 passing scenarios with universal accuracy. Hardware, model/runtime versions, context, and source changes can affect results.

| Scenario | Main check |
| --- | --- |
| Guitars under R$ 1,000 | Category, budget, availability, and sources |
| Takamine GD20 | Retrieved price and product detail |
| Product 96 | Out of stock, with real alternatives |
| Product 136 | Discontinued despite positive stock |
| Product 90 with PIX | R$ 1,967.18; no extra 5% on promotion |
| Address and Saturday hours | Institutional policy evidence |
| Return after changing one's mind | Ask for channel and actual receipt |
| Authorized order 8 | Simulated identity and historical estimate |
| Order without identity | Server block before inference |
| Defect after 35 days | Warranty context and actual receipt anchor |
| Napoleon question | Refuse general-topic answering |
| Customer/SQL injection | No customer listing or arbitrary SQL |
| Shipping at exactly R$ 500 | Acknowledge an undefined boundary |

## What answer inspection revealed

I use answer inspection to look beyond passing checks. In development, a correct PIX total was accompanied by an incorrect explanation of stacked discounts. A return answer also assumed missing eligibility context. Explicit safeguards now derive the PIX explanation from the quote and request purchase channel and actual receipt. Warranty checks require the receipt anchor rather than merely mentioning 90 days.

Later review identified two further gaps: promotional communication needed original price and percentage as well as the final price, and complaint paraphrases needed better retrieval of section 7.3. Regression tests cover the resulting changes. These fixes apply to retrieved facts and policy sections rather than memorizing particular example IDs.

I preserve imperfections in the historical transcripts. The order example states that the item was shipped on a date even though the snapshot's order date does not prove a shipment date. The out-of-scope example unnecessarily offers an external history reference. The original promotion example omits the original price and percentage. Automatic checks did not establish these details, so I explicitly flag them rather than polishing the transcripts into false evidence.

The five English examples are translations for the submission, not claims that the model produced those English messages. The original Portuguese answers remain in the versioned JSON. The order example uses a fixed fictional identity, not real authentication.

## Limits and next steps

Lexical retrieval can miss unfamiliar paraphrases. The model can omit conditions, overstate data, or add an ungrounded suggestion. Source provenance is necessary but insufficient to prove every claim. Alternatives are same-category suggestions, not verified technical equivalents.

The supplied orders lack purchase channel and actual receipt dates. The data are snapshots, with no live carrier or ERP update. Ambiguous contacts, small installments, and the exact shipping threshold need business clarification. I do not approve returns or deny rights automatically.

I would prioritize unseen paraphrases, multi-turn cases, claim-level review, and labelled retrieval recall, followed by comparison with embedding retrieval. Before a hosted release, I would add real authentication, concurrency/cold-start measurements, operational monitoring, and broader browser accessibility checks.

No paid inference calls or hosting service were used for the recorded evaluation. Download, storage, hardware, and electricity are still required.
