"""The in-process scheduler: Argus keeping its own time.

Argus used to depend entirely on an outside cron service POSTing `/tick`. That
worked, but it put the one thing that makes the product autonomous in someone
else's web form, handed a shared secret to a third party, and could only fire as
often as that service allowed. A watcher due at 14:03 waited until the next
ten-minute slot.

This loop lives inside the app instead and checks every minute, so a watcher
runs within about a minute of when it said it would.

Three properties make it safe rather than clever:

**The schedule lives in the database, not in memory.** `next_run_at` is a
column. A restart, a redeploy, or a sleeping instance loses nothing: whenever
the process comes back the very next pass picks up everything overdue.

**Claiming is atomic.** `claim_due_watchers()` uses UPDATE ... RETURNING with
SKIP LOCKED, so even if the host ran several workers, each with its own loop,
one watcher can only ever be claimed by one of them. Duplicate alerts are
prevented by the database, not by hoping there is only one scheduler.

**It cannot take the app down.** Every iteration is wrapped. A failing pass is
logged and the loop carries on, because a scheduler that dies silently is worse
than one that never existed.

The remaining requirement is simply that the process is awake. On a free host
that means something has to knock on the door: any visitor does it, and an
uptime monitor pinging `/health` does it on a schedule. If the instance is
asleep when that ping lands, the ping wakes it and this loop immediately catches
up on whatever fell due while it was out.

`POST /tick` still works and still needs its secret. It is now a manual trigger
and a fallback rather than the only way the product functions.
"""

from __future__ import annotations

import asyncio
import logging

from .config import get_settings
from .db import SessionLocal

logger = logging.getLogger("argus.scheduler")
settings = get_settings()


def _run_due_watchers() -> int:
    """Claim and run whatever is due. Blocking, so it is called in a thread.

    Claiming and processing use separate sessions on purpose. The claim is a
    short transaction that must commit promptly; a pass costs seconds of model
    latency, and holding the claim transaction open across all of that would
    keep a database connection tied up for no reason.
    """
    from .models import Watcher
    from .tick import claim_due_watchers, execute_watcher

    with SessionLocal() as db:
        claimed = claim_due_watchers(db)

    for watcher_id in claimed:
        try:
            with SessionLocal() as db:
                watcher = db.get(Watcher, watcher_id)
                if watcher is not None:
                    execute_watcher(db, watcher)
        except Exception as exc:
            # One bad page must not stop the watchers queued behind it.
            logger.warning("scheduler: watcher %s failed: %s", watcher_id, exc)

    return len(claimed)


async def _loop() -> None:
    interval = max(15, settings.scheduler_interval_seconds)
    logger.info("scheduler: started, checking every %ss", interval)

    # A short wait before the first pass. Startup already has the database
    # migration and the seeding to get through, and racing them buys nothing.
    await asyncio.sleep(5)

    while True:
        try:
            ran = await asyncio.to_thread(_run_due_watchers)
            if ran:
                logger.info("scheduler: ran %s watcher(s)", ran)
        except asyncio.CancelledError:
            raise  # shutting down, let it through
        except Exception as exc:
            # Database asleep, network gone, anything. Log it and keep the
            # loop alive; the next pass will very likely succeed.
            logger.warning("scheduler: pass failed: %s", exc)

        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise


def start(app) -> asyncio.Task | None:
    """Start the loop, unless it is switched off."""
    if not settings.scheduler_enabled:
        logger.info("scheduler: disabled, relying on external POST /tick")
        return None
    return asyncio.create_task(_loop(), name="argus-scheduler")


async def stop(task: asyncio.Task | None) -> None:
    """Cancel the loop and wait for it, so shutdown is not noisy."""
    if task is None:
        return
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass
    logger.info("scheduler: stopped")
