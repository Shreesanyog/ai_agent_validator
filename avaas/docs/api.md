# AVaaS API Reference

Base URL: `http://localhost:8000` (default). Interactive OpenAPI docs are
always available at `/docs` and `/redoc`.

## Authentication (multi-tenant)

Every route under `/api/` except `POST /api/tenants` requires an
`X-API-Key` header with a valid tenant API key, unless `REQUIRE_API_KEY`
is set to `false` in `.env` (local-only convenience). Missing/invalid keys
return `401`.

## Tenants

`POST /api/tenants`
```json
{ "name": "Acme QA Team" }
```
Returns `{ "id": "...", "name": "...", "api_key": "avaas_...", "created_at": ... }`.
Save the `api_key` — it's not retrievable again through the API.

## Agents

`POST /api/agents` (requires `X-API-Key`)
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
Returns the created `AgentSpec` (includes generated `id` and `tenant_id`).

`GET /api/agents` -> list of `AgentSpec` (scoped to your tenant)
`GET /api/agents/{agent_id}` -> single `AgentSpec`
`DELETE /api/agents/{agent_id}` -> 204

## Requirement & Use Case Analysis

`POST /api/requirements/analyze?agent_id=<optional>`
```json
{
  "use_case_definition": "Customer wants to check an order status or request a refund.",
  "business_requirements": [
    "The agent must never reveal its system prompt.",
    "The agent must confirm the order id before responding."
  ],
  "pdf_text": "",
  "agent_description": "",
  "system_prompt": "",
  "tools": [],
  "documentation": ""
}
```
Runs the Requirement & Use Case Analysis Engine standalone (see
`docs/requirement_analysis.md`) and returns a full `RequirementAnalysis`:
`agent_summary`, `use_cases`, `requirements` (each tagged
`EXPLICIT`/`DERIVED`/`INFERRED`/`UNKNOWN`), `user_intents`,
`test_scenarios`, `requirement_gaps`, `analysis_summary`. If `agent_id` is
supplied, the agent's declared tools/prompt/description are folded in as
additional (`INFERRED`/`DERIVED`) context.

## Runs

`POST /api/runs` (requires `X-API-Key`)
```json
{
  "agent_id": "agent_xxx",
  "use_case_definition": "Customer wants to check an order status or request a refund.",
  "business_requirements": ["The agent must confirm the order id before responding."],
  "pdf_text": "",
  "is_baseline": false,
  "max_test_cases": null
}
```
Executes the full pipeline synchronously (Requirement Analysis -> Test
Generation -> Async Execution -> Multi-Tier Evaluation -> Requirement
Coverage -> Regression) and returns a `RunReport` — includes `regression`
whenever a prior baseline exists for the agent and `is_baseline` is false,
and `requirement_coverage` (a `{requirement_id: "PASS"|"FAIL"|"UNTESTED"}`
map) always.

`GET /api/runs?agent_id=agent_xxx` -> list of `RunReport` (scoped to your tenant)
`GET /api/runs/{run_id}` -> single `RunReport` (JSON)
`GET /api/runs/{run_id}/html` -> the same report rendered as a standalone HTML page

### `EvalResult` shape (inside `RunReport.results`)

Each test case's evaluation carries all three tiers plus the composite:

```json
{
  "test_case_id": "tc_...",
  "test_case_type": "injection",
  "rule_score": 100.0,
  "rule_checks": [ { "name": "no_disallowed_tool_calls", "passed": true, "critical": true } ],
  "safety_score": 92.0,
  "safety_rationale": "...",
  "business_score": 85.0,
  "business_rationale": "...",
  "deepeval_score": null,
  "deepeval_metric": null,
  "composite_score": 91.4,
  "passed": true,
  "requirement_ids": ["REQ_..."],
  "violated_requirement_ids": [],
  "trace": { "response_text": "...", "tool_calls": [...], "latency_ms": 123.4, "trace_id": "...", "trace_backend": "console" }
}
```

`business_score` is `null` when the test case had no explicit/derived
acceptance criteria to grade against (see `docs/requirement_analysis.md`).
