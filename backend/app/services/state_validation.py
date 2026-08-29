"""Downstream state / database verification (Phase 3, deterministic tier).

A test case can declare that a successful agent action should have produced a
downstream side effect — a ticket created, a record updated, a balance changed.
This service verifies that claim against the actual downstream system via a
read-only HTTP check, so "the agent said it created a ticket" is separated from
"a ticket actually exists".

Security posture: only HTTP(S) verification is supported here, and it reuses the
same SSRF guard as agent ingestion. Arbitrary SQL/database execution is
deliberately NOT exposed to tenant-supplied input — the spec calls that out as a
control, and the safe, portable form is an API/endpoint the tenant controls that
returns current state. A test declares:

    "state_check": {
        "url": "http://downstream/state/tickets",   # read-only GET
        "expect_json_path": "count",                  # dotted path into the body
        "expect_operator": "gt",                       # eq|ne|gt|gte|lt|lte|contains|exists
        "expect_value": 0
    }
"""
import httpx
from .discovery import guard_url
from .adapters import _extract  # reuse the same dotted-path resolver

_OPERATORS = {
    'eq': lambda a, b: a == b,
    'ne': lambda a, b: a != b,
    'gt': lambda a, b: _num(a) > _num(b),
    'gte': lambda a, b: _num(a) >= _num(b),
    'lt': lambda a, b: _num(a) < _num(b),
    'lte': lambda a, b: _num(a) <= _num(b),
    'contains': lambda a, b: str(b) in str(a),
    'exists': lambda a, b: a is not None,
}


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float('nan')


async def verify(state_check: dict) -> dict:
    """Run one state verification. Returns a structured, storable result.

    Never raises into the pipeline: a verification that can't run is reported as
    passed=False with the reason, so it degrades to a finding rather than
    crashing a validation run.
    """
    if not state_check or not state_check.get('url'):
        return {'ran': False, 'passed': None, 'detail': 'No state_check declared'}
    url = state_check['url']
    op = state_check.get('expect_operator', 'exists')
    expected = state_check.get('expect_value')
    path = state_check.get('expect_json_path')
    try:
        await guard_url(url)
    except Exception as e:
        return {'ran': False, 'passed': False, 'detail': f'State-check URL rejected by SSRF guard: {e}'}
    try:
        async with httpx.AsyncClient(timeout=state_check.get('timeout', 20), follow_redirects=True) as client:
            r = await client.get(url, headers=state_check.get('headers') or {})
            r.raise_for_status()
            try:
                payload = r.json()
            except Exception:
                payload = r.text
    except Exception as e:
        return {'ran': True, 'passed': False, 'detail': f'State check request failed: {type(e).__name__}: {e}'}

    actual = _extract(payload, path) if path else payload
    checker = _OPERATORS.get(op, _OPERATORS['exists'])
    try:
        ok = bool(checker(actual, expected))
    except Exception as e:
        return {'ran': True, 'passed': False, 'detail': f'Comparison error: {e}', 'actual': str(actual)[:200]}
    return {
        'ran': True, 'passed': ok,
        'detail': f"Downstream state {path or 'body'} {op} {expected!r} -> {'satisfied' if ok else 'violated'}",
        'actual': str(actual)[:200],
    }
