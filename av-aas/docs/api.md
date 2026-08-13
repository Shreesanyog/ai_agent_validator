# AVaaS API Reference

Base URL: `http://localhost:8000` (default).
Interactive OpenAPI docs are always available at `/docs` and `/redoc`.

## Health

`GET /health` -> `{ "status": "ok", "llm_provider": "...", "database_url": "..." }`

## Agents

`POST /api/agents`
```json
{
  "name": "Demo Support Bot",
  "description": "string",
  "endpoint_url": "http://localhost:9000/invoke",
  "system_prompt": "string",
  "tools": [
    {"name": "get_order_status", "description": "string",
     "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]}}
  ],
  "disallowed_tools": []
}
```
Returns the created `AgentSpec` (includes generated `id`).

`GET /api/agents` -> list of `AgentSpec`
`GET /api/agents/{agent_id}` -> single `AgentSpec`
`DELETE /api/agents/{agent_id}` -> 204

## Runs

`POST /api/runs`
```json
{
  "agent_id": "agent_xxx",
  "explicit_requirements": ["The agent must always ask for an order id before refunding."],
  "is_baseline": false,
  "max_test_cases": null
}
```
Executes the full pipeline synchronously and returns a `RunReport`
(includes `regression` when a prior baseline exists for the agent and
`is_baseline` is false).

`GET /api/runs?agent_id=agent_xxx` -> list of `RunReport`
`GET /api/runs/{run_id}` -> single `RunReport` (JSON)
`GET /api/runs/{run_id}/html` -> the same report rendered as a standalone HTML page
