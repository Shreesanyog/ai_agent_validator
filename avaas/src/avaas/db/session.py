"""SQLAlchemy engine/session setup and ORM models.

AVaaS is multi-tenant: every agent and run row carries a `tenant_id` and is
always queried scoped to the authenticated tenant (see `api/deps.py`). This
is application-level (row-level) tenant isolation rather than
database-per-tenant — appropriate for the MVP scale, and swappable for a
schema-per-tenant or database-per-tenant model later (see README
"Scalability" section) without touching the rest of the codebase, since all
access goes through this module.

Rows are stored as JSON blobs for the richer nested objects (AgentSpec,
RunReport) rather than fully normalized tables — this keeps the schema
trivial to evolve while still giving real, queryable persistence (SQLite by
default, swappable via DATABASE_URL for Postgres/MySQL in production).
"""
from __future__ import annotations

from sqlalchemy import Boolean, Column, Float, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from ..config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class TenantRecord(Base):
    __tablename__ = "tenants"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    api_key = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(Float, nullable=False)


class AgentRecord(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    created_at = Column(Float, nullable=False)
    spec_json = Column(Text, nullable=False)


class RunRecord(Base):
    __tablename__ = "runs"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    agent_id = Column(String, nullable=False, index=True)
    created_at = Column(Float, nullable=False)
    is_baseline = Column(Boolean, default=False, nullable=False)
    pass_rate = Column(Float, nullable=False)
    avg_score = Column(Float, nullable=False)
    release_gate = Column(String, nullable=False)
    report_json = Column(Text, nullable=False)


def init_db() -> None:
    """Create tables if they do not already exist. Safe to call repeatedly."""
    Base.metadata.create_all(bind=engine)


def get_session():
    """FastAPI dependency yielding a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
