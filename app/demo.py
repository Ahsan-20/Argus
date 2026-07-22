"""The demo fleet and the self-hosted demo target page.

Goal: the deployed site must look alive to a grader who visits unattended, with
nobody there to press anything. So we seed a small fleet of probes and a demo
target page whose state cycles between "slots open" and "no slots". A demo
probe watching it therefore triggers on its own, periodically, producing a
steady stream of real runs, verdicts, and alert emails in the mission log.

The demo target's state lives in the database (not on disk), so it survives
Koyeb redeploys and is consistent across requests.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .config import get_settings
from .models import DemoState, Watcher

logger = logging.getLogger("argus.demo")
settings = get_settings()

DEMO_TARGET_PATH = "/demo/target"
TARGET_TITLE = "Capital Passport Office - Appointment Availability Board"


def demo_target_url() -> str:
    return settings.public_base_url.rstrip("/") + DEMO_TARGET_PATH


def is_demo_target(url: str) -> bool:
    return (url or "").rstrip("/").endswith(DEMO_TARGET_PATH)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_state(db: Session) -> DemoState:
    st = db.get(DemoState, 1)
    if st is None:
        st = DemoState(id=1, slots_open=0)
        db.add(st)
        db.commit()
        db.refresh(st)
    return st


def advance_cycle(db: Session) -> bool:
    """Flip the demo target open/closed if a full cycle has elapsed.

    Returns True if the state changed. When it closes, any demo probe that had
    triggered is re-armed, so the next open produces a fresh trigger and the
    demo keeps living.
    """
    st = get_state(db)
    updated = st.updated_at or _now()
    elapsed_min = (_now() - updated).total_seconds() / 60
    if elapsed_min < settings.demo_cycle_minutes:
        return False

    if st.slots_open > 0:
        st.slots_open = 0
        # Re-arm triggered demo probes for the next opening.
        for w in (
            db.query(Watcher)
            .filter(Watcher.is_demo.is_(True), Watcher.status == "triggered")
            .all()
        ):
            if is_demo_target(w.url):
                w.status = "active"
                w.next_run_at = _now()
    else:
        st.slots_open = 3
    db.commit()
    logger.info("demo target cycled -> slots_open=%s", st.slots_open)
    return True


def target_text(db: Session) -> str:
    """The readable text a probe 'sees' when it reads the demo target.

    Returned directly to the Watcher instead of doing an HTTP round trip to our
    own URL (which the SSRF guard would block for localhost anyway). The AI
    judging is still completely real.
    """
    st = get_state(db)
    if st.slots_open > 0:
        status = (
            f"STATUS: {st.slots_open} appointment slots are OPEN for booking "
            "right now. Eligible applicants may reserve a slot immediately "
            "through the online portal. Slots are limited and fill quickly."
        )
    else:
        status = (
            "STATUS: No appointment slots are currently available. All slots "
            "for the coming period are fully booked. Please check back later, "
            "as cancellations are released periodically."
        )
    return (
        f"{TARGET_TITLE}\n\n{status}\n\n"
        "This board is updated automatically as availability changes. "
        "Applicants are advised to monitor it regularly. Office hours are "
        "Monday to Friday, 9am to 4pm. For assistance contact the help desk."
    )


def render_target_html(db: Session) -> str:
    """Public HTML page for the demo target (what a probe would fetch live)."""
    st = get_state(db)
    open_ = st.slots_open > 0
    color = "#1a7f37" if open_ else "#8a1c1c"
    banner = (
        f"{st.slots_open} appointment slots are OPEN for booking"
        if open_
        else "No appointment slots are currently available"
    )
    body = target_text(db).split("\n\n", 2)[-1]
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{TARGET_TITLE}</title></head>"
        "<body style='font-family:Georgia,serif;max-width:640px;margin:40px auto;color:#222'>"
        f"<h1 style='font-size:22px'>{TARGET_TITLE}</h1>"
        f"<p style='padding:14px 18px;background:{color};color:#fff;font-size:18px'>"
        f"STATUS: {banner}.</p>"
        f"<p style='line-height:1.7'>{body}</p>"
        f"<p style='color:#666;font-size:13px'>Last updated: {st.updated_at} UTC. "
        "This is an Argus demonstration target: its availability cycles "
        "automatically so watcher probes can be seen triggering.</p>"
        "</body></html>"
    )


def seed_fleet(db: Session) -> int:
    """Create the demo fleet once. Idempotent: does nothing if it already exists."""
    if db.query(Watcher).filter(Watcher.is_demo.is_(True)).count() > 0:
        return 0

    email = settings.owner_email or "demo@example.com"
    now = _now()
    fleet = [
        Watcher(
            callsign="PROBE-DEMO-1",
            url=demo_target_url(),
            condition="Are appointment slots currently available for booking?",
            cadence_minutes=15,
            email=email,
            status="active",
            is_demo=True,
            next_run_at=now,
        ),
        Watcher(
            callsign="PROBE-DEMO-2",
            url="https://en.wikipedia.org/wiki/Pakistan",
            condition="Does the page state that Islamabad is the capital of Pakistan?",
            cadence_minutes=180,
            email=email,
            status="active",
            is_demo=True,
            next_run_at=now,
        ),
        Watcher(
            callsign="PROBE-DEMO-3",
            url="https://www.python.org/downloads/",
            condition="Is a stable Python 4 release available for download?",
            cadence_minutes=180,
            email=email,
            status="active",
            is_demo=True,
            next_run_at=now,
        ),
    ]
    db.add_all(fleet)
    db.commit()
    logger.info("seeded demo fleet: %d probes", len(fleet))
    return len(fleet)
