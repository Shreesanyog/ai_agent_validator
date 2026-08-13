"""Agent onboarding endpoints (tenant-scoped)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db.session import AgentRecord, get_session
from ..models.schemas import AgentSpec, CreateAgentRequest, Tenant
from .deps import get_current_tenant

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.post("", response_model=AgentSpec, status_code=201)
def create_agent(
    payload: CreateAgentRequest, tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_session)
) -> AgentSpec:
    spec = AgentSpec(tenant_id=tenant.id, **payload.model_dump())
    record = AgentRecord(
        id=spec.id,
        tenant_id=tenant.id,
        name=spec.name,
        created_at=spec.created_at,
        spec_json=spec.model_dump_json(),
    )
    db.add(record)
    db.commit()
    return spec


@router.get("", response_model=list[AgentSpec])
def list_agents(tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_session)) -> list[AgentSpec]:
    records = (
        db.query(AgentRecord)
        .filter(AgentRecord.tenant_id == tenant.id)
        .order_by(AgentRecord.created_at.desc())
        .all()
    )
    return [AgentSpec.model_validate_json(r.spec_json) for r in records]


@router.get("/{agent_id}", response_model=AgentSpec)
def get_agent(
    agent_id: str, tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_session)
) -> AgentSpec:
    record = (
        db.query(AgentRecord).filter(AgentRecord.id == agent_id, AgentRecord.tenant_id == tenant.id).first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return AgentSpec.model_validate_json(record.spec_json)


@router.delete("/{agent_id}", status_code=204)
def delete_agent(
    agent_id: str, tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_session)
) -> None:
    record = (
        db.query(AgentRecord).filter(AgentRecord.id == agent_id, AgentRecord.tenant_id == tenant.id).first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    db.delete(record)
    db.commit()
