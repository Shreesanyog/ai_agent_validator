"""LLM-as-a-Judge — Business Logic & MVP Validator tier (Tier 3).

The specialized evaluator required by the AVaaS spec: takes the specific
business requirements/acceptance criteria that a test case targets (sourced
from the Requirement & Use Case Analysis Engine) and grades whether the
agent's response actually achieved the business goal — as opposed to the
safety tier's generic factual/safety check.

Per the RA engine's critical rule that INFERRED requirements must never be
treated as authoritative, this tier only builds its rubric from a test
case's `acceptance_criteria` — which are only ever populated from
EXPLICIT or DERIVED requirements (see
`requirements_analysis/extractor.py` and `test_generation/generator.py`).
If a test case has no acceptance criteria (i.e. it targets only inferred/
generic requirements), this tier is skipped and reports `None` rather than
grading against invented business criteria.
"""
from __future__ import annotations

from ..llm.client import LLMClient
from ..models.schemas import TestCase, TraceRecord


async def evaluate_business(
    llm_client: LLMClient, test_case: TestCase, trace: TraceRecord
) -> tuple[float | None, str]:
    if not test_case.acceptance_criteria:
        return None, "no explicit/derived business acceptance criteria apply to this test case"

    if trace.error is not None:
        return 0.0, f"skipped: request failed ({trace.error})"

    rubric_lines = ["The response (and any tool calls it made) must satisfy ALL of the following business acceptance criteria:"]
    rubric_lines.extend(f"- {c}" for c in test_case.acceptance_criteria)
    rubric_lines.append(f"Business/MVP scenario under test: {test_case.description or test_case.type.value}")
    rubric = "\n".join(rubric_lines)

    context = trace.response_text
    if trace.tool_calls:
        tool_summary = "; ".join(f"{c.name}({c.arguments})" for c in trace.tool_calls)
        context = f"{context}\n\n[tool calls made: {tool_summary}]"

    score, rationale = await llm_client.score(context, rubric)
    return score, rationale
