"""Optional DeepEval integration.

If `USE_DEEPEVAL=true` AND the `deepeval` package is importable, this module
runs a DeepEval `GEval` metric (LLM-graded, using AVaaS's own configured
LLM as DeepEval's judge model where possible) over the response text as an
additional signal feeding the safety/hallucination tier.

If DeepEval is disabled, not installed, or raises for any reason (e.g. it
wants an OpenAI key we don't have), this degrades to returning `None` and
logs at DEBUG level - the safety tier simply proceeds without it. This
keeps DeepEval a genuine enhancement rather than a hard dependency, in
keeping with the rest of the pluggable architecture.
"""
from __future__ import annotations

import logging

from ..config import get_settings

logger = logging.getLogger(__name__)


async def run_deepeval_geval(response_text: str, criteria: str) -> tuple[float, str] | None:
    """Return (score 0-100, metric_name) from a DeepEval GEval run, or None
    if DeepEval isn't enabled/available/successful."""
    settings = get_settings()
    if not settings.use_deepeval:
        return None

    try:
        from deepeval.metrics import GEval  # type: ignore
        from deepeval.test_case import LLMTestCase, LLMTestCaseParams  # type: ignore
    except ImportError:
        logger.debug("USE_DEEPEVAL=true but the 'deepeval' package is not installed; skipping DeepEval tier.")
        return None

    try:
        metric = GEval(
            name="AVaaSBusinessAlignment",
            criteria=criteria,
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
        )
        test_case = LLMTestCase(input="", actual_output=response_text)
        metric.measure(test_case)
        score = float(metric.score or 0.0) * 100.0
        return round(score, 2), "GEval"
    except Exception as exc:  # noqa: BLE001
        logger.warning("DeepEval GEval run failed (%s); continuing without it.", exc)
        return None
