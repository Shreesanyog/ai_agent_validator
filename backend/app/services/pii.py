"""Deterministic PII detection.

Runs on every agent response as part of the responsible-AI / governance
layer. Deliberately regex-based (no external call, no added latency/cost)
so it can never be bypassed by a model failing to call a tool, and never
adds nondeterminism to a compliance gate.
"""
import re

PATTERNS = {
    'email': re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+'),
    'phone': re.compile(r'(?<!\d)(\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)'),
    'ssn_like': re.compile(r'(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)'),
    'credit_card': re.compile(r'(?<!\d)(?:\d[ -]*?){13,16}(?!\d)'),
    'ip_address': re.compile(r'(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)'),
    'api_key_like': re.compile(r'\b(?:sk|pk|api|key)[-_][A-Za-z0-9]{16,}\b', re.I),
}


def scan(text: str) -> list[dict]:
    """Return a list of {type, sample, count} findings for a block of text."""
    if not text:
        return []
    findings = []
    for kind, pattern in PATTERNS.items():
        hits = [m.group(0) for m in pattern.finditer(text)]
        if hits:
            sample = hits[0] if isinstance(hits[0], str) else ''.join(hits[0])
            masked = sample[:2] + '***' + sample[-2:] if len(sample) > 4 else '***'
            findings.append({'type': kind, 'sample_masked': masked, 'count': len(hits)})
    return findings
