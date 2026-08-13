"""FastAPI application entry point.

Run with:
    uvicorn avaas.main:app --reload --host 0.0.0.0 --port 8000

or simply:
    python -m avaas.main
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.routes_agents import router as agents_router
from .api.routes_health import router as health_router
from .api.routes_runs import router as runs_router
from .config import get_settings
from .db.session import init_db
from .logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info(
        "AVaaS started | env=%s | llm_provider=%s | db=%s",
        settings.app_env,
        settings.llm_provider,
        settings.database_url,
    )
    yield


app = FastAPI(
    title="AVaaS - Agent Validator as a Service",
    description="Multi-tenant platform to test, evaluate, compare, and monitor AI agents before release.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(agents_router)
app.include_router(runs_router)

_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if _FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="dashboard")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("avaas.main:app", host=settings.host, port=settings.port, reload=(settings.app_env == "development"))

