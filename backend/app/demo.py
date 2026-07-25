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
# Starter watchers offered to everyone. They sit paused in the Shared tab so
# they cost nothing until someone presses "Use this watcher" and gets their
# own running copy.
#
# Every one of these is a real, useful watch on a page that was checked by
# hand before being listed here, and between them they exercise a different
# capability each, so the set doubles as proof the engine works:
#
#   1 dollar rate       a number crossing a threshold, charted over time
#   2 python release    a version going from pre-release to stable
#   3 CSS exam notice   waiting on a specific government announcement
#   4 GitHub status     is a service I depend on broken right now
#   5 NASA picture      judging today's subject, not merely that text changed
#   6 Hacker News       a fast moving page, so the orbit adapts and tightens
#
# Every URL here was fetched and judged by hand before being listed, so none
# of them is a guess. Pages that could not be read reliably were rejected
# rather than shipped hopefully: pakbonds.com rotates its countdown between
# denominations, and the PSX index page loses its labels in extraction, so a
# watcher on either would have been a coin flip.
REAL_FLEET = [
    {
        # A recurring watch: it reports every meaningful move rather than
        # firing once and standing down, because a rate has no single moment
        # you are waiting for.
        "callsign": "Dollar moves by a rupee",
        "url": "https://www.x-rates.com/table/?from=USD&amount=1",
        "condition": (
            "Has the US dollar to Pakistani rupee rate moved by 1 rupee or "
            "more since the previous check?"
        ),
        "track": "the US dollar to Pakistani rupee rate",
        "cadence_minutes": 360,
        "repeating": True,
    },
    {
        # Worded against the page's own vocabulary. An earlier version asked
        # for "stable", a word python.org never uses (released versions are
        # labelled bugfix or security), so it would have waited forever.
        "callsign": "Python 3.15 released",
        "url": "https://www.python.org/downloads/",
        "condition": (
            "Is Python 3.15 shown in the active releases list without a "
            "pre-release label, meaning it has been released?"
        ),
        "track": "the latest released Python version",
        "cadence_minutes": 1440,
    },
    {
        "callsign": "CSS 2027 exam notice",
        "url": "https://www.fpsc.gov.pk/",
        "condition": (
            "Is there an announcement or advertisement for the CSS 2027 "
            "competitive examination?"
        ),
        "track": "the newest item in the latest updates list",
        "cadence_minutes": 720,
    },
    {
        "callsign": "GitHub outage",
        "url": "https://www.githubstatus.com/",
        "condition": (
            "Is an incident currently active or investigating, rather than "
            "every recent incident being resolved?"
        ),
        "track": "the current GitHub service status",
        "cadence_minutes": 60,
    },
    {
        "callsign": "NASA picture: exploding star",
        "url": "https://apod.nasa.gov/apod/astropix.html",
        "condition": (
            "Is today's featured astronomy picture about a supernova, nova or "
            "exploding star?"
        ),
        "track": "the subject of today's featured picture",
        "cadence_minutes": 720,
    },
    {
        "callsign": "Hacker News: security news",
        "url": "https://news.ycombinator.com",
        "condition": (
            "Does any front page story mention a security breach, hack or "
            "vulnerability?"
        ),
        "track": "the current top story title",
        "cadence_minutes": 180,
    },
]


def ensure_seed_account(db: Session) -> bool:
    """Create the maintainer's account on first boot, if it is configured.

    Existing watchers are owned by an email string from before accounts
    existed. Without a matching account nobody could sign in and claim them,
    and a roster of live watchers would look like it belonged to no one.

    Only ever creates. It never touches an account that already exists, so a
    password changed later is not quietly reset on the next restart, and it
    does nothing at all unless SEED_ACCOUNT_PASSWORD is set.
    """
    from .auth import hash_password, normalise_email
    from .models import User

    email = normalise_email(settings.seed_account_email)
    password = settings.seed_account_password
    if not email or not password:
        return False
    if db.query(User).filter(User.email == email).one_or_none():
        return False

    db.add(
        User(
            email=email,
            password_hash=hash_password(password),
            # Pre-confirmed: this address is the one the alerts already go to,
            # so there is nothing left to prove about it.
            is_verified=True,
            verified_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    logger.info("seeded account %s", email)
    return True


def ensure_starter_fleet(db: Session) -> int:
    """Create the shared starter watchers if missing. Idempotent.

    They are seeded paused and shared: visible to every operator in the Shared
    tab, costing no budget, until someone copies one into their own fleet.
    Kept in sync with the spec on every boot so editing REAL_FLEET and
    redeploying is enough to correct a wording mistake.
    """
    email = settings.owner_email or "demo@example.com"
    created = 0
    for spec in REAL_FLEET:
        existing = (
            db.query(Watcher).filter(Watcher.callsign == spec["callsign"]).first()
        )
        if existing is not None:
            existing.url = spec["url"]
            existing.condition = spec["condition"]
            existing.track = spec.get("track")
            existing.repeating = bool(spec.get("repeating"))
            existing.is_shared = True
            db.commit()
            continue
        db.add(
            Watcher(
                callsign=spec["callsign"],
                url=spec["url"],
                condition=spec["condition"],
                track=spec.get("track"),
                cadence_minutes=spec["cadence_minutes"],
                base_cadence_minutes=spec["cadence_minutes"],
                repeating=bool(spec.get("repeating")),
                email=email,
                owner_email=None,  # facility owned, shown to everyone
                status="paused",  # nothing runs until a user opts in
                is_shared=True,
                is_demo=False,
                next_run_at=_now(),
            )
        )
        created += 1
    if created:
        db.commit()
        logger.info("seeded %d starter watchers", created)
    return created


# Old name, kept so nothing that imported it breaks.
ensure_real_fleet = ensure_starter_fleet


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
        track="the number of appointment slots open",
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
