# AVaaS Strategic Vision — From Agent Validation Tool to AI Quality Engineering Platform

This document captures the enterprise positioning, stakeholder map, KPIs, governance
model, and roadmap requested in TechCon 2026 judge feedback. It complements
`README.md` (which stays focused on local setup and the implemented feature list)
and `TechCon_2026_AVaaS_Proposal.pdf` (the original pitch).

## Strategic direction

```
Current            Agent Validation Tool
                    (test one agent's responses against generated cases)

Next                AgentOps Platform
                    (govern, chain, and continuously validate agents across
                     their release lifecycle, with tenant-wide KPIs)

Vision              AI Quality Engineering Platform for Enterprise Agent Ecosystems
                    (certification, risk scoring, compliance reporting, and
                     autonomous test-intelligence across a portfolio of agents
                     and multi-agent workflows)
```

The codebase in this repository implements the **Next** stage end-to-end (see
"What changed in this iteration" below) and lays the schema/service seams the
**Vision** stage needs, rather than stubbing it out with placeholder UI.

## Stakeholder map

AVaaS is no longer scoped to a QA team's tool. The platform is designed to be
useful, and separately governable, for:

| Stakeholder | What they get from AVaaS |
|---|---|
| Business & Product | Business-requirement/MVP alignment scoring per release, in plain-language rationale |
| Delivery / Engineering | Release-gate pass/fail/warn, regression detection against a baseline, fast local iteration |
| Architecture & Platform | Pluggable adapter/LLM/observability architecture; one API surface across agent types |
| DevOps | Async background execution today; a documented path to a durable worker queue for CI/CD gating |
| Governance, Risk & Compliance | Policy-rule engine (compliance/security/PII/responsible-AI), audit trail, per-run risk score |
| AI Governance / Responsible AI | Deterministic PII scanning independent of the LLM judge, prompt/config version history, hallucination-rate tracking |
| Security | Tenant isolation, encrypted target credentials, SSRF guarding on discovery, rotating hashed refresh tokens |

## KPIs (implemented, computed from persisted evidence — not aspirational)

Exposed via `GET /api/v1/kpis` (tenant-wide) and inline on every `Run` /
`GET /api/v1/runs/{id}` (per-run):

- **Hallucination Detection Rate** — share of cases the judge flagged as hallucinated (`Run.hallucination_rate`).
- **Regression Detection Accuracy** — score drift vs. the linked baseline run, expressed as an accuracy percentage.
- **Test Coverage** — share of the four case archetypes (normal/edge/injection/multi-turn) exercised in a run.
- **Execution-Time / Latency** — average adapter latency per case, captured from real trace evidence.
- **Cost per Validation Run** — estimated LLM spend per run (provider-aware; $0 on the Ollama path).
- **Agent Release Confidence** — a single 0–100 rollup of composite score, pass rate, and risk score, shown on the run card and used to color the release-gate badge.
- **Release Gate Pass Rate** — portfolio-wide share of runs that passed release gates, for the AgentOps dashboard.
- **Agent Risk Score** — 0–100 composite of governance-finding severity, hallucination rate, and failure rate; `WARN`/`FAIL` gates trigger automatically above threshold.

## Governance capabilities implemented this iteration

- **Prompt Version Management** — `PromptVersion` table + `POST/GET /targets/{id}/prompt-versions`; every system-prompt/config change is versioned, attributed, and auditable.
- **Audit Trails** — the existing `Audit` table now also records governance actions (policy rule creation/removal, run/workflow completion with gate + risk score).
- **Policy / Compliance Validation** — tenant-authored `PolicyRule` rows (regex/keyword, scoped to compliance / security / responsible-AI categories) evaluated deterministically against every response.
- **PII Detection** — always-on regex scanner (`services/pii.py`) for email, phone, SSN-like, credit-card-like, IP address, and API-key-like strings; findings are masked before storage/display.
- **Security Testing** — the existing injection test-case archetype plus policy rules now also gate on security-category findings, not just prompt/response shape.
- **Responsible AI checks** — built-in rule set (`compliance.BUILT_IN_RULES`) for unverified high-stakes advice and fabricated irreversible-action claims; tenants can add their own.
- **Multi-agent / end-to-end workflow validation** — `Workflow`/`WorkflowRun` chain several `Target`s into one validated business process, carrying each step's strongest response forward as the next step's context, with a portfolio release gate.

## AI Test Intelligence (implemented)

`services/test_intelligence.py`, exposed at `POST /projects/{id}/intelligence`:

- **Coverage gap detection** — deterministic analysis of which of the four case
  archetypes (normal/edge/injection/multi_turn) a run exercised, plus which
  business requirements no executed case has touched. The requirement check is
  lexical, and the code says so rather than implying semantic understanding.
