"""Pydantic request/response models for the API surface."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


# ---- Watcher creation (two-step: parse then confirm) ----
class CreateWatcherRequest(BaseModel):
    sentence: str  # the plain-English watch order


class WatcherSpec(BaseModel):
    """What the Commissioner extracts; echoed back for user confirmation."""

    callsign: str
    url: str
    condition: str
    track: str = ""  # optional data point the agent tracks over time
    cadence_minutes: int
    email: str
    # True for a watch about movement, which re-arms after each alert.
    repeating: bool = False


class ConfirmWatcherRequest(WatcherSpec):
    pass


class UpdateWatcherRequest(BaseModel):
    """Partial edit of an existing watcher. Only provided fields change."""

    url: str | None = None
    condition: str | None = None
    track: str | None = None
    cadence_minutes: int | None = None
    email: str | None = None
    callsign: str | None = None
    is_shared: bool | None = None
    repeating: bool | None = None


# ---- Watcher / run views ----
class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime
    verdict_met: bool | None
    confidence: int | None
    evidence: str | None
    extracted: str | None = None
    reasoning: str | None
    page_summary: str | None
    error: str | None
    provider: str | None = None
    model: str | None = None


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    payload: str | None
    created_at: datetime


class LastRun(BaseModel):
    """A compact summary of a probe's most recent pass, for the roster.

    Lets the console show LAST VERDICT and CONFIDENCE without one request per
    probe. `error` carries the message when the pass failed, else null.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime
    verdict_met: bool | None
    confidence: int | None
    extracted: str | None = None
    error: str | None = None


class WatcherOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    callsign: str
    url: str
    condition: str
    track: str | None = None
    cadence_minutes: int
    # The cadence the operator ordered; differs from cadence_minutes once the
    # probe has adapted its orbit. Lets the UI show ORDERED vs CURRENT.
    base_cadence_minutes: int | None = None
    email: str
    owner_email: str | None = None
    is_demo: bool = False
    is_shared: bool = False
    repeating: bool = False
    status: str
    created_at: datetime
    next_run_at: datetime
    # Populated by the list endpoint; null on endpoints that do not join runs.
    last_run: LastRun | None = None
