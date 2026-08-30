"""Phase 4 — Baseline vs candidate regression + release-gate decision.

Compares a candidate run against a baseline run across the metrics doc 4 §7
enumerates, classifies each delta, and rolls the result into an explicit
PASS / FAIL / BLOCKED release decision with per-check reasons and evidence.

The distinction the spec asks for:
  * FAIL    — the candidate is measurably worse than baseline beyond threshold.
  * BLOCKED — a hard gate tripped regardless of baseline (e.g. a critical
              governance finding, or a declared state-check violation), so the
              release is blocked even if it didn't "regress".
"""
from ..core.config import settings


def _metric(run, name, default=None):
    if name in ('score', 'pass_rate', 'hallucination_rate', 'risk_score', 'release_confidence'):
        return getattr(run, name, default)
    return (run.summary or {}).get(name, default)


def compare(candidate, baseline, candidate_results) -> dict:
    """Return a full regression + release-gate report."""
    s = settings()
    checks = []
    regressions = []

    def add(name, cand, base, worse_if, threshold=None):
        delta = None if (cand is None or base is None) else round(cand - base, 3)
        regressed = False
        if delta is not None:
            if worse_if == 'lower' and threshold is not None and delta < -threshold:
                regressed = True
            elif worse_if == 'higher' and threshold is not None and delta > threshold:
                regressed = True
        checks.append({'metric': name, 'candidate': cand, 'baseline': base, 'delta': delta,
                       'regressed': regressed})
        if regressed:
            regressions.append(name)

    if baseline is not None:
        add('composite_score', _metric(candidate, 'score'), _metric(baseline, 'score'),
            'lower', s.regression_score_drop_threshold)
        add('pass_rate', _metric(candidate, 'pass_rate'), _metric(baseline, 'pass_rate'),
            'lower', s.regression_pass_rate_drop_threshold)
        add('hallucination_rate', _metric(candidate, 'hallucination_rate'), _metric(baseline, 'hallucination_rate'),
            'higher', 0.1)
        add('risk_score', _metric(candidate, 'risk_score'), _metric(baseline, 'risk_score'),
            'higher', 15)

    # Hard gates (BLOCKED regardless of baseline).
    blocked_reasons = []
    critical_findings = sum(1 for r in candidate_results
                            for f in (r.evidence.get('policy_findings') or [])
                            if f.get('severity') == 'critical')
    if critical_findings:
        blocked_reasons.append(f'{critical_findings} critical governance finding(s)')
    state_violations = sum(1 for r in candidate_results
                           if (r.evidence.get('state_verification') or {}).get('passed') is False)
    if state_violations:
        blocked_reasons.append(f'{state_violations} downstream state-verification failure(s)')
    if (_metric(candidate, 'pass_rate') or 0) < 0.5:
        blocked_reasons.append('candidate pass rate below 50% floor')

    if blocked_reasons:
        decision = 'BLOCKED'
    elif regressions:
        decision = 'FAIL'
    else:
        decision = 'PASS'

    return {
        'decision': decision,
        'candidate_run_id': candidate.id,
        'baseline_run_id': getattr(baseline, 'id', None),
        'regressions': regressions,
        'blocked_reasons': blocked_reasons,
        'checks': checks,
        'summary': (
            'Release blocked: ' + '; '.join(blocked_reasons) if decision == 'BLOCKED'
            else ('Regression detected in: ' + ', '.join(regressions) if decision == 'FAIL'
                  else 'No regression beyond thresholds; release gate passed.')),
    }
