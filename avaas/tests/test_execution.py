import httpx
import pytest

from avaas.models.schemas import AgentSpec, ConversationTurn, TestCase, TestCaseType, ToolSchema
import avaas.execution.async_runner as async_runner

# Keep a reference to the REAL httpx.AsyncClient before any monkeypatching
# replaces `async_runner.httpx.AsyncClient` (which is the httpx module
# itself, so patching it in place would otherwise recurse into our mock).
_RealAsyncClient = httpx.AsyncClient


def _agent() -> AgentSpec:
    return AgentSpec(
        tenant_id="tenant_test",
        name="Test Agent",
        endpoint_url="http://testserver/invoke",
        tools=[ToolSchema(name="echo", parameters={"type": "object", "properties": {}})],
    )


class _MockAsyncClient:
    """Minimal stand-in for httpx.AsyncClient bound to a MockTransport."""

    def __init__(self, transport: httpx.MockTransport, **kwargs):
        self._client = _RealAsyncClient(transport=transport)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self._client.aclose()

    async def post(self, url, json=None, headers=None):
        return await self._client.post(url, json=json, headers=headers)


@pytest.mark.asyncio
async def test_run_test_cases_success(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": "hello there", "tool_calls": [{"name": "echo", "arguments": {}}]})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        async_runner.httpx, "AsyncClient", lambda **kwargs: _MockAsyncClient(transport, **kwargs)
    )

    agent = _agent()
    tc = TestCase(type=TestCaseType.NORMAL, turns=[ConversationTurn(content="hi")])
    traces = await async_runner.run_test_cases(agent, [tc])

    assert len(traces) == 1
    trace = traces[0]
    assert trace.error is None
    assert trace.response_text == "hello there"
    assert trace.tool_calls[0].name == "echo"
    assert trace.latency_ms >= 0
    assert trace.trace_id is not None
    assert trace.trace_backend == "console"


@pytest.mark.asyncio
async def test_run_test_cases_records_transport_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        async_runner.httpx, "AsyncClient", lambda **kwargs: _MockAsyncClient(transport, **kwargs)
    )

    agent = _agent()
    tc = TestCase(type=TestCaseType.NORMAL, turns=[ConversationTurn(content="hi")])
    traces = await async_runner.run_test_cases(agent, [tc])

    assert traces[0].error is not None
    assert "ConnectError" in traces[0].error
