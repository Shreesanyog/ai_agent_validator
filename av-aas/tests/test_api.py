import os

import httpx
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Isolated DB per test run.
    db_file = tmp_path / "avaas_api_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("LLM_PROVIDER", "mock")

    # Reset the cached settings singleton so the new env vars take effect.
    from avaas.config import get_settings
    get_settings.cache_clear()

    import avaas.execution.async_runner as async_runner

    # Keep a reference to the REAL httpx.AsyncClient before monkeypatching
    # replaces `async_runner.httpx.AsyncClient` (which is the httpx module
    # itself - patching it in place would otherwise recurse into our mock).
    real_async_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": "Order abc is on its way.", "tool_calls": []})

    transport = httpx.MockTransport(handler)

    class _MockAsyncClient:
        def __init__(self, **kwargs):
            self._client = real_async_client(transport=transport)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            await self._client.aclose()

        async def post(self, url, json=None, headers=None):
            return await self._client.post(url, json=json, headers=headers)

    monkeypatch.setattr(async_runner.httpx, "AsyncClient", lambda **kwargs: _MockAsyncClient(**kwargs))

    from avaas.main import app

    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_agent_and_run_lifecycle(client):
    agent_payload = {
        "name": "Test Agent",
        "endpoint_url": "http://localhost:9000/invoke",
        "description": "demo",
        "system_prompt": "be helpful",
        "tools": [
            {
                "name": "get_order_status",
                "description": "look up an order",
                "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]},
            }
        ],
    }
    resp = client.post("/api/agents", json=agent_payload)
    assert resp.status_code == 201, resp.text
    agent = resp.json()
    agent_id = agent["id"]

    resp = client.get(f"/api/agents/{agent_id}")
    assert resp.status_code == 200

    resp = client.post("/api/runs", json={"agent_id": agent_id, "is_baseline": True, "max_test_cases": 3})
    assert resp.status_code == 201, resp.text
    report = resp.json()
    assert report["is_baseline"] is True
    assert report["test_cases_count"] == 3
    assert "release_gate" in report

    resp = client.get("/api/runs", params={"agent_id": agent_id})
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = client.get(f"/api/runs/{report['run_id']}/html")
    assert resp.status_code == 200
    assert "AVaaS Validation Report" in resp.text


def test_run_for_unknown_agent_returns_404(client):
    resp = client.post("/api/runs", json={"agent_id": "does-not-exist"})
    assert resp.status_code == 404
