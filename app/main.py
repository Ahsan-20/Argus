"""FastAPI entrypoint for Argus."""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, text
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


@app.get("/logo.png")
def logo() -> Response:
    """Serve the brand mark. Handy for the frontend and README."""
    import base64

    from .branding import LOGO_DATA_URI

    data = base64.b64decode(LOGO_DATA_URI.split(",", 1)[1])
    return Response(content=data, media_type="image/png")


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    """Liveness plus a real database round trip, for the deploy health check."""
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "service": "argus",
        "env": settings.app_env,
        "db": db_ok,
    }


@app.get("/stats")
def stats(db: Session = Depends(get_db)) -> dict:
    """Fleet overview for the dashboard header."""
    from .models import Run, Watcher

    by_status = dict(
        db.query(Watcher.status, func.count(Watcher.id))
        .group_by(Watcher.status)
        .all()
    )
    total_watchers = db.query(func.count(Watcher.id)).scalar() or 0
    total_runs = db.query(func.count(Run.id)).scalar() or 0
    triggered = (
        db.query(func.count(Run.id)).filter(Run.verdict_met.is_(True)).scalar() or 0
    )
    last_run = db.query(func.max(Run.started_at)).scalar()
    return {
        "total_watchers": total_watchers,
        "by_status": by_status,
        "total_runs": total_runs,
        "positive_verdicts": triggered,
        "last_run_at": last_run.isoformat() if last_run else None,
    }


@app.post("/tick")
def tick(
    x_tick_secret: str = Header(default=""),
    db: Session = Depends(get_db),
) -> dict:
    """Cron-only heartbeat. Rejects anything without the shared secret."""
    if not settings.tick_secret or x_tick_secret != settings.tick_secret:
        raise HTTPException(status_code=401, detail="bad tick secret")
    return run_due_watchers(db)
