# AVaaS Architecture

```
QA ENGINEER
     |
     v
AGENT ONBOARDING (endpoint, system prompt, tools/schemas, description)  [multi-tenant: scoped by X-API-Key]
     |
     +--> REQUIREMENTS (business rules, user stories, acceptance criteria, OR inferred)
     |
     v
REQUIREMENT & USE CASE ANALYSIS      src/avaas/requirements_analysis/extractor.py
  use cases, requirements (EXPLICIT/DERIVED/INFERRED/UNKNOWN),
  user intents, test scenarios, requirement gaps
     |
     v
TEST GENERATION                      src/avaas/test_generation/generator.py
  normal / edge / boundary / negative / injection / multi-turn /
  tool-use / authorization / failure-recovery
     |
     v
ASYNC EXECUTION                      src/avaas/execution/async_runner.py
  concurrent HTTP calls to the target agent endpoint
     |
     v
TRACE COLLECTION                     (captured inline in async_runner.py -> TraceRecord)
  response, tool calls, arguments, latency, tokens
  + pluggable tracing span             src/avaas/tracing/tracer.py
    (Langfuse+OTel primary -> LangSmith fallback -> console fallback)
     |
     v
MULTI-TIER EVALUATION                src/avaas/evaluation/*.py
  rule_based_judge.py   - deterministic schema/keyword/latency checks
  llm_judge.py           - safety & hallucination LLM-as-a-judge
                            (+ optional DeepEval GEval blend, deepeval_adapter.py)
  business_judge.py      - business logic / MVP alignment LLM-as-a-judge
                            (rubric = the test case's business acceptance criteria)
  composite_scorer.py    - 3-way weighted composite + pass/fail decision
     |
     v
REQUIREMENT COVERAGE                 src/avaas/reporting/report_generator.py
  PASS / FAIL / UNTESTED per requirement
     |
     v
BASELINE vs CANDIDATE                src/avaas/regression/baseline_comparator.py
     |
     v
RELEASE GATE  PASS / FAIL
     |
     v
REPORT / DASHBOARD                   report_generator.py (JSON + HTML) + frontend/ (React)
```

`src/avaas/pipeline.py` is the single orchestrator that calls each phase in
order (`run_validation()`) and is used by the HTTP API
(`api/routes_runs.py`). `POST /api/requirements/analyze` exposes the
Requirement & Use Case Analysis phase standalone, for previewing/iterating
before committing to a full run.

## Multi-tenancy

Every `AgentSpec` and `RunReport` carries a `tenant_id`. Tenants are created
via `POST /api/tenants` (returns an API key) and every other `/api/*` route
requires that key in the `X-API-Key` header (`api/deps.py`), unless
`REQUIRE_API_KEY=false` (local dev convenience — a `tenant_default` tenant
is used implicitly). Isolation is enforced at the query level: every
agent/run lookup filters by `tenant_id`, so one tenant's data is never
returned to another's requests, even by id. See README "Security" for the
production hardening notes (secrets-at-rest, per-tenant rate limits, etc.)
this MVP does not yet implement.

## Provider fallback

**LLM (Ollama primary / Gemini commercial fallback):** `LLM_PROVIDER`
selects which provider `LLMClient` (`llm/client.py`) attempts first for a
given call. If that call raises for any reason (service down, bad key,
timeout), `LLMClient` catches it and falls back to its built-in
deterministic heuristic scorer — NOT automatically to the other configured
provider. This is a deliberate simplification: chaining Ollama -> Gemini
automatically would silently start sending data to a commercial API the
moment the local model has a bad day, which cuts against the "data
sovereignty" goal of the primary-OSS design. If you want true
Ollama-then-Gemini failover, set `LLM_PROVIDER=gemini` as your safety net
and keep an eye on Ollama's health separately, or extend
`LLMClient.generate()` — the two provider methods (`_call_ollama`,
`_call_gemini`) are already isolated and easy to chain explicitly.

**Tracing (Langfuse+OpenTelemetry primary / LangSmith commercial
fallback):** `tracing/tracer.py` DOES implement true automatic fallback,
because trace export failing over is comparatively low-stakes (it's
telemetry, not data processing): it checks Langfuse credentials, then an
OTel OTLP endpoint, then a LangSmith key, in that order, and uses the first
one that initializes successfully — falling through the chain, not just to
a single fallback. If none are configured, it logs structured trace events
to the console/log instead, so tracing is never a hard dependency for a run
to complete.

## Why the pipeline never hard-fails on missing external services

* No LLM key configured -> `LLM_PROVIDER=mock` (or automatic fallback)
  gives deterministic heuristic scoring for both the safety and business
  tiers, so the *rule-based* judge — which is usually more important for
  catching hallucinated tool calls and prompt injection — always runs at
  full strength.
* No target agent reachable -> individual TraceRecords carry the error,
  the rule-based judge fails those test cases explicitly
  (`no_transport_error`), and the rest of the pipeline still produces a
  report.
* No tracing backend configured -> falls through to console logging;
  execution and evaluation are entirely unaffected.
* No business requirements supplied -> the business/MVP judge tier is
  skipped per test case (not graded against invented criteria — see
  `evaluation/business_judge.py`) and the Requirement Analysis Engine
  reports this explicitly as a `REQUIREMENT_GAP`, rather than silently
  proceeding as if everything were fine.
