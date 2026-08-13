"""Validation run endpoints: kick off a run, list runs, fetch a report,
fetch it as HTML, and mark/query baselines for regression comparison.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..db.session import AgentRecord, RunRecord, get_session
from ..models.schemas import AgentSpec, CreateRunRequest, RunReport
from ..pipeline import run_validation
from ..reporting.report_generator import to_html

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _latest_baseline(db: Session, agent_id: str) -> RunReport | None:
    record = (
        db.query(RunRecord)
        .filter(RunRecord.agent_id == agent_id, RunRecord.is_baseline == True)  # noqa: E712
        .order_by(desc(RunRecord.created_at))
        .first()
    )
    if record is None:
        return None
    return RunReport.model_validate_json(record.report_json)


@router.post("", response_model=RunReport, status_code=201)
async def create_run(payload: CreateRunRequest, db: Session = Depends(get_session)) -> RunReport:
    agent_record = db.query(AgentRecord).filter(AgentRecord.id == payload.agent_id).first()
    if agent_record is None:
        raise HTTPException(status_code=404, detail=f"Agent '{payload.agent_id}' not found")
    agent = AgentSpec.model_validate_json(agent_record.spec_json)

    baseline_report = None
    if not payload.is_baseline:
        baseline_report = _latest_baseline(db, agent.id)

    report = await run_validation(
        agent,
        explicit_requirements=payload.explicit_requirements or None,
        is_baseline=payload.is_baseline,
        max_test_cases=payload.max_test_cases,
        baseline_report=baseline_report,
    )

    db.add(
        RunRecord(
            id=report.run_id,
            agent_id=agent.id,
            created_at=report.created_at,
            is_baseline=report.is_baseline,
            pass_rate=report.pass_rate,
            avg_score=report.avg_score,
            release_gate=report.release_gate.value,
            report_json=report.model_dump_json(),
        )
    )
    db.commit()
    return report


@router.get("", response_model=list[RunReport])
def list_runs(agent_id: str | None = None, db: Session = Depends(get_session)) -> list[RunReport]:
    q = db.query(RunRecord)
    if agent_id:
        q = q.filter(RunRecord.agent_id == agent_id)
    records = q.order_by(desc(RunRecord.created_at)).all()
    return [RunReport.model_validate_json(r.report_json) for r in records]


@router.get("/{run_id}", response_model=RunReport)
def get_run(run_id: str, db: Session = Depends(get_session)) -> RunReport:
    record = db.query(RunRecord).filter(RunRecord.id == run_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return RunReport.model_validate_json(record.report_json)


@router.get("/{run_id}/html", response_class=HTMLResponse)
def get_run_html(run_id: str, db: Session = Depends(get_session)) -> str:
    record = db.query(RunRecord).filter(RunRecord.id == run_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    report = RunReport.model_validate_json(record.report_json)
    return to_html(report)
