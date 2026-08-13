# Requirement & Use Case Analysis Engine

`src/avaas/requirements_analysis/extractor.py` implements the AgentValidator
"Requirement and Use Case Analysis Engine" contract in full: it converts a
use-case definition, explicit business requirements/acceptance criteria,
pre-extracted document text, and/or the agent's own spec into a structured,
traceable specification consumed by Test Generation and Evaluation.

## Traceability chain

```
Requirement -> Use Case -> Acceptance Criterion -> Test Scenario ->
Test Case -> Agent Execution -> Evaluation -> Requirement Status -> Release Decision
```

Concretely, in this codebase:

- `RequirementItem` (`models/schemas.py`) carries `acceptance_criteria`.
- `test_generation/generator.py` copies the acceptance criteria of every
  requirement a `TestScenario` targets onto the concrete `TestCase`s it
  expands from that scenario.
- `evaluation/business_judge.py` uses a test case's `acceptance_criteria`
  directly as its LLM grading rubric.
- `reporting/report_generator.py::compute_requirement_coverage` rolls every
  `EvalResult` back up onto the requirement ids its test case targeted,
  producing the PASS/FAIL/UNTESTED-per-requirement table in the report.

## Source priority & the INFERRED rule

Priority order (highest first): explicit business requirements/acceptance
criteria > requirements in supplied document text > explicit use-case
definition > agent description > system prompt > tool schemas.

**Critical rule, enforced in code, not just docs:** an `INFERRED`
requirement (derived purely from the agent's own tools/prompt/description)
is never treated as authoritative. Concretely:

- `_infer_requirements_from_agent()` reports "agent exposes a `cancel_order`
  tool" — it never asserts that calling it is *permitted*. Permission
  requires an `EXPLICIT` or `DERIVED` requirement.
- `evaluation/business_judge.py` only builds its rubric from a test case's
  `acceptance_criteria`, which are only ever populated from `EXPLICIT`
  requirements (user-supplied) or from a small number of `DERIVED` cases
  where the agent's own configuration (e.g. `disallowed_tools`) makes the
  rule unambiguous — never from `INFERRED` ones.
- `RequirementSource` is a first-class enum value on every requirement in
  the API response, so a QA engineer reviewing `POST
  /api/requirements/analyze` output can see exactly which requirements are
  authoritative and which are the engine's own inference.

## Nine test scenario types

`TestScenarioType` (requirement-level) and `TestCaseType` (execution-level)
share the same nine values: `normal`, `edge`, `boundary`, `negative`,
`injection`, `multi_turn`, `tool_use`, `authorization`, `failure_recovery`.
The Requirement Analysis Engine proposes scenarios (Step 8 of its spec);
`test_generation/generator.py` expands each into one or more concrete,
executable `TestCase`s (see `_SCENARIO_TO_CASE_TYPE` mapping).

## Requirement gaps

`_find_gaps()` currently flags three concrete situations without guessing
at an answer:
1. No explicit business requirements were supplied at all (`critical`).
2. No use-case definition was supplied or derivable (`high`).
3. A declared tool has no explicit/derived authorization statement
   governing when it may be called (`medium`, one per such tool).

Each gap includes a `question_for_qa` — the exact question a human should
answer to close it. Gaps are surfaced in the API response
(`RequirementAnalysis.requirement_gaps`) and in the React dashboard's
Business Requirements panel preview.

## What's intentionally NOT implemented here

- **LLM-based paraphrasing of free-form BRD prose into requirements.** The
  current extraction is deterministic (line/sentence-splitting +
  keyword-based categorization) specifically so that the
  EXPLICIT/DERIVED/INFERRED classification stays exactly traceable to what
  the caller supplied. An LLM enrichment pass is a reasonable next step,
  but should re-tag its own output as `DERIVED` (not `EXPLICIT`) to
  preserve that guarantee — see the module docstring in `extractor.py`.
- **Real PDF file upload/OCR.** `pdf_text` accepts pre-extracted text (e.g.
  pasted from a BRD) — there is no in-repo PDF parser. Wiring in the
  `pdf-reading` tooling used elsewhere in this environment to auto-extract
  `pdf_text` from an uploaded file is the natural next step and would slot
  into `AnalyzeRequirementsRequest.pdf_text` without any other changes.
