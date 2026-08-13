"""Standalone Requirement & Use Case Analysis endpoint.

Lets a QA engineer (or the dashboard's "input business requirements" panel)
run the Requirement Analysis Engine on its own — independent of any run —
to review/iterate on requirements, use cases, and identified gaps before
committing to a validation run. `POST /api/runs` runs this exact same
engine internally as its first phase.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db.session import AgentRecord, get_session
from ..models.schemas import AgentSpec, AnalyzeRequirementsRequest, RequirementAnalysis, Tenant
from ..requirements_analysis.extractor import analyze_requirements
from .deps import get_current_tenant

router = APIRouter(prefix="/api/requirements", tags=["requirements"])


@router.post("/analyze", response_model=RequirementAnalysis)
def analyze(
    payload: AnalyzeRequirementsRequest,
    agent_id: str | None = None,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_session),
) -> RequirementAnalysis:
    agent: AgentSpec | None = None
    if agent_id:
        record = (
            db.query(AgentRecord).filter(AgentRecord.id == agent_id, AgentRecord.tenant_id == tenant.id).first()
        )
        if record is None:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        agent = AgentSpec.model_validate_json(record.spec_json)

    return analyze_requirements(payload, agent=agent)
