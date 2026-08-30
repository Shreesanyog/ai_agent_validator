# AVaaS Mock Agent

A standalone REST agent that exercises every behaviour AVaaS validates, so the
full pipeline can run locally with no external LLM or API.

## Run directly

```bash
cd mock-agent
pip install -r requirements.txt
uvicorn main:app --port 9100
```

## Behaviours (selected by keywords in the message)

| Message contains | Behaviour |
|---|---|
| (anything) | normal reply, turn-numbered from session history |
| (empty) | 422 invalid input |
| `order` | emits a `lookup_order` tool call |
| `create ticket` | mutates downstream state (see `GET /state/tickets`) |
| `refund <n>` where n>1000 | business-rule violation (approves over-limit refund) |
| `malformed` | returns malformed JSON |
| `slow` | simulated latency (~1.2s) |

Point an AVaaS target at `http://localhost:9100` with config
`{"path": "/chat", "prompt_field": "message", "response_path": "response", "session_field": "session_id"}`.
