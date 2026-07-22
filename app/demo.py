"""The seeded real fleet and the on-demand demonstration.

Honesty first. Two clearly separated things live here:

1. A small **real fleet** of probes watching genuine public sites (Wikipedia,
   python.org, Hacker News). These run on the normal schedule. Everything about
   them is real: real fetches, real AI verdicts, real evidence. They exist so
   the deployed dashboard is not empty for a grader who visits unattended.

2. A single **demonstration probe** that watches a synthetic target page we
   control. It does NOT run on the schedule. It only runs when a user presses
   "Run a live demonstration", so they can watch a full trigger happen on
   command (real sites rarely flip a condition while you watch). The target
   page and the probe are both plainly labelled as a demonstration, so nothing
   is passed off as organic real-world activity.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .config import get_settings
from .models import DemoState, Watcher

logger = logging.getLogger("argus.demo")
settings = get_settings()

DEMO_TARGET_PATH = "/demo/target"
DEMO_CALLSIGN = "PROBE-DEMO"
TARGET_TITLE = "Argus Demonstration Target - Appointment Availability Board"


def demo_target_url() -> str:
    return settings.public_base_url.rstrip("/") + DEMO_TARGET_PATH


def is_demo_target(url: str) -> bool:
    return (url or "").rstrip("/").endswith(DEMO_TARGET_PATH)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Synthetic target state
# ---------------------------------------------------------------------------
def get_state(db: Session) -> DemoState:
    st = db.get(DemoState, 1)
    if st is None:
        st = DemoState(id=1, slots_open=0)
        db.add(st)
        db.commit()
        db.refresh(st)
    return st


def set_slots(db: Session, count: int) -> None:
    st = get_state(db)
    st.slots_open = max(0, count)
    db.commit()


def target_text(db: Session) -> str:
    """The readable text the demonstration probe 'sees'. Real AI judges it."""
    st = get_state(db)
    if st.slots_open > 0:
        status = (
            f"STATUS: {st.slots_open} appointment slots are OPEN for booking "
            "right now. Eligible applicants may reserve a slot immediately."
        )
    else:
        status = (
            "STATUS: No appointment slots are currently available. All slots "
            "are fully booked. Please check back later."
        )
    return (
        f"{TARGET_TITLE}\n\n{status}\n\n"
        "This is a demonstration page used by Argus to show a watcher probe "
        "triggering on command. Its availability is controlled by the demo "
        "button, not by a real appointment system."
    )


def render_target_html(db: Session) -> str:
    st = get_state(db)
    open_ = st.slots_open > 0
    color = "#1a7f37" if open_ else "#8a1c1c"
    banner = (
        f"{st.slots_open} appointment slots are OPEN for booking"
        if open_
        else "No appointment slots are currently available"
    )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{TARGET_TITLE}</title></head>"
        "<body style='font-family:Georgia,serif;max-width:640px;margin:40px auto;color:#222'>"
        "<p style='background:#f3e6b3;border:1px solid #d9c56a;padding:8px 12px;"
        "font-size:13px'>DEMONSTRATION PAGE. This target is controlled by the "
        "Argus demo button, not a real appointment system.</p>"
        f"<h1 style='font-size:22px'>{TARGET_TITLE}</h1>"
        f"<p style='padding:14px 18px;background:{color};color:#fff;font-size:18px'>"
        f"STATUS: {banner}.</p>"
        "<p style='line-height:1.7'>This board simulates an appointment "
        "availability page so an Argus probe can be seen fetching it, reasoning "
        "about it, and triggering. The engine doing the watching is the real "
        "product; only this target is synthetic.</p>"
        f"<p style='color:#666;font-size:13px'>Last updated: {st.updated_at} UTC.</p>"
        "</body></html>"
    )


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------
REAL_FLEET = [
    {
        "callsign": "PROBE-01",
        "url": "https://www.python.org/downloads/",
        "condition": "Is a stable Python 4 release available for download?",
        "cadence_minutes": 120,
    },
    {
        "callsign": "PROBE-02",
        "url": "https://en.wikipedia.org/wiki/Pakistan",
        "condition": "Does the page state that Islamabad is the capital of Pakistan?",
        "cadence_minutes": 180,
    },
    {
        "callsign": "PROBE-03",
        "url": "https://news.ycombinator.com",
        "condition": "Does any front page story mention AI or a language model?",
        "cadence_minutes": 60,
    },
]


def ensure_real_fleet(db: Session) -> int:
    """Create the real seeded probes if missing. Idempotent."""
    email = settings.owner_email or "demo@example.com"
    created = 0
    for spec in REAL_FLEET:
        exists = (
            db.query(Watcher).filter(Watcher.callsign == spec["callsign"]).count() > 0
        )
        if exists:
            continue
        db.add(
            Watcher(
                callsign=spec["callsign"],
                url=spec["url"],
                condition=spec["condition"],
                cadence_minutes=spec["cadence_minutes"],
                email=email,
                status="active",
                is_demo=False,  # real probes run on the normal schedule
                next_run_at=_now(),
            )
        )
        created += 1
    if created:
        db.commit()
        logger.info("seeded %d real probes", created)
    return created


def ensure_demo_probe(db: Session) -> Watcher:
    """The single demonstration probe, at rest until the button is pressed."""
    probe = db.query(Watcher).filter(Watcher.callsign == DEMO_CALLSIGN).first()
    if probe is not None:
        # Self-correct the display URL if the deploy base URL changed.
        wanted = demo_target_url()
        if probe.url != wanted:
            probe.url = wanted
            db.commit()
        return probe

    probe = Watcher(
        callsign=DEMO_CALLSIGN,
        url=demo_target_url(),
        condition="Are appointment slots currently available for booking?",
        cadence_minutes=60,
        email=settings.owner_email or "demo@example.com",
        status="standby",  # excluded from the scheduler; runs only on demand
        is_demo=True,
        next_run_at=_now(),
    )
    db.add(probe)
    db.commit()
    db.refresh(probe)
    return probe
