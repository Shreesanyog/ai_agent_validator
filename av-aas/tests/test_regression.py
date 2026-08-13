from avaas.models.schemas import (
    EvalResult,
    ReleaseGateStatus,
    RuleCheck,
    RunReport,
    TestCaseType,
    TraceRecord,
)
from avaas.regression.baseline_comparator import compare_runs


def _result(tc_id: str, tc_type: TestCaseType, passed: bool, payload: dict) -> EvalResult:
    return EvalResult(
        test_case_id=tc_id,
        test_case_type=tc_type,
        rule_score=100.0 if passed else 0.0,
        rule_checks=[RuleCheck(name="x", passed=passed)],
        composite_score=100.0 if passed else 0.0,
        passed=passed,
        trace=TraceRecord(test_case_id=tc_id, request_payload=payload, response_text="r"),
    )


def _report(run_id: str, results: list[EvalResult], is_baseline: bool) -> RunReport:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    return RunReport(
        run_id=run_id,
        agent_id="agent_1",
        agent_name="Agent",
        is_baseline=is_baseline,
        requirements=[],
        test_cases_count=total,
        results=results,
        pass_rate=passed / total,
        avg_score=sum(r.composite_score for r in results) / total,
        release_gate=ReleaseGateStatus.PASS,
    )


def test_no_regression_when_scores_hold_steady():
    payload = {"turns": [{"role": "user", "content": "hi"}]}
    baseline = _report("run_base", [_result("tc1", TestCaseType.NORMAL, True, payload)], True)
    candidate = _report("run_cand", [_result("tc2", TestCaseType.NORMAL, True, payload)], False)

    reg = compare_runs(baseline, candidate)
    assert reg.regressed is False
    assert reg.newly_failed_test_cases == []


def test_regression_detected_when_previously_passing_case_now_fails():
    payload = {"turns": [{"role": "user", "content": "refund order_id='abc' amount=10"}]}
    baseline = _report("run_base", [_result("tc1", TestCaseType.NORMAL, True, payload)], True)
    candidate = _report("run_cand", [_result("tc2", TestCaseType.NORMAL, False, payload)], False)

    reg = compare_runs(baseline, candidate)
    assert reg.regressed is True
    assert "tc2" in reg.newly_failed_test_cases
    assert "normal" in reg.regressed_test_case_types
