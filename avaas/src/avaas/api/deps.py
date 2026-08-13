"""Shared FastAPI dependencies: DB session + multi-tenant authentication.

Every /api/* route (except /health and /api/tenants, which creates a
tenant) requires a valid tenant API key in the `X-API-Key` header when
`REQUIRE_API_KEY=true` (the default). When `REQUIRE_API_KEY=false`, a
"default" tenant is used implicitly — convenient for local single-user
experimentation without setting up a tenant first.
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db.session import TenantRecord, get_session
from ..models.schemas import Tenant

DEFAULT_TENANT_ID = "tenant_default"
DEFAULT_TENANT_NAME = "default"

__all__ = ["get_session", "get_current_tenant"]


def get_current_tenant(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_session),
) -> Tenant:
    settings = get_settings()

    if not settings.require_api_key:
        return Tenant(id=DEFAULT_TENANT_ID, name=DEFAULT_TENANT_NAME, api_key="")

    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header. Create a tenant via POST /api/tenants first.")

    record = db.query(TenantRecord).filter(TenantRecord.api_key == x_api_key).first()
    if record is None:
        raise HTTPException(status_code=401, detail="Invalid API key.")

    return Tenant(id=record.id, name=record.name, api_key=record.api_key, created_at=record.created_at)
