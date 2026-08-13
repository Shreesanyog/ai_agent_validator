"""SQLAlchemy engine/session setup and ORM models.

AVaaS persists two kinds of rows:
  * agents  - the onboarded AgentSpec (as JSON)
  * runs    - the full RunReport produced by a validation run (as JSON)

Reports are stored as JSON blobs rather than fully normalized tables. For a
hackathon-scale MVP this keeps the schema trivial to evolve while still
giving real persistence (SQLite by default, swappable via DATABASE_URL for
Postgres/MySQL in production).
"""
from __future__ import annotations

from sqlalchemy import Column, Float, String, Text, Boolean, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from ..config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class AgentRecord(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(Float, nullable=False)
    spec_json = Column(Text, nullable=False)


class RunRecord(Base):
    __tablename__ = "runs"

    id = Column(String, primary_key=True)
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
