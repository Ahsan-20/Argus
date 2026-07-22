"""Demo endpoints: the public target page, the presence pulse, and seeding."""

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .. import demo
from ..db import get_db
from ..deps import require_access
from ..models import Watcher
from ..tick import execute_watcher

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/target", response_class=HTMLResponse)
def demo_target(db: Session = Depends(get_db)) -> str:
    """Public page a demo probe watches. Its state cycles automatically."""
    return demo.render_target_html(db)


@router.post("/pulse", dependencies=[Depends(require_access)])
def demo_pulse(db: Session = Depends(get_db)) -> dict:
    """Called by the frontend on load: advance the demo and run its probes now.

    Presence based, so the site looks alive the moment a grader opens it,
    without burning API quota when nobody is watching.
    """
    changed = demo.advance_cycle(db)
    ran = []
    due = (
        db.query(Watcher)
        .filter(Watcher.is_demo.is_(True), Watcher.status == "active")
        .all()
    )
    for w in due:
        callsign = w.callsign
        run = execute_watcher(db, w)
        ran.append({"callsign": callsign, "met": run.verdict_met, "error": run.error})
    return {"cycled": changed, "ran": ran}


@router.post("/seed", dependencies=[Depends(require_access)])
def demo_seed(db: Session = Depends(get_db)) -> dict:
    """Seed the demo fleet if it is not already present (idempotent)."""
    created = demo.seed_fleet(db)
    return {"seeded": created}
