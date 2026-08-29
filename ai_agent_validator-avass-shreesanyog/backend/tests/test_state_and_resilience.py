"""Tests for downstream state verification, retry/backoff, and Tier-2 wiring
against the standalone mock agent."""
import asyncio, os, sys, threading, time
import pytest
import uvicorn

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'mock-agent'))


@pytest.fixture(scope='module')
def mock_agent():
    import main as mock_main
    cfg = uvicorn.Config(mock_main.app, host='127.0.0.1', port=9155, log_level='error')
    srv = uvicorn.Server(cfg)
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(50):
        if srv.started:
            break
        time.sleep(0.1)
    yield 'http://127.0.0.1:9155'
    srv.should_exit = True


def test_state_verification_passes_after_ticket_created(mock_agent):
    from app.services import state_validation
    from app.services.adapters import RestAdapter

    class T:
        base_url = mock_agent
        auth_encrypted = None
        config = {'path': '/chat', 'prompt_field': 'message', 'response_path': 'response', 'session_field': 'session_id'}
        discovery = {}
        class M: value = 'rest'
        mode = M()
        name = 'mock'

    # Trigger a real downstream mutation, then verify it landed.
    asyncio.run(RestAdapter().invoke_case(T(), {'prompt': 'create ticket please'}))
    result = asyncio.run(state_validation.verify({
        'url': f'{mock_agent}/state/tickets', 'expect_json_path': 'count',
        'expect_operator': 'gt', 'expect_value': 0}))
    assert result['ran'] and result['passed'] is True, result


def test_state_verification_flags_violation(mock_agent):
    from app.services import state_validation
    result = asyncio.run(state_validation.verify({
        'url': f'{mock_agent}/state/tickets', 'expect_json_path': 'count',
        'expect_operator': 'eq', 'expect_value': 99999}))
    assert result['ran'] and result['passed'] is False


def test_state_verification_ssrf_guarded():
    from app.services import state_validation
    # Loopback with private targets disabled (default outside conftest override
    # is enforced by guard_url); here we assert a clearly-bad scheme is rejected.
    result = asyncio.run(state_validation.verify({'url': 'ftp://evil/state'}))
    assert result['passed'] is False and 'guard' in result['detail'].lower()


def test_state_verification_noop_when_not_declared():
    from app.services import state_validation
    result = asyncio.run(state_validation.verify({}))
    assert result['ran'] is False


def test_retry_gives_up_and_reports_after_max(monkeypatch, mock_agent):
    """A dead endpoint should exhaust retries and raise, not hang forever."""
    from app.services.adapters import RestAdapter

    class T:
        base_url = 'http://127.0.0.1:9156'  # nothing listening
        auth_encrypted = None
        config = {'path': '/chat', 'max_retries': 1, 'backoff_seconds': 0.01, 'timeout': 1}
        discovery = {}
        class M: value = 'rest'
        mode = M()
        name = 'dead'

    with pytest.raises(Exception):
        asyncio.run(RestAdapter().invoke_case(T(), {'prompt': 'hi'}))


def test_regression_decision_pass_fail_blocked():
    from app.services import regression
    from types import SimpleNamespace as NS

    def run(**kw):
        base = dict(id='r', score=90, pass_rate=0.9, hallucination_rate=0.0, risk_score=10, summary={})
        base.update(kw)
        return NS(**base)

    def results(critical=0, state_fail=0):
        out = []
        for _ in range(critical):
            out.append(NS(evidence={'policy_findings': [{'severity': 'critical'}]}))
        for _ in range(state_fail):
            out.append(NS(evidence={'state_verification': {'passed': False}}))
        if not out:
            out.append(NS(evidence={}))
        return out

    baseline = run(id='base')
    # PASS: candidate matches baseline, no hard gates.
    assert regression.compare(run(id='c1'), baseline, results())['decision'] == 'PASS'
    # FAIL: composite score dropped well beyond threshold.
    assert regression.compare(run(id='c2', score=50), baseline, results())['decision'] == 'FAIL'
    # BLOCKED: a critical governance finding blocks regardless of scores.
    out = regression.compare(run(id='c3'), baseline, results(critical=1))
    assert out['decision'] == 'BLOCKED' and out['blocked_reasons']
    # BLOCKED: downstream state violation.
    assert regression.compare(run(id='c4'), baseline, results(state_fail=1))['decision'] == 'BLOCKED'
