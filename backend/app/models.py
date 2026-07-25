"""SQLAlchemy models: the whole persistent world of Argus lives here.

Everything durable is in Postgres because a free host's instance disk is
ephemeral. No blob storage: only extracted page text is ever kept.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """One person with an account.

    Watchers are tied to their owner by email rather than by a foreign key.
    That was the shape before accounts existed and it stays, because the email
    is genuinely the identity here: it is also where the alerts go. The unique
    index on it is what keeps the two in step.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Always stored lowercase and trimmed, so one person cannot end up with
    # two accounts by capitalising differently.
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Rate limits the resend button without needing anywhere else to store it.
    verify_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Set when a reset is requested and cleared the moment one is used, so a
    # reset link works exactly once even while it is still inside its expiry.
    reset_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reset_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Failed logins in a row, and a lockout that clears itself. Slows guessing
    # to a crawl without ever letting an attacker lock a real person out
    # permanently by hammering their address.
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Watcher(Base):
    """One autonomous agent (a probe) the user has launched."""

    __tablename__ = "watchers"

    id: Mapped[int] = mapped_column(primary_key=True)
    callsign: Mapped[str] = mapped_column(String(32))  # e.g. PROBE-01
    url: Mapped[str] = mapped_column(Text)
    condition: Mapped[str] = mapped_column(Text)  # testable question
    # Optional data point the agent extracts and logs every run (e.g. "the
    # current price"). Turns the agent from a notifier into a tracker.
    track: Mapped[str | None] = mapped_column(Text, nullable=True)
    cadence_minutes: Mapped[int] = mapped_column(Integer, default=30)
    # Adaptive orbit: base_cadence_minutes is the cadence the operator ordered
    # (the anchor; backfilled lazily for older rows), cadence_minutes is the
    # live value the scheduler uses, and stable_passes counts consecutive
    # passes that saw no meaningful change. See tick.plan_orbit for the rules.
    base_cadence_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stable_passes: Mapped[int] = mapped_column(Integer, default=0)
    email: Mapped[str] = mapped_column(String(255))
    # The operator who launched this probe (their email is their callsign and
    # notify address). NULL means a facility probe (seeded fleet / demo),
    # shown to every operator. Powers the MY FLEET vs ALL PROBES toggle.
    owner_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # active | paused | triggered | standby (demo probe at rest).
    # Retiring deletes the row outright; "retired" is never stored.
    status: Mapped[str] = mapped_column(String(16), default="active")
    last_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The last value this watcher extracted, carried forward so the next pass
    # can be asked "has this moved since?" rather than judging in isolation.
    # Named previous_value, not last_value: Postgres parses an unquoted
    # last_value as the window function and the query fails to compile.
    previous_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    # A recurring watch re-arms itself after each alert instead of standing
    # down, for conditions that are about movement rather than a one-off event.
    repeating: Mapped[bool] = mapped_column(Boolean, default=False)
    # Consecutive failed passes. A watcher that quietly cannot read its page
    # any more is worse than no watcher, so once this crosses the threshold
    # the owner is told once, and the count resets on the next good pass.
    consecutive_errors: Mapped[int] = mapped_column(Integer, default=0)
    # Cache validators from the last fetch. Sending these back lets a server
    # answer "nothing changed" with an empty 304 instead of the whole page,
    # which is both cheaper for them and faster for us.
    http_etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    http_last_modified: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # When the page was last genuinely read and judged, as opposed to skipped
    # because it had not changed.
    last_full_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # Marks a member of the seeded demo fleet (kept alive, re-armed on cycle).
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    # Deep read: set once a pass discovers the target's data only appears
    # after JavaScript runs. Future passes then fetch via the renderer first.
    use_renderer: Mapped[bool] = mapped_column(Boolean, default=False)
    # Shared: the owner offers this watcher as a template. Other operators see
    # it (inert) in the Shared tab and can clone it into their own fleet; the
    # clone's history and alerts are fully separate.
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)

    runs: Mapped[list["Run"]] = relationship(
        back_populates="watcher", cascade="all, delete-orphan"
    )
    # Without this cascade, retiring a probe fails on the events FK.
    events: Mapped[list["Event"]] = relationship(
        back_populates="watcher", cascade="all, delete-orphan"
    )


class Run(Base):
    """A single execution of a watcher: what it saw and what it decided."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    watcher_id: Mapped[int] = mapped_column(ForeignKey("watchers.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    verdict_met: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The value the agent extracted this run for the watcher's `track` field.
    extracted: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Which provider/model actually judged this pass. Shown in the mission log
    # so a Groq fallback is visible rather than hidden.
    provider: Mapped[str | None] = mapped_column(String(16), nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)

    watcher: Mapped["Watcher"] = relationship(back_populates="runs")


class Event(Base):
    """Audit trail: created | triggered | emailed | paused | resumed."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    watcher_id: Mapped[int] = mapped_column(ForeignKey("watchers.id"))
    type: Mapped[str] = mapped_column(String(24))
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    watcher: Mapped["Watcher"] = relationship(back_populates="events")


class BudgetCounter(Base):
    """One row per UTC day tracking Gemini calls, to enforce the daily budget."""

    __tablename__ = "budget_counters"

    day: Mapped[str] = mapped_column(String(10), primary_key=True)  # YYYY-MM-DD
    gemini_calls: Mapped[int] = mapped_column(Integer, default=0)
    groq_calls: Mapped[int] = mapped_column(Integer, default=0)


class DemoState(Base):
    """Mutable state for the self-hosted demo target page.

    Lives in the DB (not on disk) so it survives a redeploy and so the
    Demo Ops 'mutate' button can flip it to fire a live trigger for graders.
    """

    __tablename__ = "demo_state"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    slots_open: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=func.now()
    )
