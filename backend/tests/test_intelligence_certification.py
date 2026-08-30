"""Tests for AI Test Intelligence, Agent Certification, and drift monitoring."""
from types import SimpleNamespace as NS
from app.services import test_intelligence as ti, certification, monitoring


def _res(prompt, ctype, passed, score, findings=None, run_id='r1'):
    return NS(prompt=prompt, case_type=ctype, passed=passed, composite_score=score,
              evidence={'policy_findings': findings or []}, run_id=run_id, id=prompt)


def test_coverage_gaps_reports_missing_case_types():
    results = [_res('a', 'normal', True, 90), _res('b', 'edge', True, 80)]
    cov = ti.coverage_gaps(results, [])
    assert set(cov['missing_case_types']) == {'injection', 'multi_turn'}
    assert cov['case_type_coverage'] == 0.5


def test_coverage_gaps_flags_untested_requirements():
    reqs = [NS(id='q1', text='System must support refunds for cancelled subscriptions', acceptance=[])]
    cov = ti.coverage_gaps([_res('tell me about pricing', 'normal', True, 90)], reqs)
    assert len(cov['untested_requirements']) == 1
    cov2 = ti.coverage_gaps([_res('process a refund for a cancelled plan', 'normal', True, 90)], reqs)
    assert cov2['untested_requirements'] == []


def test_regression_suite_prioritises_flaky_cases():
    by_run = {
        'r1': [_res('flaky case', 'normal', True, 90, run_id='r1'), _res('stable case', 'normal', True, 95, run_id='r1')],
        'r2': [_res('flaky case', 'normal', False, 40, run_id='r2'), _res('stable case', 'normal', True, 94, run_id='r2')],
    }
    suite = ti.recommend_regression_suite(by_run)
    assert suite, 'expected at least one recommendation'
    assert suite[0]['prompt'] == 'flaky case'
    assert any('flaky' in r for r in suite[0]['reasons'])


def test_release_risk_escalates_with_regression_and_findings():
    cov = {'case_type_coverage': 1.0, 'missing_case_types': []}
    good = NS(id='c', score=92.0, hallucination_rate=0.0, summary={'policy_findings_count': 0})
    history = [NS(id='h1', score=90.0), NS(id='h2', score=91.0)]
    assert ti.predict_release_risk(good, history, cov)['risk_band'] == 'LOW'

    bad = NS(id='c', score=55.0, hallucination_rate=0.5, summary={'policy_findings_count': 6})
    out = ti.predict_release_risk(bad, history, cov)
    assert out['risk_band'] in ('HIGH', 'CRITICAL')
    assert out['factors'], 'risk must be explainable'


def test_certificate_signature_roundtrip_and_tamper_detection():
    run = NS(id='r1', tenant_id='t1', score=91.0, pass_rate=0.9, risk_score=10.0,
             hallucination_rate=0.0, release_gate='PASS')
    target = NS(id='tg1', name='Agent')
    pv = NS(id='pv1', version_no=3)
    cov = {'case_type_coverage': 1.0, 'requirement_coverage': 1.0}
    risk = {'risk_band': 'LOW'}
    cert = certification.build_certificate(run, target, pv, cov, risk)
    assert cert['payload']['status'] == 'CERTIFIED'
    assert certification.verify(cert)['valid'] is True

    tampered = {'payload': {**cert['payload'], 'composite_score': 99.9}, 'signature': cert['signature']}
    assert certification.verify(tampered)['signature_valid'] is False


def test_certificate_denied_when_gate_fails():
    run = NS(id='r1', tenant_id='t1', score=50.0, pass_rate=0.4, risk_score=70.0,
             hallucination_rate=0.4, release_gate='FAIL')
    cert = certification.build_certificate(run, NS(id='t', name='A'), None, {}, {'risk_band': 'HIGH'})
    assert cert['payload']['status'] == 'DENIED'
    assert certification.verify(cert)['valid'] is False


def test_drift_report_detects_production_regression():
    baseline = NS(pass_rate=0.95)
    samples = [NS(passed=False, rule_score=30, policy_findings=[]) for _ in range(8)] + \
              [NS(passed=True, rule_score=90, policy_findings=[]) for _ in range(2)]
    out = monitoring.drift_report(samples, baseline)
    assert out['status'] == 'CRITICAL_DRIFT'
    assert out['drift_vs_baseline'] < -0.2


def test_drift_report_handles_no_samples():
    assert monitoring.drift_report([], None)['status'] == 'NO_DATA'
