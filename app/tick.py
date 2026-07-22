"""The scheduler heartbeat.

An external cron (cron-job.org) POSTs /tick every ~5 minutes. This both drives
runs and keeps the Koyeb free instance awake. Due watchers are claimed
atomically so overlapping ticks can never run the same watcher twice.

Day 2: fill in run_due_watchers with the fetch -> Watcher -> store -> maybe
Herald flow.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import get_settings

settings = get_settings()


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


def run_due_watchers(db: Session) -> dict:
    """Process this tick. TODO(day2): fetch, judge, store, maybe alert."""
    claimed = claim_due_watchers(db)
    return {"claimed": claimed, "processed": 0, "note": "run loop lands day 2"}
