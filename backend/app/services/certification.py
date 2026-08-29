"""Agent Certification.

Issues a tamper-evident certificate binding a specific target + prompt version
to the evidence of a specific validation run. The certificate is what a CI/CD
release gate consumes: it answers "is this exact agent build, with this exact
prompt, cleared for release?" rather than "did some run pass at some point".

The signature is an HMAC over the canonical payload using the application's
JWT secret, so a certificate cannot be edited after issue without detection.
Verification is offline — no DB lookup needed to prove integrity.
"""
import hashlib, hmac, json
from datetime import datetime, timedelta, timezone
from ..core.config import settings

CERT_VALIDITY_DAYS = 90


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()


def sign(payload: dict) -> str:
    key = settings().jwt_secret.get_secret_value().encode()
    return hmac.new(key, _canonical(payload), hashlib.sha256).hexdigest()


def build_certificate(run, target, prompt_version, coverage: dict, risk: dict) -> dict:
    """Assemble the certificate payload and its signature.

    Certification requires an affirmative release gate AND an acceptable risk
    band; a WARN/FAIL gate or HIGH/CRITICAL risk yields a certificate whose
    status is explicitly 'DENIED', which is still issued and stored so the
    refusal itself is auditable.
    """
    issued = datetime.now(timezone.utc)
    eligible = run.release_gate == 'PASS' and risk.get('risk_band') in ('LOW', 'MEDIUM')
    payload = {
        'target_id': target.id,
        'target_name': target.name,
        'tenant_id': run.tenant_id,
        'run_id': run.id,
        'prompt_version_id': getattr(prompt_version, 'id', None),
        'prompt_version_no': getattr(prompt_version, 'version_no', None),
        'composite_score': round(run.score or 0, 2),
        'pass_rate': round(run.pass_rate or 0, 3),
        'risk_score': run.risk_score,
        'predicted_risk_band': risk.get('risk_band'),
        'hallucination_rate': run.hallucination_rate,
        'case_type_coverage': coverage.get('case_type_coverage'),
        'requirement_coverage': coverage.get('requirement_coverage'),
        'release_gate': run.release_gate,
        'status': 'CERTIFIED' if eligible else 'DENIED',
        'issued_at': issued.isoformat(),
        'expires_at': (issued + timedelta(days=CERT_VALIDITY_DAYS)).isoformat(),
        'spec_version': 'avaas-cert-v1',
    }
    return {'payload': payload, 'signature': sign(payload)}


def verify(certificate: dict) -> dict:
    """Offline integrity + expiry check for a previously issued certificate."""
    payload = certificate.get('payload') or {}
    expected = sign(payload)
    intact = hmac.compare_digest(expected, certificate.get('signature', ''))
    try:
        expired = datetime.fromisoformat(payload['expires_at']) < datetime.now(timezone.utc)
    except Exception:
        expired = True
    return {
        'signature_valid': intact,
        'expired': expired,
        'status': payload.get('status'),
        'valid': intact and not expired and payload.get('status') == 'CERTIFIED',
    }
