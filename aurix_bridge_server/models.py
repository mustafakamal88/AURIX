from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


LIVE_CONFIRM_PHRASE = "I_ACCEPT_LIVE_RISK"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


CommandStatus = Literal[
    "QUEUED",
    "DISPATCHED",
    "EA_RECEIVED",
    "EXECUTION_BLOCKED",
    "EXECUTION_FAILED",
    "EXECUTION_FILLED",
    "CANCELLED",
    "EXPIRED",
]


class Command(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: Literal["OPEN_MARKET", "CLOSE_POSITION", "CANCEL_ORDER", "KILL_SWITCH"]
    terminal_id: str = "AURIX-MAC-001"
    symbol: Optional[str] = None
    direction: Optional[Literal["BUY", "SELL"]] = None
    volume: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    ticket: Optional[int] = None
    comment: str = "AURIX"
    live_confirm: Optional[str] = None
    created_at: str = Field(default_factory=utc_now_iso)
    status: CommandStatus = "QUEUED"
    risk_decision_id: Optional[str] = None
    dispatched_at: Optional[str] = None
    completed_at: Optional[str] = None
    dispatch_count: int = 0
    last_error: Optional[str] = None
    execution_result_id: Optional[str] = None


class Snapshot(BaseModel):
    terminal_id: str
    received_at: str = Field(default_factory=utc_now_iso)
    account: dict[str, Any] = Field(default_factory=dict)
    tick: dict[str, Any] = Field(default_factory=dict)
    candles: list[dict[str, Any]] = Field(default_factory=list)
    positions: list[dict[str, Any]] = Field(default_factory=list)
    orders: list[dict[str, Any]] = Field(default_factory=list)
    deals: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class ExecutionResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    terminal_id: str
    command_id: str
    ok: bool
    retcode: Optional[int] = None
    message: str = ""
    order: Optional[int] = None
    deal: Optional[int] = None
    symbol: Optional[str] = None
    direction: Optional[str] = None
    volume: Optional[float] = None
    price: Optional[float] = None
    received_at: str = Field(default_factory=utc_now_iso)
    raw: dict[str, Any] = Field(default_factory=dict)
