"""FastAPI application entry point.

Run with:
    uvicorn avaas.main:app --reload --host 0.0.0.0 --port 8000

or simply:
    python -m avaas.main

The React dashboard (frontend/) is a separate Vite dev server during
development (`npm run dev`, see README) and is optionally mounted here as
static files once built (`npm run build` -> frontend/dist/) for a
single-process deployment.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.routes_agents import router as agents_router
from .api.routes_health import router as health_router
from .api.routes_requirements import router as requirements_router
from .api.routes_runs import router as runs_router
from .api.routes_tenants import router as tenants_router
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
        "AVaaS started | env=%s | llm_provider=%s | db=%s | require_api_key=%s",
        settings.app_env,
        settings.llm_provider,
        settings.database_url,
        settings.require_api_key,
    )
    yield


app = FastAPI(
    title="AVaaS - Agent Validator as a Service",
    description="Multi-tenant platform to test, evaluate, compare, and monitor AI agents before release.",
    version="0.2.0",
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
app.include_router(tenants_router)
app.include_router(agents_router)
app.include_router(runs_router)
app.include_router(requirements_router)

# Serve the built React dashboard if it has been built (frontend/dist/).
# During development, run the Vite dev server separately (see README) - it
# proxies API calls to this backend, so this mount is not used in that mode.
_FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="dashboard")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("avaas.main:app", host=settings.host, port=settings.port, reload=(settings.app_env == "development"))
