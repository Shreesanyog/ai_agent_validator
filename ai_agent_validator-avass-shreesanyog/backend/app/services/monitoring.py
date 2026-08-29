"""Production Monitoring & Continuous Validation.

Closes the loop between pre-release validation and live behaviour: production
(or staging) interactions are submitted to AVaaS and scored through the SAME
tiers used at release time — the deterministic rule judge and the governance
policy/PII engine — so a drift between "passed QA" and "behaving in prod" is
measurable rather than anecdotal.

Deliberately does NOT call the LLM judge by default: production sampling is
high-volume, and spending a judge call per sampled interaction would make cost
scale with traffic. Rule + governance tiers are free and catch the failure
classes that matter most in production (malformed output, error leakage, PII
exposure, policy breach). LLM judging stays opt-in per sample.
"""
from statistics import mean
from . import compliance
from . import rules as rule_judge


def score_sample(prompt: str, response: str, policy_rules: list) -> dict:
    """Score one live interaction through the deterministic tiers."""
    out = {'text': response, 'latency_ms': 0, 'evidence': {}}
    rule_score, rule_findings = rule_judge.evaluate({'prompt': prompt, 'type': 'normal'}, out, None)
    findings = compliance.evaluate(response, policy_rules)
    critical = any(f['severity'] == 'critical' for f in findings)
    return {
        'rule_score': rule_score,
        'rule_findings': rule_findings,
        'policy_findings': findings,
        'passed': rule_score >= 70 and not critical,
    }


def drift_report(samples: list, baseline_run) -> dict:
    """Compare live sampled behaviour against the certified baseline run.

    A sustained gap between production pass rate and the pass rate the agent
    was certified at is the signal that a re-validation (or rollback) is due.
    """
    if not samples:
        return {'samples': 0, 'production_pass_rate': None, 'drift_vs_baseline': None, 'status': 'NO_DATA'}
    passed = sum(1 for s in samples if s.passed)
    prod_rate = passed / len(samples)
    scores = [s.rule_score for s in samples if s.rule_score is not None]
    findings_total = sum(len(s.policy_findings or []) for s in samples)

    drift = None
    status = 'HEALTHY'
    if baseline_run and baseline_run.pass_rate is not None:
        drift = round(prod_rate - baseline_run.pass_rate, 3)
        if drift <= -0.20:
            status = 'CRITICAL_DRIFT'
        elif drift <= -0.10:
            status = 'DRIFT_DETECTED'
    if findings_total and status == 'HEALTHY':
        status = 'GOVERNANCE_FINDINGS'

    return {
        'samples': len(samples),
        'production_pass_rate': round(prod_rate, 3),
        'avg_rule_score': round(mean(scores), 1) if scores else None,
        'governance_findings': findings_total,
        'baseline_pass_rate': round(baseline_run.pass_rate, 3) if baseline_run and baseline_run.pass_rate is not None else None,
        'drift_vs_baseline': drift,
        'status': status,
        'recommendation': {
            'NO_DATA': 'No production samples ingested yet.',
            'HEALTHY': 'Production behaviour matches certified baseline.',
            'GOVERNANCE_FINDINGS': 'Live traffic triggered policy/PII findings; review before next release.',
            'DRIFT_DETECTED': 'Production pass rate has drifted below baseline. Schedule re-validation.',
            'CRITICAL_DRIFT': 'Severe drift from certified baseline. Re-validate or roll back.',
        }[status],
    }
