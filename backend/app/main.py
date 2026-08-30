import sys
import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .db import Base, engine
from .api.routes import r
from .core.config import settings

# --- WINDOWS PLAYWRIGHT FIX ---
# Playwright's subprocess transport needs the Proactor loop on Windows.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
# ------------------------------

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("avaas")


@asynccontextmanager
async def life(app):
    # In development we can create tables directly for zero-setup local runs.
    # In production (or whenever AUTO_CREATE_TABLES=false) Alembic owns the schema:
    #   alembic upgrade head
    if settings().app_env == "development" and settings().auto_create_tables:
        async with engine.begin() as c:
            await c.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title=settings().app_name, version="3.0.0", lifespan=life)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().cors,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id(request: Request, call_next):
    """Attach a correlation/request id to every request for traceable logging."""
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    try:
        response = await call_next(request)
    except Exception:
        # Never leak internals/secrets in an error body; log with the request id.
        logger.exception("Unhandled error [request_id=%s]", rid)
        return JSONResponse(status_code=500, content={"detail": "Internal server error", "request_id": rid})
    response.headers["X-Request-ID"] = rid
    return response


app.include_router(r)


@app.get("/health")
def health():
    return {"status": "ok"}
