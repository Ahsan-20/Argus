"""SQLAlchemy models: the whole persistent world of Argus lives here.

Everything durable is in Postgres because the Koyeb instance disk is
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
    email: Mapped[str] = mapped_column(String(255))
    # active | paused | triggered | retired
    status: Mapped[str] = mapped_column(String(16), default="active")
    last_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # Marks a member of the seeded demo fleet (kept alive, re-armed on cycle).
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

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

    Lives in the DB (not on disk) so it survives Koyeb redeploys and so the
    Demo Ops 'mutate' button can flip it to fire a live trigger for graders.
    """

    __tablename__ = "demo_state"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    slots_open: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=func.now()
    )
