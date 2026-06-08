from __future__ import annotations

from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from aurix_bridge_server.models import utc_now_iso


EntryType = Literal["PAPER_TRADE", "SIGNAL", "DAILY_SUMMARY", "SYSTEM_NOTE"]
ReviewClassification = Literal[
    "VALID_WIN",
    "VALID_LOSS",
    "NO_TRADE",
    "SESSION_BLOCKED",
    "HIGH_SPREAD_BLOCKED",
    "INSUFFICIENT_DATA",
    "NO_SIGNAL",
    "OPEN_TRADE",
    "UNKNOWN",
]
MistakeFlag = Literal[
    "TRADED_CLOSED_SESSION",
    "HIGH_SPREAD",
    "NO_CONTEXT",
    "NO_STOP_LOSS",
    "NO_TAKE_PROFIT",
    "LOW_CONFIDENCE",
    "NONE",
]


class JournalEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    entry_type: EntryType
    source_id: str
    symbol: Optional[str] = None
    direction: Optional[str] = None
    status: Optional[str] = None
    session: Optional[str] = None
    regime: Optional[str] = None
    bias: Optional[str] = None
    setup_name: Optional[str] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    close_price: Optional[float] = None
    pnl_points: Optional[float] = None
    r_multiple: Optional[float] = None
    classification: ReviewClassification = "UNKNOWN"
    mistake_flags: list[MistakeFlag] = Field(default_factory=lambda: ["NONE"])
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now_iso)
