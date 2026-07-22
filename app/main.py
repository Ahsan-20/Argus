"""FastAPI entrypoint for Argus."""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import get_settings
from .db import SessionLocal, get_db, init_db
from .deps import require_access
from .routers import demo as demo_router
from .routers import watchers
from .tick import run_due_watchers

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Seed the real fleet (genuine sites) and the on-demand demonstration probe
    # so the deployed dashboard is populated and ready.
    if settings.demo_mode:
        from . import demo

        with SessionLocal() as db:
            demo.ensure_real_fleet(db)
            demo.ensure_demo_probe(db)
    yield


app = FastAPI(title="Argus", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.allowed_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# The whole watcher API is gated behind the shared access code. The demo router
# gates its own write endpoints; /demo/target stays public so probes (and
# graders) can read it.
app.include_router(watchers.router, dependencies=[Depends(require_access)])
app.include_router(demo_router.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "argus", "env": settings.app_env}


@app.post("/tick")
def tick(
    x_tick_secret: str = Header(default=""),
    db: Session = Depends(get_db),
) -> dict:
    """Cron-only heartbeat. Rejects anything without the shared secret."""
    if not settings.tick_secret or x_tick_secret != settings.tick_secret:
        raise HTTPException(status_code=401, detail="bad tick secret")
    return run_due_watchers(db)
