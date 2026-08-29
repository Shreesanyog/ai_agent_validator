"""Full-pipeline E2E: Business Requirement -> Generation -> Execution ->
Trace -> Rule/LLM/Business Evaluation -> Composite -> Regression -> Release.

The mock agent is real (in-process); only the LLM is stubbed, since no Ollama
runs in the sandbox. This is exactly the E2E flow doc 4 §16 asks for.
"""
import asyncio, os, sys, threading, time
import pytest
import uvicorn

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'mock-agent'))


@pytest.fixture(scope='module')
def mock_agent():
    import main as mock_main
    cfg = uvicorn.Config(mock_main.app, host='127.0.0.1', port=9177, log_level='error')
    srv = uvicorn.Server(cfg)
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(50):
        if srv.started:
            break
        time.sleep(0.1)
    yield 'http://127.0.0.1:9177'
    srv.should_exit = True


def test_end_to_end_pipeline(mock_agent, monkeypatch):
    from app.db import Base, engine, Session
    from app.services.llm import LLM
    from app.services.pipeline import execute_run
    from app.models import Tenant, User, Membership, Project, Target, Run, Result, Requirement, RunStatus, Role, TargetMode
    from sqlalchemy import select

    # Stub the LLM: generation returns a normal + a state-checking case; judge passes.
    async def fake_json(self, system, prompt):
        if 'Test Designer' in system or 'Generate at most' in prompt:
            return ({'cases': [
                {'type': 'normal', 'prompt': 'check my order status'},
                {'type': 'tool_use', 'prompt': 'create ticket for a defective item',
                 'state_check': {'url': f'{mock_agent}/state/tickets', 'expect_json_path': 'count',
                                 'expect_operator': 'gt', 'expect_value': 0}},
            ]}, 'fake', {'prompt': 5, 'completion': 5})
        return ({'safety_score': 90, 'business_score': 85, 'hallucination_detected': False,
                 'rationale': ['looks correct']}, 'fake', {'prompt': 5, 'completion': 5})
    monkeypatch.setattr(LLM, 'json', fake_json)

    async def run_flow():
        async with engine.begin() as c:
            await c.run_sync(Base.metadata.create_all)
        async with Session() as db:
            t = Tenant(name='E2E', slug='e2e-flow')
            u = User(email='e2e@x.com', password_hash='x')
            db.add_all([t, u]); await db.flush()
            db.add(Membership(tenant_id=t.id, user_id=u.id, role=Role.owner))
            proj = Project(tenant_id=t.id, name='E2E', created_by=u.id); db.add(proj); await db.flush()
            db.add(Requirement(tenant_id=t.id, project_id=proj.id, source='user',
                               text='Agent must create a ticket when a defect is reported', acceptance=['ticket exists'], authoritative=True))
            tgt = Target(tenant_id=t.id, project_id=proj.id, name='mock', base_url=mock_agent,
                         mode=TargetMode.rest, created_by=u.id,
                         config={'path': '/chat', 'prompt_field': 'message', 'response_path': 'response', 'session_field': 'session_id'})
            db.add(tgt); await db.flush()
            run = Run(tenant_id=t.id, project_id=proj.id, target_id=tgt.id, created_by=u.id)
            db.add(run); await db.flush()
            rid, tid = run.id, t.id
            await db.commit()
        # Execute the whole pipeline in the background-task function directly.
        await execute_run(rid, tid, max_cases=2, context='')
        async with Session() as db:
            run = (await db.execute(select(Run).where(Run.id == rid))).scalar_one()
            results = list((await db.execute(select(Result).where(Result.run_id == rid))).scalars())
            return run, results

    run, results = asyncio.run(run_flow())
    assert run.status == RunStatus.completed, run.summary
    assert len(results) == 2
    # The state-checking case must have actually verified the downstream ticket.
    state_case = next(r for r in results if r.evidence.get('state_verification', {}).get('ran'))
    assert state_case.evidence['state_verification']['passed'] is True
    # Composite score and release gate were computed.
    assert run.score is not None and run.release_gate in ('PASS', 'WARN', 'FAIL')
