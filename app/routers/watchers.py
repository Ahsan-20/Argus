"""Watcher endpoints: the Commissioner flow and fleet management.

Creating a probe is deliberately two steps. POST /watchers runs the
Commissioner and returns a parsed spec WITHOUT writing anything, so the user
can see exactly what the agent understood. POST /watchers/confirm launches it.
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..fetcher import UnsafeUrlError, assert_safe_url
from ..llm import LLMError, complete_json
from ..models import Event, Run, Watcher
from ..prompts import COMMISSIONER_PROMPT, COMMISSIONER_SCHEMA
from ..schemas import (
    ConfirmWatcherRequest,
    CreateWatcherRequest,
    RunOut,
    WatcherOut,
    WatcherSpec,
)
from ..tick import execute_watcher

router = APIRouter(prefix="/watchers", tags=["watchers"])
settings = get_settings()

MIN_CADENCE = 15
MAX_CADENCE = 1440


def _validated_url(url: str) -> str:
    """Reject unsafe or malformed targets before anything is stored."""
    url = (url or "").strip()
    try:
        assert_safe_url(url)
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=400, detail=f"unusable target: {exc}")
    return url


def _validated_email(email: str) -> str:
    email = (email or "").strip() or settings.owner_email
    if "@" not in email or " " in email:
        raise HTTPException(status_code=400, detail=f"invalid notify email: {email}")
    return email


def _next_callsign(db: Session) -> str:
    """Monotonic callsign (the model's own suggestion is advisory).

    Based on max id, not row count, so retiring a probe never causes a later
    probe to reuse an existing callsign.
    """
    top = db.query(func.max(Watcher.id)).scalar() or 0
    return f"PROBE-{top + 1:02d}"


@router.post("", response_model=WatcherSpec)
def parse_order(payload: CreateWatcherRequest, db: Session = Depends(get_db)):
    """Run the Commissioner on a plain-English order. Writes nothing."""
    sentence = (payload.sentence or "").strip()
    if not sentence:
        raise HTTPException(status_code=400, detail="empty watch order")

    try:
        spec = complete_json(
            system=COMMISSIONER_PROMPT,
            user=sentence,
            model=settings.gemini_model_commissioner,
            schema=COMMISSIONER_SCHEMA,
        )
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=f"Commissioner failed: {exc}")

    if not spec.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=spec.get("message") or "That is not a valid watch order.",
        )

    cadence = int(spec.get("cadence_minutes") or 30)
    return WatcherSpec(
        callsign=_next_callsign(db),
        url=_validated_url(spec.get("url", "")),
        condition=spec.get("condition", ""),
        cadence_minutes=max(MIN_CADENCE, min(MAX_CADENCE, cadence)),
        email=_validated_email(spec.get("email", "")),
    )


@router.post("/confirm", response_model=WatcherOut)
def launch(payload: ConfirmWatcherRequest, db: Session = Depends(get_db)):
    """Launch the confirmed probe into orbit."""
    active = (
        db.query(func.count(Watcher.id))
        .filter(Watcher.status.in_(("active", "triggered")))
        .scalar()
        or 0
    )
    if active >= settings.max_active_watchers:
        raise HTTPException(
            status_code=429,
            detail=f"fleet is full ({settings.max_active_watchers} probes)",
        )

    condition = (payload.condition or "").strip()
    if not condition:
        raise HTTPException(status_code=400, detail="watch condition is empty")

    watcher = Watcher(
        callsign=payload.callsign or _next_callsign(db),
        # Re-validated here, not just in parse: this endpoint is reachable
        # directly and must never accept an internal address.
        url=_validated_url(payload.url),
        condition=condition,
        cadence_minutes=max(MIN_CADENCE, min(MAX_CADENCE, payload.cadence_minutes)),
        email=_validated_email(payload.email),
        status="active",
        next_run_at=datetime.now(timezone.utc),  # first pass on the next tick
    )
    db.add(watcher)
    db.commit()
    db.refresh(watcher)

    db.add(
        Event(
            watcher_id=watcher.id,
            type="created",
            payload=json.dumps({"url": watcher.url, "condition": watcher.condition}),
        )
    )
    db.commit()
    return watcher


@router.get("", response_model=list[WatcherOut])
def list_watchers(db: Session = Depends(get_db)):
    return db.query(Watcher).order_by(Watcher.id.desc()).all()


@router.get("/{watcher_id}", response_model=WatcherOut)
def get_watcher(watcher_id: int, db: Session = Depends(get_db)):
    watcher = db.get(Watcher, watcher_id)
    if not watcher:
        raise HTTPException(status_code=404, detail="no such probe")
    return watcher


@router.get("/{watcher_id}/runs", response_model=list[RunOut])
def mission_log(watcher_id: int, limit: int = 50, db: Session = Depends(get_db)):
    """Every pass this probe has made, newest first."""
    if not db.get(Watcher, watcher_id):
        raise HTTPException(status_code=404, detail="no such probe")
    return (
        db.query(Run)
        .filter(Run.watcher_id == watcher_id)
        .order_by(Run.id.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )


@router.post("/{watcher_id}/run-now", response_model=RunOut)
def run_now(watcher_id: int, db: Session = Depends(get_db)):
    """Ping a probe immediately, without waiting for its next scheduled pass.

    Does not shift next_run_at: a manual ping is extra, not a replacement.
    """
    watcher = db.get(Watcher, watcher_id)
    if not watcher:
        raise HTTPException(status_code=404, detail="no such probe")
    return execute_watcher(db, watcher)


def _set_status(db: Session, watcher_id: int, status: str) -> Watcher:
    watcher = db.get(Watcher, watcher_id)
    if not watcher:
        raise HTTPException(status_code=404, detail="no such probe")
    watcher.status = status
    if status == "active":
        watcher.next_run_at = datetime.now(timezone.utc)
    db.add(Event(watcher_id=watcher.id, type=status))
    db.commit()
    db.refresh(watcher)
    return watcher


@router.post("/{watcher_id}/pause", response_model=WatcherOut)
def pause(watcher_id: int, db: Session = Depends(get_db)):
    return _set_status(db, watcher_id, "paused")


@router.post("/{watcher_id}/resume", response_model=WatcherOut)
def resume(watcher_id: int, db: Session = Depends(get_db)):
    """Resume re-arms a probe, including one that already triggered."""
    return _set_status(db, watcher_id, "active")


@router.delete("/{watcher_id}")
def retire(watcher_id: int, db: Session = Depends(get_db)):
    watcher = db.get(Watcher, watcher_id)
    if not watcher:
        raise HTTPException(status_code=404, detail="no such probe")
    db.delete(watcher)
    db.commit()
    return {"retired": watcher_id}
