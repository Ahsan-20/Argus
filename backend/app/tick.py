"""The scheduler heartbeat and the run loop.

An external cron (cron-job.org) POSTs /tick every ~5 minutes. This both drives
runs and keeps a sleeping free instance awake. Due watchers are claimed
atomically so overlapping ticks can never run the same watcher twice.

A run never raises. Every failure (blocked target, empty page, provider
outage) is recorded as an honest error run and shown in the mission log,
because a probe reporting "target returned 403" is still the agent visibly
doing its job.
"""

import json
import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import get_settings
from .email_templates import category_of, render_alert_html
from .fetcher import (
    MIN_USEFUL_CHARS,
    BlockedByRobotsError,
    UnsafeUrlError,
    fetch_readable_text,
    fetch_rendered_text,
)
from .llm import complete_json
from .models import Event, Run, Watcher
from .notify import deliver_alert
from .prompts import HERALD_PROMPT, HERALD_SCHEMA, WATCHER_PROMPT, WATCHER_SCHEMA

settings = get_settings()
logger = logging.getLogger("argus.tick")

# The Watcher prompt already tells the model to prefer false negatives below
# 70. Enforcing it in code too means a badly behaved model cannot raise a
# false alarm on its own.
TRIGGER_CONFIDENCE = 70

# Consecutive failed passes before the owner is told the watcher is stuck.
# Three is enough to ride out a transient timeout or a brief outage without
# crying wolf, and soon enough that nobody waits weeks on a dead watch.
FAILURE_NOTICE_AFTER = 3

# MIN_USEFUL_CHARS comes from the fetcher: pages below it are reported as
# unusable rather than judged, because a verdict formed from a scrap of
# navigation chrome sounds confident while meaning nothing.

# Adaptive orbit bounds. A probe may tighten to half its ordered cadence when
# the target is moving and relax stepwise to four times it when the target is
# static, always inside the global 15..1440 clamp. Anchoring to the ordered
# cadence means the orbit can never drift arbitrarily far from what the
# operator asked for.
ORBIT_MIN = 15
ORBIT_MAX = 1440
ORBIT_TIGHTEN_DIV = 2
ORBIT_RELAX_MULT = 4
ORBIT_CALM_PASSES = 3  # unchanged passes required per relaxation step


