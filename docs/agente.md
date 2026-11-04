# Agent, sessions, and privacy

I use local Qwen3 8B through Ollama to interpret store questions, choose tools, and draft answers. I keep evidence handling, authorization, arithmetic, and execution limits in the application.

## Provider and cost

The provider accepts only HTTP loopback endpoints (`127.0.0.1`, `localhost`, or `::1`), rejects credentials and cloud model tags, and ignores proxy environment variables. The startup script sets `OLLAMA_NO_CLOUD=1`. There is no paid fallback, inference API key, or message-based charge.

The model download is approximately 5.2 GB. I selected it for tool support and the available GPU, accepting hardware-dependent latency and memory requirements. Model availability is not evidence of answer quality.

## Execution

1. I accept the user message with bounded session history and server-controlled customer context.
2. Recognized policy questions receive preventive retrieval, identified by `trigger=retrieval`.
3. The model selects from five tools. Pydantic validates types, limits, and extra fields before execution.
4. Tool results and actual sources return to the model as data. Another tool round is allowed within the budget.
5. A final call without tools produces the natural-language answer. The server builds the HTTP envelope and source list.
6. Evidence checks and explicit business safeguards reject or qualify unsupported results.

The registry contains `search_products`, `get_product`, `quote_payment`, `search_policies`, and `get_order_status`. It has no arbitrary SQL, code execution, network browsing, customer listing, or order-writing tool.

I version the system prompt in `src/emporio_ai/prompts/system.txt`. Responses identify its abbreviated hash, provider, and model. The prompt defines the store persona, scope, evidence requirements, and handling of missing information. User and retrieved text cannot grant new tools or customer access.

Search accepts natural category wording and budgets in reais; the server resolves categories and converts money. If the model finds an unavailable item but does not finish searching for alternatives, an explicit server rule can query the same category. Alternatives are real available products, not a claim of technical equivalence.

Business safeguards use `trigger=business_rule`. They address availability, promotional price disclosure, non-stacking PIX, missing receipt/channel context, warranty timing, expired delivery estimates, and shipping at exactly R$ 500. `generation_mode` distinguishes model output, safeguards, authorization blocks, and safe fallback behavior.

## Execution limits

I limit each message to 2,000 characters, six tool-selection rounds, eight tool calls, and a final formatting step. The agent has a 240-second total budget, with up to 90 seconds per model request. Context includes at most three recent user/assistant pairs and a global character budget.

The provider uses temperature zero, seed 42, an 8,192-token context, and up to 1,200 output tokens. These settings do not ensure identical results across runtime versions or hardware. Initial model loading can increase latency.

A provider failure returns a controlled error, releases the session, and preserves prior history rather than inserting a fabricated answer. Tool-budget or evidence failures produce a controlled status. I do not retry indefinitely.

## Conversation lifecycle

`POST /sessions` creates a random 256-bit token. Only its hash is stored. The caller sends it as `Authorization: Bearer <session_id>` for chat and deletion. Sessions expire after 24 hours, allow at most 20 turns, and have a global capacity of 500. A transactional lease prevents concurrent work in one conversation. A semaphore permits only one local inference at a time.

`DELETE /sessions/current` removes the session and its messages. History is stored in ignored `runtime/sessions.sqlite3`. Operational logs record request ID, model, prompt version, duration, and tool counts; they omit full messages, tool arguments, session tokens, and credentials.

## Order access

I distinguish a conversation capability from customer identity. Order requests without trusted customer context are blocked before inference. `EMPORIO_DEMO_CUSTOMER_ID` supplies a fixed fictional identity on the server for demonstration only. The request body and model cannot choose or change it. Production use would require real authentication and authorization.

## Grounding limits

A valid source ID establishes that the application consulted that record. It does not prove that every sentence is faithful to it. The model may omit a condition or add an unnecessary suggestion. I use deterministic regression tests for safeguards and a separate real-model evaluation for language behavior; I do not present test-double results as model accuracy.
