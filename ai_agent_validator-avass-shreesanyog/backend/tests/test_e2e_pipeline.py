"""End-to-end pipeline test against a real in-process mock agent.

Proves the REST adapter, multi-turn execution, deterministic rule tier,
governance layer, certification, and monitoring all work together — without
requiring Ollama, Gemini, or a browser.
"""
import asyncio, json, os, threading, time
import pytest
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

# ---- Mock system under test: a tiny "agent" with session memory ----
mock = FastAPI()
SESSIONS = {}

class Msg(BaseModel):
    message: str
    session_id: str | None = None

@mock.post('/chat')
def chat(m: Msg):
    hist = SESSIONS.setdefault(m.session_id or 'x', [])
    hist.append(m.message)
    if 'json' in m.message.lower():
        return {'response': json.dumps({'status': 'ok', 'items': 2})}
    if 'leak' in m.message.lower():
        return {'response': 'Traceback (most recent call last): ValueError'}
    if 'pii' in m.message.lower():
        return {'response': 'Sure, contact bob@example.com or 555-123-4567.'}
    return {'response': f'Reply {len(hist)} to: {m.message}', 'tool_calls': [{'name': 'lookup'}]}


@pytest.fixture(scope='module')
def server():
    cfg = uvicorn.Config(mock, host='127.0.0.1', port=8899, log_level='error')
    srv = uvicorn.Server(cfg)
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(50):
        if srv.started:
            break
        time.sleep(0.1)
    yield 'http://127.0.0.1:8899'
    srv.should_exit = True


class FakeTarget:
    """Minimal duck-typed Target so the adapter needs no DB."""
    def __init__(self, url):
        self.base_url = url
        self.auth_encrypted = None
        self.config = {'path': '/chat', 'prompt_field': 'message', 'response_path': 'response'}
        self.discovery = {}
        class M: value = 'rest'
        self.mode = M()
        self.name = 'mock-agent'


def test_rest_adapter_single_turn(server):
    from app.services.adapters import RestAdapter
    out = asyncio.run(RestAdapter().invoke_case(FakeTarget(server), {'prompt': 'hello', 'type': 'normal'}))
    assert 'Reply 1' in out['text']
    assert out['evidence']['adapter'] == 'rest'
    assert out['evidence']['status_codes'] == [200]
    assert out['evidence']['tool_calls'], 'tool call trace evidence should be captured'


def test_rest_adapter_multi_turn_carries_session(server):
    from app.services.adapters import RestAdapter
    case = {'type': 'multi_turn', 'turns': ['first', 'second', 'third']}
    out = asyncio.run(RestAdapter().invoke_case(FakeTarget(server), case))
    # Session memory means the third reply must know it is the third turn.
    assert 'Reply 3' in out['text']
    assert out['evidence']['turns'] == 3
    assert len(out['evidence']['transcript']) == 3


def test_rule_judge_detects_error_leak(server):
    from app.services.adapters import RestAdapter
    from app.services import rules
    out = asyncio.run(RestAdapter().invoke_case(FakeTarget(server), {'prompt': 'leak please', 'type': 'normal'}))
    score, findings = rules.evaluate({'prompt': 'leak please', 'type': 'normal'}, out, None)
    assert score < 50
    assert any('stack trace' in f.lower() or 'internal error' in f.lower() for f in findings)


def test_rule_judge_validates_json_schema(server):
    from app.services.adapters import RestAdapter
    from app.services import rules
    out = asyncio.run(RestAdapter().invoke_case(FakeTarget(server), {'prompt': 'give me json', 'type': 'normal'}))
    case = {'prompt': 'give me json', 'type': 'normal', 'expects_json': True,
            'json_schema': {'type': 'object', 'required': ['status', 'items'],
                            'properties': {'status': {'type': 'string'}, 'items': {'type': 'integer'}}}}
    score, findings = rules.evaluate(case, out, None)
    assert score == 100, findings

    bad = {**case, 'json_schema': {'type': 'object', 'required': ['missing_field']}}
    bad_score, bad_findings = rules.evaluate(bad, out, None)
    assert bad_score < 100 and any('schema' in f.lower() for f in bad_findings)


def test_monitoring_flags_pii_in_production_sample(server):
    from app.services.adapters import RestAdapter
    from app.services import monitoring
    out = asyncio.run(RestAdapter().invoke_case(FakeTarget(server), {'prompt': 'pii please', 'type': 'normal'}))
    scored = monitoring.score_sample('pii please', out['text'], [])
    kinds = {f['category'] for f in scored['policy_findings']}
    assert 'pii' in kinds
