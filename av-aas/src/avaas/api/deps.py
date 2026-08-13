"""Shared FastAPI dependencies."""
from __future__ import annotations

from ..db.session import get_session  # re-exported for convenience

__all__ = ["get_session"]
