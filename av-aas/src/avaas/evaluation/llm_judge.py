"""LLM-as-a-Judge (Tier 2 of the dual-tier evaluation).

Scores the agent's free-text response for qualitative fit against the
test case's description and the requirements it targets. Delegates to
LLMClient, which already falls back to a deterministic heuristic score if
no real LLM provider is configured or reachable - so this module never
blocks a run on external-service availability.
"""
from __future__ import annotations

from ..llm.client import LLMClient
from ..models.schemas import RequirementItem, TestCase, TraceRecord


async def evaluate_llm(
    llm_client: LLMClient,
    test_case: TestCase,
    trace: TraceRecord,
    requirements: list[RequirementItem],
) -> tuple[float, str]:
    if trace.error is not None:
        return 0.0, f"skipped: request failed ({trace.error})"

    relevant = [r for r in requirements if r.id in test_case.requirement_ids]
    rubric_lines = [f"- {r.text}" for r in relevant] or ["- The response should be helpful, accurate, and on-topic."]
    rubric_lines.append(f"- Test intent: {test_case.description or test_case.type.value}")
    rubric = "\n".join(rubric_lines)

    score, rationale = await llm_client.score(trace.response_text, rubric)
    return score, rationale
