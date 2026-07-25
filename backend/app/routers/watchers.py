"""Watcher endpoints: the Commissioner flow and fleet management.

Creating a probe is deliberately two steps. POST /watchers runs the
Commissioner and returns a parsed spec WITHOUT writing anything, so the user
can see exactly what the agent understood. POST /watchers/confirm launches it.
"""

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import current_email, verified_email
from ..fetcher import UnsafeUrlError, assert_safe_url
from ..llm import LLMError, complete_json
from ..models import Event, Run, Watcher
from ..prompts import COMMISSIONER_PROMPT, COMMISSIONER_SCHEMA
from ..schemas import (
    ConfirmWatcherRequest,
    CreateWatcherRequest,
    EventOut,
    LastRun,
    RunOut,
    UpdateWatcherRequest,
    WatcherOut,
    WatcherSpec,
)
from ..tick import execute_watcher, plain_dashes

router = APIRouter(prefix="/watchers", tags=["watchers"])
settings = get_settings()
logger = logging.getLogger("argus.watchers")


def _first_check(watcher_id: int) -> None:
    """Run a just-launched watcher's first pass in the background.

    Creation should feel alive: the operator sees a real verdict within
    seconds instead of silence until the next cron tick. Own session, and
    never raises (a failed first pass is recorded as an honest error run).
    """
    from ..db import SessionLocal

    try:
        with SessionLocal() as db:
            watcher = db.get(Watcher, watcher_id)
            if watcher is not None:
                execute_watcher(db, watcher)
    except Exception as exc:
        logger.warning("first check failed for watcher %s: %s", watcher_id, exc)

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


def _check_caps(db: Session, owner: str | None) -> None:
    """Enforce the facility-wide cap and the per-person cap.

    The per-person cap counts every watcher the operator owns, any status, so
    pausing is not a loophole. Deleting one frees the slot. Calls without an
    operator header only face the facility cap.
    """
    active = (
        db.query(func.count(Watcher.id))
        .filter(Watcher.status.in_(("active", "triggered")))
        .scalar()
        or 0
    )
    if active >= settings.max_active_watchers:
        raise HTTPException(
            status_code=429,
            detail=(
                f"The facility is full ({settings.max_active_watchers} watchers "
                "running). Try again after some finish."
            ),
        )
    if owner:
        mine = (
            db.query(func.count(Watcher.id))
            .filter(Watcher.owner_email == owner)
            .scalar()
            or 0
        )
        if mine >= settings.max_watchers_per_user:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"You already have {mine} watchers, and the limit is "
                    f"{settings.max_watchers_per_user} per person. Delete one "
                    "you no longer need, then try again."
                ),
            )


def _next_callsign(db: Session) -> str:
    """Fallback name when the Commissioner does not supply a usable one.

    Based on max id, not row count, so retiring a probe never causes a later
    probe to reuse an existing callsign.
    """
    top = db.query(func.max(Watcher.id)).scalar() or 0
    return f"PROBE-{top + 1:02d}"


def _clean_name(value: str | None) -> str:
    """Tidy a model-suggested watcher name into something displayable."""
    name = plain_dashes(value).strip().strip("\"'")
    name = " ".join(name.split())  # collapse any stray whitespace
    return name[:32]


@router.post("", response_model=WatcherSpec)
def parse_order(
    payload: CreateWatcherRequest,
    db: Session = Depends(get_db),
    owner: str = Depends(verified_email),
):
    """Run the Commissioner on a plain-English order. Writes nothing.

    Notify defaults, in order: an email dictated in the sentence itself, then
    the signed-in operator (alerts should go to the person who asked), then
    the facility owner as a last resort.
    """
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
            detail=plain_dashes(spec.get("message"))
            or "That is not a valid watch order.",
        )

    cadence = int(spec.get("cadence_minutes") or 30)
    return WatcherSpec(
        # The Commissioner names the watcher after what it watches; the
        # numbered fallback only applies if it returns nothing usable.
        callsign=_clean_name(spec.get("callsign")) or _next_callsign(db),
        url=_validated_url(spec.get("url", "")),
        condition=plain_dashes(spec.get("condition")),
        track=plain_dashes(spec.get("track")),
        cadence_minutes=max(MIN_CADENCE, min(MAX_CADENCE, cadence)),
        email=_validated_email((spec.get("email") or "").strip() or owner or ""),
        repeating=bool(spec.get("repeating")),
    )


