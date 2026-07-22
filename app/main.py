"""FastAPI entrypoint for Argus.

Day 1: app boots, health check, CORS, DB tables created, /tick secured. The
watcher CRUD and run loop land on days 1-3 per the plan.
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db, init_db
from .routers import watchers
from .tick import run_due_watchers

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Argus", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.allowed_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(watchers.router)


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


# TODO(day1-3): routers for /watchers (create, confirm, list, run-now, pause,
# resume, delete) and /demo (target, mutate, seed). Kept out of main to stay
# readable; add app.include_router(...) here as each lands.
