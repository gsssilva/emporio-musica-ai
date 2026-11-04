# Chat interface

I used the supplied AI-assisted HTML prototype and screenshots as a visual reference, then connected the interface to the real session and chat endpoints. I kept the chat first in a centered single-column layout, with explanatory content and technical details below it. The dark theme, orange accents, and local fonts support the store identity without adding an e-commerce workflow.

## Implementation and behavior

I use plain HTML, CSS, and JavaScript served by FastAPI. No frontend build step or external font request is required. Font licenses are included with the assets. The chat adapts to the viewport, with a desktop height capped at 680 pixels.

The browser creates a session automatically and keeps its token and displayed messages in tab-scoped `sessionStorage`. Reloading resumes the tab's conversation; blocked storage falls back to in-memory state. Closing the tab removes that local persistence, while server history follows its own expiration.

Enter sends; Shift+Enter inserts a line. The field allows 2,000 characters. While a request is pending, I disable sending, suggestions, and conversation reset to avoid duplicates or a session switch mid-answer. The waiting message explains local model loading without inventing progress percentages or reasoning steps.

I render model and user content as text, with limited bold and currency formatting, rather than interpreting HTML. Copy uses the answer text. Expandable references display actual returned source records. The technical panel displays the actual trace and metadata; it does not infer an intention or invent tool calls.

For completed catalogue answers without a payment quote, actual catalogue source IDs can load up to five auxiliary product cards from the API. Cards distinguish current product prices from payment conditions. Active promotions show original price, percentage, and promotional price. If an auxiliary request fails, I omit its card and retain the agent answer. Positive stock alone does not mark discontinued or upcoming products as available.

## New conversation

I kept one **Nova conversa** action and removed the redundant plus button. It opens an inline confirmation. **Apagar e iniciar** deletes the current server conversation before creating a replacement. Cancel leaves it unchanged. If deletion fails, I preserve the existing conversation and show the failure instead of reporting success.

## Failure handling

- Unavailable model or network: visible state and a reconnect action.
- Invalid or expired session: replacement session with an explicit resend action; no silent replay.
- Busy conversation or inference: explicit retry without duplicating the customer bubble.
- Session turn limit: an invitation to start another conversation, with deletion confirmation.
- Model failure, invalid response, or timeout: an error rather than fabricated content; retry requires a user action.
- HTTP 200 with a non-completed agent status: the answer is shown with a qualification.

Health checks run every 30 seconds outside active requests. They check service/model availability rather than guaranteeing the next inference. Chat timeout is 250 seconds, slightly above the agent's 240-second budget. A network interruption does not establish that the server stopped processing.

## Accessibility and verification

I use labelled native controls, visible focus, and announced waiting states. The equalizer respects `prefers-reduced-motion`. I did not add audio, uploads, checkout, or simulated customer answers.

To inspect the interface, I start the model and API, send a suggested question, expand its sources, compare its trace, ask a follow-up, reload, and verify keyboard sending and copy. I use a disposable conversation to test deletion.

Python tests check the shell and assets. Ten JavaScript tests use explicit DOM and HTTP doubles to check session creation, text-safe evidence, duplicate suppression, restoration, expiration, busy and limit responses, reset/deletion, failed deletion, blocked storage, and offline handling. These are client tests, not LLM quality measurements or a substitute for browser accessibility review.

```powershell
node --test tests/test_chat_ui.cjs
```

Node is required only for these tests, with no npm dependencies. Running the application itself requires Python and Ollama.
