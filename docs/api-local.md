# Local HTTP API

I serve the chat and API on the same local origin. After installing dependencies, importing data, indexing policies, and starting the model, run:

```powershell
.\.venv\Scripts\python.exe -m uvicorn emporio_ai.api:app --host 127.0.0.1 --port 8000 --no-access-log
```

The root `/` serves the chat; `/docs` serves Swagger; `/assets` serves local assets. Binding to loopback keeps this prototype local. I have not implemented production customer authentication.

## Conversation endpoints

| Method and path | Contract |
| --- | --- |
| `POST /sessions` | Creates a conversation and returns `session_id`; empty body or `{}` |
| `POST /chat` | Accepts `message`; requires the conversation Bearer token |
| `DELETE /sessions/current` | Deletes the authorized conversation and its history |
| `GET /chat/health` | Checks model availability without inference |

In Swagger, I create a session, copy its token into **Authorize**, and send a message such as:

```json
{"message":"Quanto fica o produto 90 no PIX? Posso acumular com a promoção?"}
```

The response includes `answer`, `kind`, `sources`, `tool_trace`, `generation_mode`, `request_id`, `provider`, `model`, `prompt_version`, `usage`, and `status`. Policy sources contain section, pages, text, and the manual hash. Catalogue and order sources identify a snapshot rather than claiming live external integration.

`trigger=retrieval` marks preventive retrieval; `trigger=business_rule` marks a server safeguard. Other tool calls are selected by the model. I expose these distinctions so an evaluator can inspect how the answer was produced.

A session token does not authenticate a customer or purchase model credits. Session creation rejects `customer_id`; order-tool arguments cannot include it. The optional environment-defined demo customer is fixed on the server. There is no public customer-listing or direct order-query endpoint.

## Errors and limits

Invalid arguments return 422. Invalid or expired sessions return 401; missing Bearer credentials are handled by framework security. A busy conversation returns 409, and usage limits or an occupied inference slot return 429. Model or database failures return controlled 503 responses.

A valid HTTP envelope can also contain an agent status other than `completed`, for example after a tool limit. I inspect `status` as well as HTTP status; 200 does not mean every requested operation finished. Provider failures preserve previous history and release the conversation lease.

## Auxiliary catalogue endpoints

| GET path | Purpose |
| --- | --- |
| `/catalogo` | Secondary HTML catalogue view |
| `/health` | Database health and snapshot provenance |
| `/api/categories` | Source categories |
| `/api/products` | Product search and filters |
| `/api/products/{product_id}` | Product detail and current price |
| `/api/products/{product_id}/quote` | Deterministic payment quote |

Product filters are `query`, `category_id`, `max_price_brl`, `available_only`, and `limit`. Quotes accept `method` and `installments` subject to business rules. Budgets accept at most two decimal places. Missing products return 404; unavailable products cannot be quoted and return 409.

I use local resources and safe text insertion in the catalogue HTML. This is not checkout or a hosted store. Integration tests use temporary databases and an identified provider test double; real-model evaluation exercises the same agent service separately.
