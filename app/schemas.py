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
    cadence_minutes: int
    email: str


class ConfirmWatcherRequest(WatcherSpec):
    pass


# ---- Watcher / run views ----
class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime
    verdict_met: bool | None
    confidence: int | None
    evidence: str | None
    reasoning: str | None
    page_summary: str | None
    error: str | None
    provider: str | None = None
    model: str | None = None


class WatcherOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    callsign: str
    url: str
    condition: str
    cadence_minutes: int
    email: str
    status: str
    created_at: datetime
    next_run_at: datetime
