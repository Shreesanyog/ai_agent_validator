import httpx
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Isolated DB per test run.
    db_file = tmp_path / "avaas_api_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("REQUIRE_API_KEY", "true")

    # Reset the cached settings singleton so the new env vars take effect.
    from avaas.config import get_settings
    get_settings.cache_clear()

    import avaas.execution.async_runner as async_runner

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": "Order abc is on its way.", "tool_calls": []})

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

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


def _create_tenant(client) -> str:
    resp = client.post("/api/tenants", json={"name": "Test Tenant"})
    assert resp.status_code == 201, resp.text
    return resp.json()["api_key"]


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_agent_endpoints_require_api_key(client):
    resp = client.post("/api/agents", json={"name": "x", "endpoint_url": "http://localhost:9000/invoke"})
    assert resp.status_code == 401


def test_tenant_isolation(client):
    key_a = _create_tenant(client)
    key_b = _create_tenant(client)

    agent_payload = {"name": "A's Agent", "endpoint_url": "http://localhost:9000/invoke", "tools": []}
    resp = client.post("/api/agents", json=agent_payload, headers={"X-API-Key": key_a})
    assert resp.status_code == 201
    agent_id = resp.json()["id"]

    # Tenant B cannot see tenant A's agent.
    resp = client.get(f"/api/agents/{agent_id}", headers={"X-API-Key": key_b})
    assert resp.status_code == 404

    resp = client.get("/api/agents", headers={"X-API-Key": key_b})
    assert resp.status_code == 200
    assert resp.json() == []

    resp = client.get("/api/agents", headers={"X-API-Key": key_a})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_requirements_analyze_endpoint(client):
    key = _create_tenant(client)
    resp = client.post(
        "/api/requirements/analyze",
        json={
            "use_case_definition": "Customer checks order status.",
            "business_requirements": ["Agent must confirm order id before answering."],
        },
        headers={"X-API-Key": key},
    )
    assert resp.status_code == 200, resp.text
    analysis = resp.json()
    assert analysis["analysis_summary"]["explicit_requirement_count"] == 1
    assert len(analysis["use_cases"]) == 1
    assert len(analysis["test_scenarios"]) > 0


def test_agent_and_run_lifecycle(client):
    key = _create_tenant(client)
    headers = {"X-API-Key": key}

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
    resp = client.post("/api/agents", json=agent_payload, headers=headers)
    assert resp.status_code == 201, resp.text
    agent = resp.json()
    agent_id = agent["id"]
    assert agent["tenant_id"]

    resp = client.get(f"/api/agents/{agent_id}", headers=headers)
    assert resp.status_code == 200

    resp = client.post(
        "/api/runs",
        json={
            "agent_id": agent_id,
            "is_baseline": True,
            "max_test_cases": 3,
            "business_requirements": ["The agent must confirm the order id before responding."],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    report = resp.json()
    assert report["is_baseline"] is True
    assert report["test_cases_count"] == 3
    assert "release_gate" in report
    assert "requirement_coverage" in report
    assert report["tenant_id"] == agent["tenant_id"]

    resp = client.get("/api/runs", params={"agent_id": agent_id}, headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = client.get(f"/api/runs/{report['run_id']}/html", headers=headers)
    assert resp.status_code == 200
    assert "AVaaS Validation Report" in resp.text
    assert "Requirement Coverage" in resp.text


def test_run_for_unknown_agent_returns_404(client):
    key = _create_tenant(client)
    resp = client.post("/api/runs", json={"agent_id": "does-not-exist"}, headers={"X-API-Key": key})
    assert resp.status_code == 404


def test_require_api_key_false_uses_default_tenant(client, monkeypatch):
    monkeypatch.setenv("REQUIRE_API_KEY", "false")
    from avaas.config import get_settings
    get_settings.cache_clear()

    resp = client.post("/api/agents", json={"name": "x", "endpoint_url": "http://localhost:9000/invoke", "tools": []})
    assert resp.status_code == 201
    assert resp.json()["tenant_id"] == "tenant_default"

    get_settings.cache_clear()
