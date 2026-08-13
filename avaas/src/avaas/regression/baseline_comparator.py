"""Phase 4: Regression & Reporting - baseline vs candidate comparison.

Compares a candidate RunReport against the most recent baseline RunReport
for the same agent (within the same tenant) and decides whether a
regression gate should fail the release.
"""
from __future__ import annotations

from ..config import get_settings
from ..models.schemas import RegressionReport, RunReport


def compare_runs(baseline: RunReport, candidate: RunReport) -> RegressionReport:
    settings = get_settings()

    pass_rate_delta = round(candidate.pass_rate - baseline.pass_rate, 4)
    avg_score_delta = round(candidate.avg_score - baseline.avg_score, 2)

    regressed_types: set[str] = set()
    newly_failed: list[str] = []

    baseline_by_signature = {_signature(r): r for r in baseline.results}
    for cand_result in candidate.results:
        sig = _signature(cand_result)
        base_result = baseline_by_signature.get(sig)
        if base_result is None:
            continue
        if base_result.passed and not cand_result.passed:
            newly_failed.append(cand_result.test_case_id)
            regressed_types.add(cand_result.test_case_type.value)

    regressed = (
        pass_rate_delta < -settings.regression_pass_rate_drop_threshold
        or avg_score_delta < -settings.regression_score_drop_threshold
        or len(newly_failed) > 0
    )

    return RegressionReport(
        baseline_run_id=baseline.run_id,
        candidate_run_id=candidate.run_id,
        baseline_pass_rate=baseline.pass_rate,
        candidate_pass_rate=candidate.pass_rate,
        baseline_avg_score=baseline.avg_score,
        candidate_avg_score=candidate.avg_score,
        pass_rate_delta=pass_rate_delta,
        avg_score_delta=avg_score_delta,
        regressed=regressed,
        regressed_test_case_types=sorted(regressed_types),
        newly_failed_test_cases=newly_failed,
    )


def _signature(result) -> str:
    """A stable-ish key to match equivalent test cases across two runs that
    were generated independently (ids are freshly minted each run)."""
    return f"{result.test_case_type.value}:{result.trace.request_payload}"
