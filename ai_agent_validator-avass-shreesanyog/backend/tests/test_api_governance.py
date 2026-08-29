"""API-level tests: auth, tenant isolation, and the new governance endpoints."""
import asyncio
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope='module')
def client():
    from app.db import Base, engine
    from app.main import app

    async def setup():
        async with engine.begin() as c:
            await c.run_sync(Base.metadata.create_all)
    asyncio.run(setup())
    return TestClient(app)


def _register(client, slug, email):
    r = client.post('/api/v1/auth/register', json={
        'organization': f'Org {slug}', 'slug': slug, 'email': email, 'password': 'CorrectHorse123!'})
    assert r.status_code == 200, r.text
    return {'Authorization': f"Bearer {r.json()['access_token']}"}


def test_full_governance_flow_and_tenant_isolation(client):
    a = _register(client, 'tenant-a', 'a@example.com')
    b = _register(client, 'tenant-b', 'b@example.com')

    # Tenant A sets up a project, policy, target, prompt version, workflow.
    pid = client.post('/api/v1/projects', json={'name': 'P', 'description': ''}, headers=a).json()['id']

    pol = client.post(f'/api/v1/projects/{pid}/policies', headers=a, json={
        'name': 'no-guarantees', 'category': 'responsible_ai',
        'pattern': 'guaranteed refund', 'description': '', 'severity': 'high'})
    assert pol.status_code == 200, pol.text

    tgt = client.post(f'/api/v1/projects/{pid}/targets', headers=a, json={
        'name': 'Agent', 'base_url': 'https://agent.example.com', 'mode': 'rest', 'config': {}})
    assert tgt.status_code == 200, tgt.text
    tid = tgt.json()['id']

    pv = client.post(f'/api/v1/targets/{tid}/prompt-versions', headers=a,
                     json={'system_prompt': 'v1 prompt', 'config_snapshot': {}, 'notes': 'initial'})
    assert pv.status_code == 200 and pv.json()['version_no'] == 1
    pv2 = client.post(f'/api/v1/targets/{tid}/prompt-versions', headers=a,
                      json={'system_prompt': 'v2 prompt', 'config_snapshot': {}, 'notes': 'tweak'})
    assert pv2.json()['version_no'] == 2, 'prompt versions must increment'

    wf = client.post(f'/api/v1/projects/{pid}/workflows', headers=a,
                     json={'name': 'chain', 'description': '', 'steps': [tid]})
    assert wf.status_code == 200

    # Monitoring ingests live samples and scores them deterministically.
    mon = client.post(f'/api/v1/targets/{tid}/monitor', headers=a, json={'samples': [
        {'prompt': 'hi', 'response': 'Hello, how can I help you today?', 'source': 'production'},
        {'prompt': 'contact', 'response': 'Email bob@example.com', 'source': 'production'},
    ]})
    assert mon.status_code == 200, mon.text
    assert mon.json()['ingested'] == 2
    # The PII-bearing sample must be flagged by the governance tier.
    report = client.get(f'/api/v1/targets/{tid}/monitor', headers=a).json()
    assert any(s['policy_findings'] for s in report['recent_samples'])

    # Compliance report aggregates for GRC.
    cr = client.get(f'/api/v1/projects/{pid}/compliance-report', headers=a)
    assert cr.status_code == 200 and 'audit_trail' in cr.json()

    # --- Tenant isolation: B must not see or touch A's resources ---
    assert client.get('/api/v1/projects', headers=b).json() == []
    assert client.get(f'/api/v1/projects/{pid}/policies', headers=b).json() == []
    assert client.get(f'/api/v1/targets/{tid}/prompt-versions', headers=b).json() == []
    assert client.get(f'/api/v1/projects/{pid}/workflows', headers=b).json() == []
    assert client.get(f'/api/v1/targets/{tid}/monitor', headers=b).json()['recent_samples'] == []
    assert client.post(f'/api/v1/targets/{tid}/monitor', headers=b,
                       json={'samples': [{'prompt': 'x', 'response': 'y'}]}).status_code == 404


def test_certification_requires_completed_run(client):
    a = _register(client, 'tenant-c', 'c@example.com')
    pid = client.post('/api/v1/projects', json={'name': 'P2'}, headers=a).json()['id']
    tid = client.post(f'/api/v1/projects/{pid}/targets', headers=a, json={
        'name': 'A', 'base_url': 'https://x.example.com', 'mode': 'rest'}).json()['id']
    r = client.post(f'/api/v1/targets/{tid}/certificates', headers=a, json={'run_id': 'does-not-exist'})
    assert r.status_code == 422


def test_unauthenticated_access_is_rejected(client):
    # HTTPBearer returns 401 (missing credentials) or 403 depending on version;
    # what matters is that the request never reaches the handler.
    assert client.get('/api/v1/projects').status_code in (401, 403)
    assert client.get('/api/v1/kpis').status_code in (401, 403)


def test_analysis_engine_endpoint_and_traceability(client, monkeypatch):
    from app.services.llm import LLM

    async def fake_json(self, system, prompt):
        return ({'requirements': [{'requirement_id': 'REQ-001', 'requirement': 'stub', 'source': 'EXPLICIT'}],
                 'use_cases': [], 'user_intents': [], 'test_scenarios': [], 'requirement_gaps': [],
                 'analysis_summary': {}}, 'fake', {'prompt': 5, 'completion': 5})
    monkeypatch.setattr(LLM, 'json', fake_json)

    a = _register(client, 'tenant-d', 'd@example.com')
    b = _register(client, 'tenant-e', 'e@example.com')
    pid = client.post('/api/v1/projects', json={'name': 'P3'}, headers=a).json()['id']

    r = client.post(f'/api/v1/projects/{pid}/analysis', headers=a, json={
        'business_requirements': 'Refunds must be issued within 14 days of an approved return.',
        'agent_description': 'A customer support agent for an e-commerce store.',
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body['version_no'] == 1
    assert 'analysis_summary' in body['analysis']

    # Re-running increments the version.
    r2 = client.post(f'/api/v1/projects/{pid}/analysis', headers=a, json={'business_requirements': 'Updated policy.'})
    assert r2.json()['version_no'] == 2

    latest = client.get(f'/api/v1/projects/{pid}/analysis/latest', headers=a)
    assert latest.status_code == 200 and latest.json()['version_no'] == 2

    all_versions = client.get(f'/api/v1/projects/{pid}/analysis', headers=a).json()
    assert len(all_versions) == 2

    # Tenant isolation on the new endpoints.
    assert client.get(f'/api/v1/projects/{pid}/analysis', headers=b).json() == []
    assert client.get(f'/api/v1/projects/{pid}/analysis/latest', headers=b).status_code == 404


def test_analysis_requires_at_least_one_input(client):
    a = _register(client, 'tenant-f', 'f@example.com')
    pid = client.post('/api/v1/projects', json={'name': 'P4'}, headers=a).json()['id']
    r = client.post(f'/api/v1/projects/{pid}/analysis', headers=a, json={})
    assert r.status_code == 200
    assert r.json()['llm_provider'] == 'none'
    assert r.json()['analysis']['requirement_gaps']
