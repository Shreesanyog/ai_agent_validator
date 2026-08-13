"""Tenant provisioning.

`POST /api/tenants` is intentionally NOT behind the `X-API-Key` dependency
(a tenant needs to be created before it has a key to send). In a real
deployment this endpoint would itself sit behind an admin-level credential
or an internal-only network boundary — see README "Security".
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db.session import TenantRecord, get_session
from ..models.schemas import CreateTenantRequest, Tenant

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


@router.post("", response_model=Tenant, status_code=201)
def create_tenant(payload: CreateTenantRequest, db: Session = Depends(get_session)) -> Tenant:
    tenant = Tenant(name=payload.name)
    record = TenantRecord(id=tenant.id, name=tenant.name, api_key=tenant.api_key, created_at=tenant.created_at)
    db.add(record)
    db.commit()
    return tenant
