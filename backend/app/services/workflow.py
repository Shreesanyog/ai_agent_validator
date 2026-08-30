"""Multi-agent / end-to-end enterprise workflow validation.

A Workflow is an ordered chain of Targets (e.g. intake agent -> routing
agent -> fulfillment agent). Executing it creates one Run per step and
chains each step's response into the next step's optional_context, so
the validator exercises the same handoffs a real cross-agent business
process depends on, not just each agent in isolation.
"""
from sqlalchemy import select
from ..db import Session
from ..models import Workflow,WorkflowRun,RunStatus,Run,Target,Result
from .pipeline import execute_run


async def execute_workflow(workflow_run_id, tenant_id, max_cases, context):
    async with Session() as db:
        wr = (await db.execute(select(WorkflowRun).where(WorkflowRun.id == workflow_run_id, WorkflowRun.tenant_id == tenant_id))).scalar_one()
        workflow = (await db.execute(select(Workflow).where(Workflow.id == wr.workflow_id, Workflow.tenant_id == tenant_id))).scalar_one()
        wr.status = RunStatus.running
        await db.commit()
    run_ids = []
    carried_context = context
    try:
        for target_id in workflow.steps:
            async with Session() as db:
                target = (await db.execute(select(Target).where(Target.id == target_id, Target.tenant_id == tenant_id))).scalar_one_or_none()
                if not target:
                    continue
                step_run = Run(tenant_id=tenant_id, project_id=target.project_id, target_id=target.id,
                                workflow_run_id=workflow_run_id, created_by=wr.created_by)
                db.add(step_run)
                await db.commit()
                run_ids.append(step_run.id)
            await execute_run(step_run.id, tenant_id, max_cases, carried_context)
            async with Session() as db:
                completed = (await db.execute(select(Run).where(Run.id == step_run.id))).scalar_one()
                results = list((await db.execute(select(Result).where(Result.run_id == step_run.id))).scalars())
                # Chain the strongest observed response forward as context for the next agent in the chain.
                if results:
                    best = max(results, key=lambda r: r.composite_score)
                    carried_context = f"Prior step ({target.name}) response: {best.response[:1500]}"

        async with Session() as db:
            wr = (await db.execute(select(WorkflowRun).where(WorkflowRun.id == workflow_run_id))).scalar_one()
            step_runs = list((await db.execute(select(Run).where(Run.id.in_(run_ids)))).scalars())
            scores = [r.score for r in step_runs if r.score is not None]
            gates = [r.release_gate for r in step_runs if r.release_gate]
            wr.run_ids = run_ids
            wr.composite_score = round(sum(scores) / len(scores), 1) if scores else 0.0
            wr.release_gate = 'PASS' if gates and all(g in ('PASS', 'WARN') for g in gates) and 'FAIL' not in gates else 'FAIL'
            wr.status = RunStatus.completed
            wr.summary = {'steps': len(workflow.steps), 'step_gates': gates}
            await db.commit()
    except Exception as e:
        async with Session() as db:
            wr = (await db.execute(select(WorkflowRun).where(WorkflowRun.id == workflow_run_id))).scalar_one()
            wr.status = RunStatus.failed
            wr.summary = {'error': str(e), 'completed_steps': len(run_ids)}
            await db.commit()
