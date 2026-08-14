import sys
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .db import Base,engine
from .api.routes import r
from .core.config import settings

# --- WINDOWS PLAYWRIGHT FIX ---
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
# ------------------------------

@asynccontextmanager
async def life(app):
 if settings().app_env=='development':
  async with engine.begin() as c:await c.run_sync(Base.metadata.create_all)
 yield
 
app=FastAPI(title=settings().app_name,version='2.0.0',lifespan=life)
app.add_middleware(CORSMiddleware,allow_origins=settings().cors,allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
app.include_router(r)

@app.get('/health')
def health():return {'status':'ok'}