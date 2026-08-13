# AVaaS Architecture

```
QA ENGINEER
     |
     v
AGENT ONBOARDING (endpoint, system prompt, tools/schemas, description)
     |
     +--> REQUIREMENTS (explicit business rules, OR inferred from spec)
     |
     v
REQUIREMENT ANALYSIS  (src/avaas/requirements_analysis/extractor.py)
     |
     v
TEST GENERATION        (src/avaas/test_generation/generator.py)
  normal / edge / boundary / injection / multi-turn
     |
     v
ASYNC EXECUTION         (src/avaas/execution/async_runner.py)
  concurrent HTTP calls to the target agent endpoint
     |
     v
TRACE COLLECTION        (captured inline in async_runner.py -> TraceRecord)
  response, tool calls, arguments, latency, tokens
     |
     v
EVALUATION (dual-tier)  (src/avaas/evaluation/*.py)
  rule_based_judge.py  - deterministic schema/keyword/latency checks
  llm_judge.py          - LLM-as-a-judge qualitative score (falls back to a
                          deterministic heuristic when no LLM is configured)
  composite_scorer.py   - weighted composite score + pass/fail decision
     |
     v
REQUIREMENT COVERAGE     (EvalResult.violated_requirement_ids)
     |
     v
BASELINE vs CANDIDATE    (src/avaas/regression/baseline_comparator.py)
     |
     v
RELEASE GATE  PASS / FAIL
     |
     v
REPORT / DASHBOARD       (src/avaas/reporting/report_generator.py + frontend/)
```

`src/avaas/pipeline.py` is the single orchestrator that calls each phase in
order and is used by both the HTTP API (`api/routes_runs.py`) and any future
CLI/batch entry point.

## Data flow contracts

* **AgentSpec** - what gets onboarded (endpoint, prompt, tools as JSON Schema).
* **RequirementItem** - one testable statement, explicit or inferred.
* **TestCase** - one generated scenario (turns, expectations, related requirement ids).
* **TraceRecord** - what actually happened when a TestCase was executed.
* **EvalResult** - the scored, pass/fail verdict for one TestCase.
* **RunReport** - the full run: requirements + results + pass rate + release gate (+ optional regression).

All of the above are defined once, in `src/avaas/models/schemas.py`, and
reused end-to-end so every phase speaks the same contract.

## Storage

Two tables (`agents`, `runs`), SQLite by default via SQLAlchemy
(`src/avaas/db/session.py`). Swap `DATABASE_URL` to point at Postgres/MySQL
for production; no code changes required.

## Why the pipeline never hard-fails on missing external services

* No LLM key configured -> `LLM_PROVIDER=mock` (or automatic fallback) gives
  deterministic heuristic scoring, so the *rule-based* judge - which is
  usually more important for catching hallucinated tool calls and prompt
  injection - always runs at full strength.
* No target agent reachable -> individual TraceRecords carry the error,
  the rule-based judge fails those test cases explicitly (`no_transport_error`),
  and the rest of the pipeline still produces a report.
