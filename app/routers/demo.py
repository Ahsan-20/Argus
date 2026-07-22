"""Demo endpoints: the public target page and the on-demand demonstration."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .. import demo
from ..db import get_db
from ..deps import require_access
from ..models import Event
from ..schemas import RunOut
from ..tick import execute_watcher

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/target", response_class=HTMLResponse)
def demo_target(db: Session = Depends(get_db)) -> str:
    """Public, clearly-labelled demonstration page the demo probe watches."""
    return demo.render_target_html(db)


@router.post("/run", dependencies=[Depends(require_access)])
def demo_run(db: Session = Depends(get_db)) -> dict:
    """Run a live demonstration on command.

    Opens the synthetic target, runs the demonstration probe once so the user
    watches it fetch, reason and trigger, then returns the run and the alert
    that would have been sent (rendered in-app, never emailed). Finally it
    resets the target and the probe so the demo is repeatable.
    """
    probe = demo.ensure_demo_probe(db)
    demo.set_slots(db, 3)  # slots are now open
    probe.status = "active"
    probe.next_run_at = datetime.now(timezone.utc)
    db.commit()

    run = execute_watcher(db, probe)  # fetches demo target, judges, triggers

    alert = None
    ev = (
        db.query(Event)
        .filter(Event.watcher_id == probe.id, Event.type == "emailed")
        .order_by(Event.id.desc())
        .first()
    )
    if ev and ev.payload:
        alert = json.loads(ev.payload)

    # Reset so the next press is a fresh demonstration.
    demo.set_slots(db, 0)
    probe.status = "standby"
    db.commit()

    return {
        "run": RunOut.model_validate(run).model_dump(mode="json"),
        "alert": alert,
        "note": "Demonstration only: the alert is shown here, not emailed.",
    }
