"""The scheduler heartbeat and the run loop.

An external cron (cron-job.org) POSTs /tick every ~5 minutes. This both drives
runs and keeps the Koyeb free instance awake. Due watchers are claimed
atomically so overlapping ticks can never run the same watcher twice.

A run never raises. Every failure (blocked target, empty page, provider
outage) is recorded as an honest error run and shown in the mission log,
because a probe reporting "target returned 403" is still the agent visibly
doing its job.
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import get_settings
from .fetcher import UnsafeUrlError, fetch_readable_text
from .llm import complete_json
from .models import Event, Run, Watcher
from .prompts import WATCHER_PROMPT, WATCHER_SCHEMA

settings = get_settings()
logger = logging.getLogger("argus.tick")

# The Watcher prompt already tells the model to prefer false negatives below
# 70. Enforcing it in code too means a badly behaved model cannot raise a
# false alarm on its own.
TRIGGER_CONFIDENCE = 70

# Some sites (JS-rendered storefronts, infinite-scroll feeds) return a scrap of
# navigation chrome instead of content. Judging a condition against 150 chars of
# menu text produces a confident-sounding but meaningless verdict, so anything
# below this is reported as an unusable page rather than pretended to be a read.
MIN_USEFUL_CHARS = 200


def claim_due_watchers(db: Session) -> list[int]:
    """Atomically claim up to max_runs_per_tick due watchers.

    Bumps next_run_at forward in the same statement that selects them, so a
    second concurrent tick sees them as not-yet-due. Returns claimed ids.
    """
    now = datetime.now(timezone.utc)
    rows = db.execute(
        text(
            """
            UPDATE watchers
               SET next_run_at = :now + (cadence_minutes || ' minutes')::interval
             WHERE id IN (
                   SELECT id FROM watchers
                    WHERE status = 'active' AND next_run_at <= :now
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


def _build_watcher_input(watcher: Watcher, page_text: str) -> str:
    previous = watcher.last_snapshot or "(no previous pass)"
    return (
        f"WATCH CONDITION:\n{watcher.condition}\n\n"
        f"PREVIOUS PAGE SUMMARY:\n{previous}\n\n"
        f"CURRENT PAGE TEXT:\n{page_text}"
    )


def execute_watcher(db: Session, watcher: Watcher) -> Run:
    """Run one pass of a watcher: fetch, judge, record, maybe trigger."""
    run = Run(watcher_id=watcher.id, started_at=datetime.now(timezone.utc))

    try:
        page_text = fetch_readable_text(watcher.url)

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
            run.evidence = (verdict.get("evidence") or "")[:4000]
            run.reasoning = (verdict.get("reasoning") or "")[:4000]
            run.page_summary = (verdict.get("page_summary") or "")[:2000]
            run.provider = meta.get("provider")
            run.model = meta.get("model")

            # Carry the summary forward so the next pass has something to
            # compare against.
            watcher.last_snapshot = run.page_summary

            if run.verdict_met and run.confidence >= TRIGGER_CONFIDENCE:
                _trigger(db, watcher, run)

    except UnsafeUrlError as exc:
        run.error = f"blocked target: {exc}"
        run.verdict_met = False
        run.confidence = 0
    except Exception as exc:
        logger.warning("PROBE %s run failed: %s", watcher.callsign, exc)
        run.error = f"{type(exc).__name__}: {exc}"[:2000]
        run.verdict_met = False
        run.confidence = 0

    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _trigger(db: Session, watcher: Watcher, run: Run) -> None:
    """Fire once, then stop. Resuming re-arms against the new page state.

    One-shot prevents an alert storm when a condition stays true across many
    consecutive passes. The Herald email lands on day 3.
    """
    watcher.status = "triggered"
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


def run_due_watchers(db: Session) -> dict:
    """Process one tick: claim due watchers and run each of them."""
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
