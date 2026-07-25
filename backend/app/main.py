"""FastAPI entrypoint for Argus."""

import logging
from contextlib import asynccontextmanager

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Response,
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from .config import get_settings
from .db import SessionLocal, get_db, init_db
from .deps import optional_user
from . import scheduler
from .routers import accounts as accounts_router
from .routers import demo as demo_router
from .routers import watchers
from .tick import claim_due_watchers

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from . import demo

    # The seed account is not part of demo mode: it is what gives the existing
    # watchers an owner who can actually sign in, so it runs regardless.
    with SessionLocal() as db:
        demo.ensure_seed_account(db)

    # Seed the real fleet (genuine sites) and the on-demand demonstration probe
    # so the deployed dashboard is populated and ready.
    if settings.demo_mode:
        with SessionLocal() as db:
            demo.ensure_real_fleet(db)
            demo.ensure_demo_probe(db)

    # Argus runs its own schedule from here. POST /tick still works as a manual
    # trigger and as a fallback.
    task = scheduler.start(app)
    try:
        yield
    finally:
        await scheduler.stop(task)


app = FastAPI(title="Argus", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Every watcher endpoint authenticates for itself, because they do not all
# want the same thing: reading tolerates an unverified account, creating does
# not, and each one has to know WHO is asking to check ownership. A blanket
# router dependency could only have answered "is anyone signed in".
app.include_router(accounts_router.router)
app.include_router(watchers.router)
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
def stats(
    db: Session = Depends(get_db),
    caller=Depends(optional_user),
) -> dict:
    """Fleet overview for the dashboard header and the public landing ticker.

    Counts only, no private data, so it is safe to serve without the access
    code. The frontend ticker and settings page read the budget and channels
    from here rather than guessing.
    """
    from datetime import datetime, timezone

    from .models import BudgetCounter, Run, Watcher

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

    # The same figures narrowed to whoever is asking. The dashboard greets
    # someone by name and then shows these, so facility-wide totals there read
    # as personal ones: a page saying "you are using 3 of your 5" sat directly
    # above a card claiming 10 watchers. Null for anonymous callers, which is
    # what the public landing page wants.
    owner = caller.email if caller else None
    mine = None
    if owner:
        owned = db.query(Watcher.id).filter(Watcher.owner_email == owner).subquery()
        mine = {
            "total_watchers": db.query(func.count(Watcher.id))
            .filter(Watcher.owner_email == owner)
            .scalar()
            or 0,
            "active_watchers": db.query(func.count(Watcher.id))
            .filter(Watcher.owner_email == owner, Watcher.status == "active")
            .scalar()
            or 0,
            "total_runs": db.query(func.count(Run.id))
            .filter(Run.watcher_id.in_(db.query(owned.c.id)))
            .scalar()
            or 0,
            "positive_verdicts": db.query(func.count(Run.id))
            .filter(
                Run.watcher_id.in_(db.query(owned.c.id)),
                Run.verdict_met.is_(True),
            )
            .scalar()
            or 0,
        }

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    counter = db.get(BudgetCounter, today)
    used = counter.gemini_calls if counter else 0
    return {
        "total_watchers": total_watchers,
        "by_status": by_status,
        "total_runs": total_runs,
        "positive_verdicts": triggered,
        "mine": mine,
        "last_run_at": last_run.isoformat() if last_run else None,
        "llm_budget": {"used": used, "limit": settings.llm_daily_budget},
        "channels": {"email": True, "whatsapp": settings.whatsapp_enabled},
        # So the UI can show usage before someone hits the wall.
        "limits": {
            "per_user": settings.max_watchers_per_user,
            "facility": settings.max_active_watchers,
        },
    }


@app.post("/pulse")
def pulse() -> dict:
    """Presence beacon the console pings on load and while the tab is visible.

    Deliberately costless: it spends no LLM budget and never fires the demo
    (that stays strictly on-demand for integrity). Its only job is to wake the
    sleeping free instance so an unattended visitor meets a warm backend. The
    real fleet on the cron tick is what keeps the mission log genuinely fresh.
    """
    return {"ok": True, "service": "argus"}


def _process_claimed(watcher_ids: list[int]) -> None:
    """Run each claimed watcher on its own session, never raising."""
    from .models import Watcher
    from .tick import execute_watcher

    for watcher_id in watcher_ids:
        try:
            with SessionLocal() as db:
                watcher = db.get(Watcher, watcher_id)
                if watcher is not None:
                    execute_watcher(db, watcher)
        except Exception as exc:
            logging.getLogger("argus.tick").warning(
                "tick: watcher %s failed: %s", watcher_id, exc
            )


@app.post("/tick")
def tick(
    background_tasks: BackgroundTasks,
    x_tick_secret: str = Header(default=""),
    db: Session = Depends(get_db),
) -> dict:
    """Cron-only heartbeat. Rejects anything without the shared secret.

    Due watchers are claimed synchronously, which is the part that must not be
    lost, then executed after the response is sent. A pass costs several
    seconds of model latency, so doing the work inline made the endpoint take
    roughly eight seconds per watcher: measured at 24 seconds for three. Cron
    services time out well before that and start reporting the job as failing,
    so the claim is the transaction and the work is the follow-up.
    """
    if not settings.tick_secret or x_tick_secret != settings.tick_secret:
        raise HTTPException(status_code=401, detail="bad tick secret")
    claimed = claim_due_watchers(db)
    background_tasks.add_task(_process_claimed, claimed)
    return {"claimed": len(claimed), "status": "running"}