- **Regression suite recommendation** — mines all historical results and ranks
  candidates by the signals that actually predict breakage: cases that are flaky
  across runs (passed *and* failed), cases that have caught a real failure, cases
  on injection/edge paths, high score volatility, and cases that previously
  triggered a governance finding. Every recommendation carries its reasons.
- **Release risk prediction** — an explainable 0–100 score with a LOW/MEDIUM/
  HIGH/CRITICAL band, built from score regression vs. historical mean,
  hallucination rate, governance findings, and coverage gaps. Every contribution
  is returned alongside the total so a release decision can be defended in a
  governance review.
- **Generative scenario suggestion** — the one genuinely generative task is left
  to the LLM: proposing risk-bearing scenarios not yet covered. Everything
  quantitative above is deterministic.

## Agent Certification (implemented)

`services/certification.py`. A certificate binds a specific **target + prompt
version + run** and is signed with an HMAC-SHA256 over the canonical payload, so
tampering is detectable offline without a DB lookup — this is what makes it
consumable by an external CI/CD release gate. Certification requires both a
`PASS` release gate and a LOW/MEDIUM predicted risk band; when those aren't met a
`DENIED` certificate is still issued and stored, so the refusal itself is
auditable. Certificates expire after 90 days, making "certified" a claim with a
shelf life rather than a permanent label.

## Production Monitoring & Continuous Validation (implemented)

`services/monitoring.py`, exposed at `POST/GET /targets/{id}/monitor`. Live or
staging interactions are scored through the *same* deterministic tiers used at
release time (rule judge + governance/PII engine), and compared against the
certified baseline's pass rate to produce a drift status:
`HEALTHY` → `GOVERNANCE_FINDINGS` → `DRIFT_DETECTED` → `CRITICAL_DRIFT`.

A deliberate design decision: production sampling does **not** call the LLM judge
by default. Production traffic is high-volume, and a judge call per sample would
make cost scale with traffic. The deterministic tiers are free and catch the
failure classes that matter most in production — malformed output, error
leakage, PII exposure, policy breach.

## Compliance Reporting (implemented)

`GET /projects/{id}/compliance-report` produces a single auditable export for GRC
stakeholders: release-gate outcomes across all runs, governance findings
aggregated by category and severity, every issued certificate with its status,
and the audit trail. The dashboard exports it as JSON.

## Requirement & Use Case Analysis Engine (implemented)

`services/analysis.py`, exposed at `POST/GET /projects/{id}/analysis`. Converts
unstructured inputs (use-case definition, business requirements, agent
description, documentation text) into the structured, traceable spec: use
cases, source-classified requirements, user intents, test-scenario stubs, and
explicitly-flagged requirement gaps — versioned per project so each analysis
run is auditable.

Two things make this defensible rather than "ask the LLM and trust it":

- **Source priority is enforced in the prompt**: explicit business requirements
  and supplied documents outrank the use-case definition, which outranks the
  agent description, which outranks tool schemas. Conflicts between sources are
  surfaced as a `requirement_gap`, never silently resolved.
- **EXPLICIT is deterministically re-checked, not taken on the model's word.**
  Every requirement the model labels `EXPLICIT` is re-verified by term overlap
  against the actual supplied source text; a claim that isn't traceable is
  automatically downgraded to `DERIVED` and flagged `_source_reclassified`. This
  is what stops a tool's mere existence (`cancel_order`) from being promoted
  into an authoritative business rule ("cancellation is permitted") — tested
  directly in `test_analysis_engine.py`.

Test generation (`services/pipeline.py`) now prefers this structured analysis
over the flat `Requirement` rows when one exists for the project, and stamps
`requirement_id`/`use_case_id`/`scenario_id` onto every generated case and
persisted `Result`. `GET /runs/{id}/traceability` walks the resulting chain —
Use Case → Requirement → Test Case → Execution → Evaluation — for one run.

**Known limitation, stated plainly**: PDF documents are accepted as extracted
text (`pdf_documents`/`documentation` fields), not as an uploaded binary parsed
server-side. Wiring an actual PDF upload → text-extraction step is a small,
well-scoped addition, not a redesign, and is on the near-term roadmap below.

## Assumptions

- Tenants provide either a live REST/OpenAPI endpoint, a browser-hosted UI, or a
  transcript; AVaaS cannot validate an agent it cannot reach or replay.
- Ollama is available locally for the primary LLM path; Gemini is a bounded,
  explicitly configured fallback, never a silent default.
- Business requirements supplied by a tenant are treated as authoritative; AVaaS
  never promotes an LLM-inferred scenario to an authoritative business rule.

## Constraints

- Single-process FastAPI `BackgroundTasks` execution (documented in `README.md`)
  is a local/demo constraint, not a production one — the interfaces
  (`execute_run`, `execute_workflow`) are already async and queue-ready.
- Regex-based PII/compliance detection is deterministic and fast but pattern-based;
  it complements, not replaces, the LLM-as-judge safety check, and is not a
  certified DLP or legal-compliance product.
