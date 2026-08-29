"""Governance-layer regression tests: PII, policy, KPI, workflow tables must
stay tenant-scoped and deterministic even as the pipeline evolves."""
from app.models import PolicyRule, PolicyFinding, PromptVersion, Workflow, WorkflowRun
from app.services import pii, compliance, kpi


def test_governance_models_are_tenant_scoped():
    assert all(hasattr(x, 'tenant_id') for x in (PolicyRule, PolicyFinding, PromptVersion, Workflow, WorkflowRun))


def test_pii_scan_detects_email_and_phone():
    hits = pii.scan("Reach me at jane@example.com or 555-222-3333.")
    kinds = {h['type'] for h in hits}
    assert 'email' in kinds and 'phone' in kinds


def test_pii_scan_masks_samples():
    hits = pii.scan("Card: 4111111111111111")
    assert hits and all('***' in h['sample_masked'] for h in hits)


def test_compliance_evaluate_matches_pattern_and_pii():
    class Rule:
        id, name = 'r1', 'no-guarantee'
        class category: value = 'responsible_ai'
        pattern = 'guaranteed cure'
        class severity: value = 'high'
    findings = compliance.evaluate('We guaranteed cure this, email me at x@y.com', [Rule()])
    assert any(f['rule_name'] == 'no-guarantee' for f in findings)
    assert any(f['category'] == 'pii' for f in findings)


def test_risk_score_increases_with_severity_and_hallucination():
    low = compliance.risk_score([[]], hallucination_rate=0.0, pass_rate=1.0)
    high = compliance.risk_score([[{'severity': 'critical'}]], hallucination_rate=0.5, pass_rate=0.5)
    assert high > low


def test_tenant_kpis_handles_no_completed_runs():
    out = kpi.tenant_kpis([])
    assert out['completed_runs'] == 0 and out['total_estimated_cost'] == 0.0