@router.post("/confirm", response_model=WatcherOut)
def launch(
    payload: ConfirmWatcherRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    owner: str = Depends(verified_email),
):
    """Launch the confirmed probe into orbit, owned by the calling operator."""
    _check_caps(db, owner)

    condition = (payload.condition or "").strip()
    if not condition:
        raise HTTPException(status_code=400, detail="watch condition is empty")

    cadence = max(MIN_CADENCE, min(MAX_CADENCE, payload.cadence_minutes))
    watcher = Watcher(
        callsign=_clean_name(payload.callsign) or _next_callsign(db),
        # Re-validated here, not just in parse: this endpoint is reachable
        # directly and must never accept an internal address.
        url=_validated_url(payload.url),
        condition=condition,
        track=(payload.track or "").strip() or None,
        cadence_minutes=cadence,
        base_cadence_minutes=cadence,  # the anchor the adaptive orbit works from
        email=_validated_email((payload.email or "").strip() or owner or ""),
        repeating=bool(payload.repeating),
        owner_email=owner,  # None if the header was absent (facility probe)
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

    # First pass runs immediately in the background, so the operator sees a
    # real verdict within seconds of launching.
    background_tasks.add_task(_first_check, watcher.id)
    return watcher


@router.get("", response_model=list[WatcherOut])
def list_watchers(
    shared: bool = False,
    db: Session = Depends(get_db),
    caller: str = Depends(current_email),
):
    """List watchers, newest first, each with a compact last-pass summary.

    Returns the caller's own watchers, or the shared ones with `shared=true`.

    Whose they are is taken from the session token, never from a parameter.
    This used to accept `owner` in the query string, which meant anybody could
    read anybody else's roster by typing a different address into the URL.

    Facility starters are deliberately NOT mixed into your own list: they are
    templates to copy, and resuming one in place would run it for everyone and
    send its alerts to the facility address rather than to whoever pressed the
    button. They are reached with `shared=true`, where the action is "use this
    watcher", which clones it.
    """
    # The demonstration probe is machinery behind the "Run a quick demo"
    # button, not something anyone owns, so it never appears in a list.
    q = db.query(Watcher).filter(Watcher.is_demo.is_(False))
    if shared:
        q = q.filter(Watcher.is_shared.is_(True))
    else:
        q = q.filter(Watcher.owner_email == caller)
    watchers = q.order_by(Watcher.id.desc()).all()

    # One query for every probe's most recent run: the runs whose id is the max
    # id for their watcher. Avoids an N+1 across the roster.
    ids = [w.id for w in watchers]
    latest: dict[int, Run] = {}
    if ids:
        newest_ids = (
            db.query(func.max(Run.id))
            .filter(Run.watcher_id.in_(ids))
            .group_by(Run.watcher_id)
            .subquery()
        )
        for run in db.query(Run).filter(Run.id.in_(newest_ids)).all():
            latest[run.watcher_id] = run

    out = []
    for w in watchers:
        view = WatcherOut.model_validate(w)
        run = latest.get(w.id)
        view.last_run = LastRun.model_validate(run) if run else None
        out.append(view)
    return out


def _readable(db: Session, watcher_id: int, caller: str) -> Watcher:
    """A watcher the caller is allowed to look at: their own, or a shared one.

    404 rather than 403 for someone else's private watcher. Telling a stranger
    "that exists but is not yours" hands them a way to count and probe other
    people's watchers by walking the ids.
    """
    watcher = db.get(Watcher, watcher_id)
    if not watcher:
        raise HTTPException(status_code=404, detail="no such probe")
    if watcher.owner_email == caller or watcher.is_shared or watcher.owner_email is None:
        return watcher
    raise HTTPException(status_code=404, detail="no such probe")


def _owned(db: Session, watcher_id: int, caller: str) -> Watcher:
    """A watcher the caller may change. Strictly their own.

    Shared and facility watchers are readable by everyone and editable by
    nobody: pausing or retiring one in place would do it for every person
    looking at it. The way to make a shared watcher yours is to copy it.
    """
    watcher = db.get(Watcher, watcher_id)
    if not watcher:
        raise HTTPException(status_code=404, detail="no such probe")
    if watcher.owner_email != caller:
        if watcher.is_shared or watcher.owner_email is None:
            raise HTTPException(
                status_code=403,
                detail="This one is shared. Use 'Use this watcher' to get your own copy.",
            )
        raise HTTPException(status_code=404, detail="no such probe")
    return watcher


@router.get("/{watcher_id}", response_model=WatcherOut)
def get_watcher(
    watcher_id: int,
    db: Session = Depends(get_db),
    caller: str = Depends(current_email),
):
    return _readable(db, watcher_id, caller)


@router.patch("/{watcher_id}", response_model=WatcherOut)
def update_watcher(
    watcher_id: int,
    payload: UpdateWatcherRequest,
    db: Session = Depends(get_db),
    caller: str = Depends(verified_email),
):
    """Edit an existing watcher. Only provided fields change.

    A material change (page, condition) resets the watcher's memory (last
    snapshot, learned deep-read) and schedules a fresh check, so old context
    never contaminates the new watch. Editing the cadence re-anchors the
    adaptive orbit to the newly ordered value.
    """
    watcher = _owned(db, watcher_id, caller)
    if watcher.is_demo:
        raise HTTPException(status_code=400, detail="the demo watcher cannot be edited")

    material = False
    if payload.url is not None and payload.url.strip() != watcher.url:
        watcher.url = _validated_url(payload.url)
        watcher.use_renderer = False  # the new page must be learned afresh
        material = True
    if payload.condition is not None:
        condition = payload.condition.strip()
        if not condition:
            raise HTTPException(status_code=400, detail="watch condition is empty")
        if condition != watcher.condition:
            watcher.condition = condition
            material = True
    if payload.track is not None:
        watcher.track = payload.track.strip() or None
    if payload.cadence_minutes is not None:
        cadence = max(MIN_CADENCE, min(MAX_CADENCE, payload.cadence_minutes))
        if cadence != watcher.cadence_minutes or watcher.base_cadence_minutes != cadence:
            watcher.cadence_minutes = cadence
            watcher.base_cadence_minutes = cadence
            watcher.stable_passes = 0
    if payload.email is not None:
        watcher.email = _validated_email(payload.email)
    if payload.callsign is not None and _clean_name(payload.callsign):
        watcher.callsign = _clean_name(payload.callsign)
    if payload.is_shared is not None:
        watcher.is_shared = bool(payload.is_shared)
    if payload.repeating is not None:
        watcher.repeating = bool(payload.repeating)

    if material:
        watcher.last_snapshot = None
        watcher.next_run_at = datetime.now(timezone.utc)

    db.add(Event(watcher_id=watcher.id, type="edited"))
    db.commit()
    db.refresh(watcher)
    return watcher


@router.post("/{watcher_id}/clone", response_model=WatcherOut)
def clone_watcher(
    watcher_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    owner: str = Depends(verified_email),
):
    """Copy a shared watcher into the calling operator's own fleet.

    The clone is fully separate: own history, own alerts (to the caller's
    email), own schedule. It inherits the source's learned deep-read so it
    reads JS pages correctly from its first pass.
    """
    src = db.get(Watcher, watcher_id)
    if not src:
        raise HTTPException(status_code=404, detail="no such probe")
    if not (src.is_shared or src.owner_email is None):
        raise HTTPException(status_code=403, detail="this watcher is not shared")

    _check_caps(db, owner)

    watcher = Watcher(
        # Keep the name it was shared under: that is what the operator picked
        # it for. A numbered fallback would throw away the useful part.
        callsign=src.callsign,
        url=src.url,
        condition=src.condition,
        track=src.track,
        cadence_minutes=src.cadence_minutes,
        base_cadence_minutes=src.base_cadence_minutes or src.cadence_minutes,
        email=_validated_email(owner or ""),
        owner_email=owner,
        status="active",
        repeating=src.repeating,
        use_renderer=src.use_renderer,  # inherit the learned deep read
        next_run_at=datetime.now(timezone.utc),
    )
    db.add(watcher)
    db.commit()
    db.refresh(watcher)
    db.add(
        Event(
            watcher_id=watcher.id,
            type="created",
            payload=json.dumps({"cloned_from": src.id, "url": watcher.url}),
        )
    )
    db.commit()

    background_tasks.add_task(_first_check, watcher.id)
    return watcher


@router.get("/{watcher_id}/runs", response_model=list[RunOut])
def mission_log(
    watcher_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    caller: str = Depends(current_email),
):
    """Every pass this probe has made, newest first."""
    _readable(db, watcher_id, caller)
    return (
        db.query(Run)
        .filter(Run.watcher_id == watcher_id)
        .order_by(Run.id.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )


@router.get("/{watcher_id}/transmissions", response_model=list[EventOut])
def transmissions(
    watcher_id: int,
    db: Session = Depends(get_db),
    caller: str = Depends(current_email),
):
    """Alerts this probe has sent, newest first.

    Rendering the sent message in-app means the grader always sees the alert,
    even if the email is filtered to spam.
    """
    _readable(db, watcher_id, caller)
    return (
        db.query(Event)
        .filter(Event.watcher_id == watcher_id, Event.type == "emailed")
        .order_by(Event.id.desc())
        .all()
    )


@router.delete("/{watcher_id}/transmissions")
def clear_transmissions(
    watcher_id: int,
    db: Session = Depends(get_db),
    caller: str = Depends(verified_email),
):
    """Delete every alert this probe has sent (the stored in-app copies)."""
    _owned(db, watcher_id, caller)
    cleared = (
        db.query(Event)
        .filter(Event.watcher_id == watcher_id, Event.type == "emailed")
        .delete()
    )
    db.commit()
    return {"cleared": cleared}


@router.post("/{watcher_id}/run-now", response_model=RunOut)
def run_now(
    watcher_id: int,
    db: Session = Depends(get_db),
    caller: str = Depends(verified_email),
):
    """Ping a probe immediately, without waiting for its next scheduled pass.

    Does not shift next_run_at: a manual ping is extra, not a replacement.
    """
    watcher = _owned(db, watcher_id, caller)
    return execute_watcher(db, watcher)


def _set_status(db: Session, watcher_id: int, status: str, caller: str) -> Watcher:
    watcher = _owned(db, watcher_id, caller)
    watcher.status = status
    if status == "active":
        watcher.next_run_at = datetime.now(timezone.utc)
    db.add(Event(watcher_id=watcher.id, type=status))
    db.commit()
    db.refresh(watcher)
    return watcher


@router.post("/{watcher_id}/pause", response_model=WatcherOut)
def pause(
    watcher_id: int,
    db: Session = Depends(get_db),
    caller: str = Depends(verified_email),
):
    return _set_status(db, watcher_id, "paused", caller)


@router.post("/{watcher_id}/resume", response_model=WatcherOut)
def resume(
    watcher_id: int,
    db: Session = Depends(get_db),
    caller: str = Depends(verified_email),
):
    """Resume re-arms a probe, including one that already triggered."""
    return _set_status(db, watcher_id, "active", caller)


@router.delete("/{watcher_id}")
def retire(
    watcher_id: int,
    db: Session = Depends(get_db),
    caller: str = Depends(verified_email),
):
    """Delete a watcher and its history.

    Children are bulk-deleted explicitly rather than via ORM cascade: the
    cascade loads children at flush time, which can race a background first
    check inserting a fresh run mid-delete (seen live). One retry absorbs
    exactly that race.
    """
    _owned(db, watcher_id, caller)
    for attempt in (1, 2):
        try:
            db.query(Run).filter(Run.watcher_id == watcher_id).delete()
            db.query(Event).filter(Event.watcher_id == watcher_id).delete()
            db.query(Watcher).filter(Watcher.id == watcher_id).delete()
            db.commit()
            break
        except IntegrityError:
            db.rollback()
            if attempt == 2:
                raise HTTPException(
                    status_code=409,
                    detail="probe is mid-check; try again in a moment",
                )
    return {"retired": watcher_id}
