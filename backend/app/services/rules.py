"""Tier 1: deterministic rule-based judge.

Fast, cheap, and fully reproducible checks that run before any LLM is asked
for an opinion — schema/JSON validity, formatting, refusal/error-leakage
detection, and length sanity. This is the tier that catches the "silent
failure" class the platform exists to prevent (malformed JSON, hallucinated
API arguments, stack traces leaking to users) without spending a token.

DeepEval is integrated as an optional extension when USE_DEEPEVAL is enabled
and the case declares a deepeval metric; failures there never fail the run.
"""
import json, logging, re
from jsonschema import validate as js_validate, ValidationError
from ..core.config import settings

logger = logging.getLogger(__name__)

# Signals that the target leaked an internal error rather than answering.
ERROR_LEAK = re.compile(r'(Traceback \(most recent call last\)|<\?php|java\.lang\.|NullPointerException|'
                        r'psycopg2\.|sqlalchemy\.exc\.|Internal Server Error|500 Server Error)', re.I)
# Signals the agent refused/deflected; not inherently a failure, but recorded.
REFUSAL = re.compile(r"\b(I (?:can(?:no|')t|am unable to|won't) (?:help|assist|do that)|as an AI language model)\b", re.I)


def evaluate(case: dict, out: dict, err: str | None) -> tuple[float, list[str]]:
    """Return (rule_score 0-100, list of human-readable rule findings)."""
    findings: list[str] = []
    if err:
        return 0.0, [f'Adapter error: {err}']
    text = (out.get('text') or '').strip()
    if not text:
        return 0.0, ['Empty response from target']

    score = 100.0

    # Transport-level checks (REST adapter surfaces status codes).
    bad_status = [s for s in out.get('evidence', {}).get('status_codes', []) if s >= 400]
    if bad_status:
        score -= 40
        findings.append(f'Non-success HTTP status codes: {bad_status}')

    # Internal error leakage is always a hard failure.
    if ERROR_LEAK.search(text):
        score -= 60
        findings.append('Response leaked an internal error/stack trace to the user')

    # Structured-output contract: if the case expects JSON, it must parse,
    # and must validate against the declared schema when one is supplied.
    expects_json = case.get('expects_json') or bool(case.get('json_schema'))
    if expects_json:
        candidate = _strip_fences(text)
        try:
            parsed = json.loads(candidate)
            if case.get('json_schema'):
                try:
                    js_validate(parsed, case['json_schema'])
                except ValidationError as e:
                    score -= 50
                    findings.append(f'JSON failed schema validation: {e.message}')
        except json.JSONDecodeError as e:
            score -= 60
            findings.append(f'Expected valid JSON but parsing failed: {e.msg}')

    # Required/forbidden substrings straight from the generated case criteria.
    for needle in case.get('must_contain', []) or []:
        if needle.lower() not in text.lower():
            score -= 20
            findings.append(f'Missing required content: {needle!r}')
    for needle in case.get('must_not_contain', []) or []:
        if needle.lower() in text.lower():
            score -= 30
            findings.append(f'Contains forbidden content: {needle!r}')

    # Length sanity: a one-word reply to a substantive prompt is a smell.
    if len(text) < 15 and case.get('type') != 'edge':
        score -= 15
        findings.append('Response suspiciously short for a substantive prompt')

    if REFUSAL.search(text):
        findings.append('Note: agent refused or deflected the request')

    # Multi-turn contract: every turn must have produced a non-empty reply.
    transcript = out.get('evidence', {}).get('transcript') or []
    if len(transcript) > 1:
        empty_turns = [i for i, t in enumerate(transcript) if not (t.get('agent') or '').strip()]
        if empty_turns:
            score -= 25
            findings.append(f'Multi-turn: no reply on turn(s) {empty_turns}')

    score = max(0.0, min(100.0, score))
    deepeval_findings = _deepeval(case, text)
    findings.extend(deepeval_findings)
    return score, findings


def _strip_fences(text: str) -> str:
    """Models often wrap JSON in markdown fences; unwrap before parsing."""
    t = text.strip()
    if t.startswith('```'):
        t = re.sub(r'^```[a-zA-Z]*\n?', '', t)
        t = re.sub(r'\n?```$', '', t)
    return t.strip()


def _deepeval(case: dict, text: str) -> list[str]:
    """Optional DeepEval metrics. Never fails the run if unavailable."""
    if not settings().use_deepeval or not case.get('deepeval_metric'):
        return []
    try:
        from deepeval.metrics import AnswerRelevancyMetric
        from deepeval.test_case import LLMTestCase
        metric = AnswerRelevancyMetric(threshold=0.5)
        tc = LLMTestCase(input=case.get('prompt', ''), actual_output=text)
        metric.measure(tc)
        return [f'DeepEval answer_relevancy={metric.score:.2f} (threshold 0.5)']
    except Exception:
        logger.debug('DeepEval metric unavailable; skipped', exc_info=True)
        return []