def plan_orbit(
    base: int, current: int, stable_passes: int, changed: bool
) -> tuple[int, int, str | None]:
    """Decide the next cadence. Pure, so the policy is unit-testable.

    Returns (new_cadence, new_stable_passes, reason). reason is None when the
    cadence should not change.
    """
    lo = max(ORBIT_MIN, base // ORBIT_TIGHTEN_DIV)
    hi = min(ORBIT_MAX, base * ORBIT_RELAX_MULT)

    if changed:
        target = lo
        if target == current:
            return current, 0, None
        return target, 0, "target is moving, orbit tightened"

    stable_passes += 1
    if stable_passes < ORBIT_CALM_PASSES:
        return current, stable_passes, None
    # One relaxation step: half again slower, never past the ceiling. The
    # max(...) guard ensures progress even at tiny cadences (15 -> 22).
    target = min(hi, max(current + 1, current * 3 // 2))
    if target == current:
        return current, 0, None
    return target, 0, f"target static for {ORBIT_CALM_PASSES} passes, orbit relaxed"


def _adapt_orbit(db: Session, watcher: Watcher, changed: bool) -> None:
    """Let a probe manage its own cadence from what it observed.

    A moving target tightens the orbit; a static one relaxes it, saving LLM
    budget for pages that are actually changing. Every adjustment is recorded
    as an orbit_adjusted event so the autonomy stays visible, never silent.
    """
    if watcher.base_cadence_minutes is None:  # rows from before this feature
        watcher.base_cadence_minutes = watcher.cadence_minutes

    current = watcher.cadence_minutes
    new_cadence, new_streak, reason = plan_orbit(
        watcher.base_cadence_minutes, current, watcher.stable_passes or 0, changed
    )
    watcher.stable_passes = new_streak
    if reason is None:
        return
    watcher.cadence_minutes = new_cadence
    db.add(
        Event(
            watcher_id=watcher.id,
            type="orbit_adjusted",
            payload=json.dumps({"from": current, "to": new_cadence, "reason": reason}),
        )
    )
    logger.info(
        "PROBE %s orbit adjusted %s -> %s min (%s)",
        watcher.callsign, current, new_cadence, reason,
    )


def claim_due_watchers(db: Session) -> list[int]:
    """Atomically claim up to max_runs_per_tick due watchers.

    Bumps next_run_at forward in the same statement that selects them, so a
    second concurrent tick sees them as not-yet-due. Returns claimed ids.

    The atomic UPDATE ... RETURNING with SKIP LOCKED is Postgres-only. The
    SQLite dev fallback gets a plain read-then-update: single process, no
    concurrent cron, so the race the Postgres path defends against cannot
    happen there.
    """
    now = datetime.now(timezone.utc)

    # is_demo probes (the demonstration probe) never run on the schedule; they
    # only run when a user presses the demo button.
    if db.get_bind().dialect.name != "postgresql":
        due = (
            db.query(Watcher)
            .filter(
                Watcher.status == "active",
                Watcher.is_demo.is_(False),
                Watcher.next_run_at <= now,
            )
            .order_by(Watcher.next_run_at)
            .limit(settings.max_runs_per_tick)
            .all()
        )
        for w in due:
            w.next_run_at = now + timedelta(minutes=w.cadence_minutes)
        db.commit()
        return [w.id for w in due]

    rows = db.execute(
        text(
            """
            UPDATE watchers
               SET next_run_at = :now + (cadence_minutes || ' minutes')::interval
             WHERE id IN (
                   SELECT id FROM watchers
                    WHERE status = 'active' AND is_demo = false
                      AND next_run_at <= :now
                    ORDER BY next_run_at
                    LIMIT :cap
                   FOR UPDATE SKIP LOCKED
             )
            RETURNING id
            """
        ),
        {"now": now, "cap": settings.max_runs_per_tick},
    )
    ids = [r[0] for r in rows]
    db.commit()
    return ids


_DASHES = "—–"  # em dash, en dash


def plain_dashes(value: str | None) -> str:
    """Remove em and en dashes from model-written copy.

    The prompts forbid them, but models reach for em dashes constantly, so the
    house style is enforced in code too rather than trusted to instructions.
    A dash between digits is a range and becomes a hyphen; anywhere else it
    was standing in for a clause break and becomes a comma.

    Applied to what the model writes (alert subject and body, run reasoning
    and summaries). Never applied to quoted page evidence, which stays
    verbatim: it is the proof, not our prose.
    """
    if not value:
        return value or ""
    out = re.sub(rf"(?<=\d)\s*[{_DASHES}]\s*(?=\d)", "-", value)
    out = re.sub(rf"\s*[{_DASHES}]\s*", ", ", out)
    out = re.sub(r",\s*,", ",", out)  # a dash next to existing punctuation
    out = re.sub(r"\s+([.,;:!?])", r"\1", out)
    return re.sub(r"[ \t]{2,}", " ", out).strip()


def _build_watcher_input(watcher: Watcher, page_text: str) -> str:
    previous = watcher.last_snapshot or "(no previous pass)"
    track = watcher.track or "(nothing to track)"
    # The previous value is what makes "has this moved since last time"
    # answerable. Without it the model can only judge the page in isolation.
    last_value = watcher.previous_value or "(nothing recorded yet)"
    # A model has no clock. Without this line every time-relative watch is
    # unanswerable: "closes within a week", "before September", "expired".
    now = datetime.now(timezone.utc)
    return (
        f"TODAY'S DATE (UTC):\n{now.strftime('%A %d %B %Y, %H:%M')} UTC\n\n"
        f"WATCH CONDITION:\n{watcher.condition}\n\n"
        f"DATA POINT TO TRACK:\n{track}\n\n"
        f"PREVIOUS TRACKED VALUE:\n{last_value}\n\n"
        f"PREVIOUS PAGE SUMMARY:\n{previous}\n\n"
        f"CURRENT PAGE TEXT:\n{page_text}"
    )


def _unchanged_run(db: Session, watcher: Watcher, run: Run) -> Run:
    """Record a pass where the server said the page had not changed.

    No body was transferred and no model was called: the previous verdict
    still stands, because the page it was formed from is byte for byte the
    same. Recorded rather than skipped so the history stays honest about the
    watcher having looked.
    """
    previous = (
        db.query(Run)
        .filter(Run.watcher_id == watcher.id, Run.error.is_(None))
        .order_by(Run.id.desc())
        .first()
    )
    run.verdict_met = previous.verdict_met if previous else False
    run.confidence = previous.confidence if previous else 0
    run.evidence = previous.evidence if previous else None
    run.extracted = previous.extracted if previous else None
    run.page_summary = watcher.last_snapshot
    run.reasoning = (
        "The page has not changed since the last check: the server confirmed it "
        "with a not-modified response, so nothing needed re-reading."
    )
    watcher.consecutive_errors = 0
    db.add(run)
    db.commit()
    db.refresh(run)
    logger.info("PROBE %s unchanged (304), no model call", watcher.callsign)
    return run


def execute_watcher(db: Session, watcher: Watcher) -> Run:
    """Run one pass of a watcher: fetch, judge, record, maybe trigger."""
    from . import demo  # local import avoids a circular import at module load

    run = Run(watcher_id=watcher.id, started_at=datetime.now(timezone.utc))

    try:
        # The demo target is read straight from its DB state, so the AI judging
        # stays real without an HTTP round trip to our own (SSRF-blocked) URL.
        # What this watch is about, so an over-long page can be trimmed around
        # the relevant part rather than chopped at the front.
        focus = f"{watcher.condition} {watcher.track or ''}"
        if demo.is_demo_target(watcher.url):
            page_text = demo.target_text(db)
        elif watcher.use_renderer:
            # This probe learned on an earlier pass that its target's data
            # only appears after JavaScript runs: render first, plain second.
            page_text = fetch_rendered_text(watcher.url)
            if not page_text:
                page_text = fetch_readable_text(watcher.url, focus).text
        else:
            # Ask the server whether anything changed before asking for the
            # whole page again. A condition about timing can turn true while
            # the page sits still, so the shortcut is only taken when the page
            # was genuinely read recently.
            fresh_enough = (
                watcher.last_full_check_at is not None
                and (
                    datetime.now(timezone.utc) - watcher.last_full_check_at
                ).total_seconds()
                < settings.full_recheck_hours * 3600
            )
            result = fetch_readable_text(
                watcher.url,
                focus,
                etag=watcher.http_etag if fresh_enough else None,
                last_modified=watcher.http_last_modified if fresh_enough else None,
            )
            if result.not_modified:
                return _unchanged_run(db, watcher, run)
            page_text = result.text
            watcher.http_etag = result.etag
            watcher.http_last_modified = result.last_modified
            watcher.last_full_check_at = datetime.now(timezone.utc)

        if len(page_text.strip()) < MIN_USEFUL_CHARS:
            run.error = "page returned too little readable text to judge"
            run.verdict_met = False
            run.confidence = 0
            run.page_summary = watcher.last_snapshot  # keep the last good one
            run.reasoning = (
                "Target reachable but yielded no usable content "
                f"({len(page_text.strip())} characters). It is most likely "
                "JavaScript rendered or blocking automated access. No verdict "
                "claimed rather than guessing from navigation text."
            )
        else:
            meta: dict = {}
            verdict = complete_json(
                system=WATCHER_PROMPT,
                user=_build_watcher_input(watcher, page_text),
                model=settings.gemini_model_watcher,
                schema=WATCHER_SCHEMA,
                meta=meta,
            )
            run.verdict_met = bool(verdict.get("met"))
            run.confidence = int(verdict.get("confidence") or 0)
            # Evidence stays verbatim: it is the page's words, not ours.
            run.evidence = (verdict.get("evidence") or "")[:4000]
            run.extracted = ((verdict.get("extracted") or "").strip() or None)
            if run.extracted:
                run.extracted = run.extracted[:500]
            run.reasoning = plain_dashes(verdict.get("reasoning"))[:4000]
            run.page_summary = plain_dashes(verdict.get("page_summary"))[:2000]
            run.provider = meta.get("provider")
            run.model = meta.get("model")
            changed_flag = bool(verdict.get("changed"))

            # Deep read: the page read fine, but the tracked value was not in
            # the static text (a JS countdown, a client-rendered price). Try
            # once through the renderer; if that surfaces the data, adopt the
            # rendered verdict and remember, so future passes render first.
            if (
                watcher.track
                and not run.extracted
                and not watcher.use_renderer
                and not watcher.is_demo
            ):
                try:
                    deep_text = fetch_rendered_text(watcher.url)
                except UnsafeUrlError:
                    deep_text = ""
                if (
                    len(deep_text.strip()) >= MIN_USEFUL_CHARS
                    and deep_text.strip() != page_text.strip()
                ):
                    deep = None
                    meta2: dict = {}
                    try:
                        deep = complete_json(
                            system=WATCHER_PROMPT,
                            user=_build_watcher_input(watcher, deep_text),
                            model=settings.gemini_model_watcher,
                            schema=WATCHER_SCHEMA,
                            meta=meta2,
                        )
                    except Exception as exc:  # best-effort second opinion
                        logger.warning(
                            "deep read judge failed for %s: %s",
                            watcher.callsign,
                            exc,
                        )
                    adopted = deep and (
                        (deep.get("extracted") or "").strip()
                        or (bool(deep.get("met")) and not run.verdict_met)
                    )
                    if adopted:
                        run.verdict_met = bool(deep.get("met"))
                        run.confidence = int(deep.get("confidence") or 0)
                        run.evidence = (deep.get("evidence") or "")[:4000]
                        run.extracted = (
                            (deep.get("extracted") or "").strip() or None
                        )
                        if run.extracted:
                            run.extracted = run.extracted[:500]
                        run.reasoning = (
                            "[deep read: this data appears only after the "
                            "page's scripts run] "
                            + plain_dashes(deep.get("reasoning"))
                        )[:4000]
                        run.page_summary = plain_dashes(
                            deep.get("page_summary")
                        )[:2000]
                        run.provider = meta2.get("provider")
                        run.model = meta2.get("model")
                        changed_flag = bool(deep.get("changed"))
                        watcher.use_renderer = True
                        db.add(Event(watcher_id=watcher.id, type="deep_read"))
                        logger.info(
                            "PROBE %s learned deep read for %s",
                            watcher.callsign,
                            watcher.url,
                        )

            # Carry the summary and the value forward so the next pass has
            # something to compare against.
            watcher.last_snapshot = run.page_summary
            if run.extracted:
                watcher.previous_value = run.extracted

            # Adaptive orbit, active real probes only: the demo probe's
            # cadence is cosmetic, and a manual ping of a paused or triggered
            # probe is an inspection, not a scheduled pass.
            if watcher.status == "active" and not watcher.is_demo:
                _adapt_orbit(db, watcher, changed_flag)

            # Only an active probe can fire. Without this, run-now on an
            # already-triggered probe would emit duplicate trigger events
            # (and, from day 3, duplicate alert emails).
            if (
                run.verdict_met
                and run.confidence >= TRIGGER_CONFIDENCE
                and watcher.status == "active"
            ):
                _trigger(db, watcher, run)

    except BlockedByRobotsError as exc:
        # Not a failure to report as breakage: the site asked, and we listened.
        run.error = f"not allowed by the site: {exc}"
        run.verdict_met = False
        run.confidence = 0
    except UnsafeUrlError as exc:
        run.error = f"blocked target: {exc}"
        run.verdict_met = False
        run.confidence = 0
    except Exception as exc:
        logger.warning("PROBE %s run failed: %s", watcher.callsign, exc)
        run.error = f"{type(exc).__name__}: {exc}"[:2000]
        run.verdict_met = False
        run.confidence = 0

    # Track failing streaks so a watcher that has quietly stopped working
    # says so, instead of looking healthy while reading nothing.
    if run.error:
        watcher.consecutive_errors = (watcher.consecutive_errors or 0) + 1
    else:
        watcher.consecutive_errors = 0

    db.add(run)
    db.commit()
    db.refresh(run)

    if (
        run.error
        and watcher.consecutive_errors == FAILURE_NOTICE_AFTER
        and not watcher.is_demo
        and watcher.status in ("active", "triggered")
    ):
        _notify_trouble(db, watcher, run)

    return run


def _notify_trouble(db: Session, watcher: Watcher, run: Run) -> None:
    """Tell the owner their watcher has stopped being able to read its page.

    Sent once per failing streak, at the threshold, so a site that is down for
    a week produces one message rather than a hundred. The count resets on the
    next good pass, so a later streak is reported again.
    """
    host = watcher.url.split("/")[2] if "://" in watcher.url else watcher.url
    subject = f"{watcher.callsign} cannot read {host}"
    body = (
        f"Argus has failed to read the page {FAILURE_NOTICE_AFTER} times in a "
        f"row, so this watch is not running properly.\n\n"
        f"What it reported: {run.error}\n\n"
        "The site may be down, may have moved, or may have started blocking "
        "automated visits. Argus will keep trying on schedule. If the page has "
        "moved, open the watcher and edit its address."
    )
    html = render_alert_html(
        category="trouble",
        callsign=watcher.callsign,
        subject=subject,
        body=body,
        evidence=run.error,
        url=watcher.url,
        confidence=None,
        stamp=run.started_at.strftime("%Y-%m-%d %H:%M UTC") if run.started_at else None,
    )
    channels = deliver_alert(
        email=watcher.email, subject=subject, body=body, html=html
    )
    db.add(
        Event(
            watcher_id=watcher.id,
            type="trouble",
            payload=json.dumps(
                {
                    "category": "trouble",
                    "subject": subject,
                    "body": body,
                    "to": watcher.email,
                    "channels": channels,
                }
            ),
        )
    )
    db.commit()
    logger.warning(
        "PROBE %s failing: %d consecutive errors, owner notified",
        watcher.callsign,
        watcher.consecutive_errors,
    )


def _compose_alert(watcher: Watcher, run: Run) -> dict:
    """The Herald writes the alert. Falls back to a plain template if it fails.

    Returns subject, body and a category used to pick the email design.
    """
    user = (
        f"CALLSIGN: {watcher.callsign}\n"
        f"WATCHED URL: {watcher.url}\n"
        f"CONDITION: {watcher.condition}\n"
        f"EVIDENCE: {run.evidence}\n"
        f"REASONING: {run.reasoning}\n"
    )
    try:
        alert = complete_json(
            system=HERALD_PROMPT,
            user=user,
            model=settings.gemini_model_herald,
            schema=HERALD_SCHEMA,
        )
        subject = plain_dashes((alert.get("subject") or "").strip())
        body = plain_dashes((alert.get("body") or "").strip())
        if subject and body:
            return {
                "subject": subject,
                "body": body,
                "category": category_of(alert.get("category")),
            }
    except Exception as exc:
        logger.warning("Herald failed for %s, using template: %s", watcher.callsign, exc)

    # Deterministic fallback so an alert is never lost to an LLM hiccup. Kept
    # in the same voice as the Herald: the fact, then stop.
    evidence = (run.evidence or "").strip()
    return {
        "subject": "Argus found what you were watching for",
        "body": (
            f"The page now shows: “{evidence}”"
            if evidence
            else "The thing you were waiting for has appeared on the page."
        ),
        "category": "generic",
    }


def _trigger(db: Session, watcher: Watcher, run: Run) -> None:
    """Fire once, then stop. Resuming re-arms against the new page state.

    One-shot prevents an alert storm when a condition stays true across many
    consecutive passes. The Herald composes the alert and it is delivered on
    every enabled channel; the full sent message is stored so the app can show
    it even if the email is filtered.

    The claim below is atomic: two concurrent passes (an instant first check
    plus a manual check) can both see met=True, and without it both would
    email. Only the pass that flips active -> triggered at the database sends
    the alert. Seen live as a double email on 2026-07-24.
    """
    claimed = (
        db.query(Watcher)
        .filter(Watcher.id == watcher.id, Watcher.status == "active")
        .update({"status": "triggered"}, synchronize_session=False)
    )
    watcher.status = "triggered"
    if not claimed:
        logger.info(
            "PROBE %s trigger already claimed by a concurrent pass",
            watcher.callsign,
        )
        return
    db.add(
        Event(
            watcher_id=watcher.id,
            type="triggered",
            payload=json.dumps(
                {"confidence": run.confidence, "evidence": (run.evidence or "")[:500]}
            ),
        )
    )
    logger.info("PROBE %s TRIGGERED (confidence %s)", watcher.callsign, run.confidence)

    alert = _compose_alert(watcher, run)
    html = render_alert_html(
        category=alert["category"],
        callsign=watcher.callsign,
        subject=alert["subject"],
        body=alert["body"],
        evidence=run.evidence,
        url=watcher.url,
        tracked_label=watcher.track,
        tracked_value=run.extracted,
        confidence=run.confidence,
        stamp=run.started_at.strftime("%Y-%m-%d %H:%M UTC") if run.started_at else None,
    )
    if watcher.is_demo:
        # Demo probes re-trigger every cycle around the clock. Recording the
        # alert (so the app shows it) without actually sending keeps the owner
        # inbox and the Gmail quota clean. Real watchers still email for real.
        channels = {"email": {"sent": False, "note": "demo alert, not delivered"}}
    else:
        channels = deliver_alert(
            email=watcher.email,
            subject=alert["subject"],
            body=alert["body"],
            html=html,
        )
    db.add(
        Event(
            watcher_id=watcher.id,
            type="emailed",
            payload=json.dumps(
                {
                    "category": alert["category"],
                    "subject": alert["subject"],
                    "body": alert["body"],
                    "to": watcher.email,
                    "channels": channels,
                }
            ),
        )
    )

    if watcher.repeating:
        # A recurring watch goes straight back on duty: it reported this move,
        # and the next comparison is against the value it just saw. That is
        # what stops it re-alerting on the same event, so a recurring watch
        # only makes sense with a condition phrased about change.
        #
        # Written with an explicit UPDATE, not by assigning the attribute. The
        # claim above wrote "triggered" straight to the row, so setting the
        # attribute back to "active" returns it to its originally loaded value
        # and SQLAlchemy, seeing no change, emits nothing. The row would stay
        # triggered and the watch would quietly stop.
        next_at = datetime.now(timezone.utc) + timedelta(
            minutes=watcher.cadence_minutes
        )
        db.query(Watcher).filter(Watcher.id == watcher.id).update(
            {"status": "active", "next_run_at": next_at},
            synchronize_session=False,
        )
        watcher.status = "active"
        watcher.next_run_at = next_at
        logger.info("PROBE %s re-armed (recurring watch)", watcher.callsign)


def run_due_watchers(db: Session) -> dict:
    """Claim due watchers and run them inline, returning what each decided.

    The /tick endpoint no longer uses this: it claims in the request and
    executes afterwards, so a cron service is not held open for the length of
    several model calls. Kept because running a whole tick synchronously and
    seeing the verdicts is the quickest way to exercise the scheduler by hand.
    """
    claimed = claim_due_watchers(db)
    results = []
    for watcher_id in claimed:
        watcher = db.get(Watcher, watcher_id)
        if watcher is None:
            continue
        run = execute_watcher(db, watcher)
        results.append(
            {
                "callsign": watcher.callsign,
                "met": run.verdict_met,
                "confidence": run.confidence,
                "error": run.error,
            }
        )
    return {"claimed": len(claimed), "processed": len(results), "runs": results}
