# AVaaS Architecture

See the diagram and data flow in the root `README.md`. This document covers the
design decisions behind them.

## Layering

- **`api/routes.py`** — HTTP surface. Every handler resolves a `Principal`
  (tenant + user + role) and filters every query by `tenant_id`. No route reads
  across tenants.
- **`services/`** — all domain logic, each module independently testable and
  free of FastAPI imports.
- **`models.py` / `db.py`** — SQLAlchemy 2.0 typed mappings on an async engine
  driven entirely by `DATABASE_URL`.

## Pluggable providers

Three provider seams are swappable without touching call sites:

| Seam | Primary | Fallback | Selection |
|---|---|---|---|
| LLM (`services/llm.py`) | Ollama (local/OSS) | Gemini | Ollama attempted first; Gemini only if configured and Ollama fails |
| Observability (`services/observability.py`) | Langfuse + OpenTelemetry | LangSmith | Configured provider first; exporter failure never fails a run |
| Target ingestion (`services/adapters.py`) | REST / OpenAPI | Browser (Playwright), Transcript | Chosen by `Target.mode` |

Adding a provider means adding a class with the same `invoke_case` /
`json` shape — the pipeline is provider-agnostic.

## Evaluation architecture

Three independent tiers, deliberately ordered cheapest-and-most-certain first:

1. **Tier 1 — `rules.py`** (deterministic, free): JSON/schema validity, error
   leakage, status codes, required/forbidden content, multi-turn completeness.
2. **Tier 2 — `deepeval_judge.py`** (generic quality): DeepEval → built-in LLM
   rubric → skipped. Never fabricates a score.
3. **Tier 3 — `pipeline.py` judge** (business/MVP): receives the full transcript
   *and* Tier-1 findings, so its verdict is grounded in established evidence.

Running alongside, and independent of all three: `compliance.py` + `pii.py`
governance and `state_validation.py`. Independence is the point — a hallucinating
or compromised LLM judge cannot suppress a governance violation or a failed state
check, because those are computed deterministically and gate the result directly.

Composite score = configurable weighted aggregation of the tiers that produced a
score. A tier that could not run is omitted rather than defaulted, so a missing
tier never silently inflates or deflates the result.

## Regression strategy and release gates

`regression.py` distinguishes two failure modes the spec calls for:

- **FAIL** — measurably worse than baseline beyond configured thresholds.
- **BLOCKED** — a hard gate tripped regardless of baseline: a critical governance
  finding, a downstream state-verification failure, or a sub-50% pass rate.

The distinction matters operationally: FAIL means "compare and decide", BLOCKED
means "do not ship regardless of how the baseline looked".

## Extension points

| To add… | Do this |
|---|---|
| A new target type | New adapter class in `adapters.py` + a `TargetMode` value |
| A new LLM provider | New provider in `llm.py`, keep the `json()` contract |
| A new evaluation tier | New service returning a 0-100 score; add a weight in config |
| A new governance rule class | New `PolicyCategory` + detection in `compliance.py` |
| A new state verifier | Extend `_OPERATORS` in `state_validation.py` |