- SQLite is the local default; production requires PostgreSQL, migrations, and
  row-level security as already called out in `README.md`.

## Risks

- **False negatives in policy rules** — a tenant's regex may not catch every
  phrasing of a violation; mitigate with the built-in rule set as a floor and
  periodic rule review, not as the sole compliance control.
- **Cost/latency growth as workflows chain more agents** — each workflow step is
  a full validation run; the cost-per-run KPI is designed to make this visible
  before it becomes a budget surprise.
- **Background-task durability** — an in-process crash mid-run currently loses
  that run's progress (not the DB, which is committed incrementally); this is the
  primary reason a durable worker queue is prioritized on the roadmap below.

## Non-functional requirements

- Tenant data, credentials, and results are isolated at the query level on every
  route (see `backend/tests/test_tenant_isolation.py` and
  `backend/tests/test_governance.py`).
- No PII is ever persisted un-masked; findings store a masked sample only.
- Trace-exporter failures (Langfuse/OTel/LangSmith) must never fail a run or drop
  local evidence — enforced in `services/observability.py`.

## Cost considerations

- LLM spend is Ollama-first (effectively $0 marginal cost) with Gemini as a single
  bounded fallback call; `estimated_cost` is computed and surfaced per run and
  rolled up per tenant so cost is a first-class, visible KPI rather than a
  post-hoc bill surprise.
- PII/policy scanning adds no LLM calls (pure regex), so governance depth does
  not increase per-run cost.

## Competitive positioning (qualitative)

Generic LLM-eval libraries (e.g. DeepEval, Ragas) score individual responses but
are not multi-tenant, do not own release-gating, and have no governance/audit
layer. Observability platforms (Langfuse, LangSmith) capture traces but do not
generate tests or compute a release decision. AVaaS's differentiation is
combining test generation + execution + multi-tier evaluation + governance +
release gating + multi-agent workflow chaining in one tenant-isolated system,
while still integrating the open-source-first tools above as pluggable backends
rather than reinventing them.

## Roadmap

| Stage | Capability | Status |
|---|---|---|
| Now | Multi-tenancy with query-level isolation, RBAC, encrypted credentials, audit trail | Implemented |
| Now | Universal live endpoint ingestion (REST/OpenAPI adapter), true multi-turn with session continuity | Implemented |
| Now | Async runner resilience: bounded concurrency, retry + exponential backoff, rate limiting, correlation IDs | Implemented |
| Now | Three evaluation tiers — deterministic rules (T1), generic quality/DeepEval (T2), business/MVP judge (T3) — with fully configurable composite weights | Implemented |
| Now | Downstream state verification (`state_check`) with SSRF guarding; arbitrary SQL deliberately not exposed | Implemented |
| Now | Requirement & Use Case Analysis Engine with source-priority enforcement and deterministic EXPLICIT-claim verification | Implemented |
| Now | Traceability: requirement/use-case/scenario IDs stamped on every case and result, `GET /runs/{id}/traceability` | Implemented |
| Now | Phase 4 regression: baseline vs candidate comparison with explicit PASS / FAIL / BLOCKED release decision | Implemented |
| Now | Agent Certification (HMAC-signed, expiring, offline-verifiable), Production Monitoring drift, Compliance Reporting | Implemented |
| Now | AI Test Intelligence: coverage gaps, regression-suite recommendation, explainable release-risk prediction | Implemented |
| Now | Governance: prompt versioning, policy/PII/compliance engine, risk scoring, KPI dashboard, multi-agent workflows | Implemented |
| Now | PostgreSQL + Alembic migrations (config-only switch), Docker + docker-compose, standalone mock agent, bootstrap scripts | Implemented (compose not booted in authoring sandbox) |
| Near-term | Durable worker queue (Celery/Arq) so runs survive process restarts and scale horizontally — the main production prerequisite | Not started |
| Near-term | PDF upload → server-side text extraction feeding the analysis engine (currently accepts extracted text) | Not started |
| Near-term | Sustained-RPS load-test mode with latency percentiles (currently bounded concurrent execution) | Not started |
| Near-term | Semantic (embedding-based) requirement coverage to replace the current lexical/term-overlap match | Not started |
| Mid-term | Fully normalized traceability schema as separate tables (`UseCase`, `AcceptanceCriterion`, `ConversationTurn`, `ToolCall`, `Trace`, `Evaluation`, `Baseline`, `RegressionResult`, `ReleaseDecision`) — today these roles are covered by `RequirementAnalysis` + `Run`/`Result` JSON evidence with stamped IDs | Not started |
| Mid-term | Native CI/CD plugins (GitHub Actions / Azure DevOps) consuming certificates as a gate | Not started |
| Mid-term | Scheduled continuous validation runs rather than on-demand only | Not started |
| Long-term | Autonomous Testing: production monitoring findings feeding the next test-generation cycle | Not started |
