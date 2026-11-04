# Architecture and design rationale

I separated natural-language interpretation from operations that require exact results. The model chooses tools and drafts answers; Python controls access, validates inputs, calculates money, and applies explicit business safeguards.

## Request flow

```text
Chat / Swagger / HTTP client
  -> FastAPI validation and conversation token
  -> bounded history and server-controlled customer context
  -> preventive policy retrieval when relevant
  -> local Ollama tool selection
  -> closed Pydantic tool registry
     -> read-only catalogue and authorized order queries
     -> integer monetary calculations
     -> FTS5 policy retrieval with section/page provenance
  -> final natural-language answer
  -> evidence checks and identified business safeguards
  -> answer, sources, trace, model and prompt metadata
```

I chose FastAPI for validation and OpenAPI, with a small same-origin browser chat. The agent service can also run without HTTP, as it does in the evaluation script. I did not need a separate orchestration framework for five tools and a bounded loop.

## Storage and tools

I use three SQLite databases: catalogue, policy index, and conversations. This keeps catalogue imports from deleting history or policies. The received CSVs contain 191 operational records, so a transactional snapshot import and small local queries fit the problem.

I expose `search_products`, `get_product`, `quote_payment`, `search_policies`, and `get_order_status`. Pydantic rejects extra arguments and invalid types. The server resolves categories from the catalogue and supplies customer identity independently of model arguments. Query connections are read-only, SQL is parameterized, and returned fields are explicit. No tool accepts arbitrary SQL, lists customers, or changes orders.

I parse monetary inputs with `Decimal`, then calculate in integer cents and basis points. This avoids floating-point discrepancies and keeps installment totals exact. I preserve historical order totals rather than applying today's catalogue prices retroactively.

## Retrieval and inference

I chose FTS5/BM25 because the manual has eight pages. The index has 29 section-based chunks with original page numbers and a document hash. Controlled term expansion and related sections improve context without rewriting policies. Lexical retrieval remains vulnerable to unfamiliar phrasing; I would benchmark embeddings before adding them.

I run Qwen3 8B through Ollama on loopback, with cloud features disabled and no paid fallback. The provider ignores proxy configuration and rejects remote endpoints. A fixed seed and temperature zero support repeatability, not cross-hardware determinism.

## Evidence and safeguards

I keep prompt instructions separate from user and retrieved content. The server attaches actual sources and rejects unknown references. Preventive retrieval and deterministic business rules have explicit trace markers, so they are distinguishable from model-selected tool calls.

Safeguards cover known issues such as status/stock availability, PIX and promotion consistency, promotion disclosure, missing return context, warranty timing, historical delivery estimates, and ambiguous shipping thresholds. They do not prove every sentence is correct. I therefore separate domain tests from real-model evaluation and discuss imperfect outputs openly.

## Sessions and operational boundaries

I store only hashes of random conversation tokens. Sessions expire after 24 hours and can be deleted. A transactional lease prevents simultaneous writes within one conversation; an inference semaphore protects the local model. Logs contain operational metadata rather than full messages or session tokens.

A conversation token does not authenticate a store customer. Order access is blocked unless the server supplies a trusted context. The optional fixed demo identity is explicitly simulated. Production authentication, deployment, external commerce integrations, and scalable inference are outside this submission.
