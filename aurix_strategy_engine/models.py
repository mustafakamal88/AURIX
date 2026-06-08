from __future__ import annotations

from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from aurix_bridge_server.models import utc_now_iso


SignalStatus = Literal[
    "NO_SIGNAL",
    "SHADOW_SIGNAL",
    "SKIPPED_SPREAD",
    "SKIPPED_INSUFFICIENT_DATA",
    "SKIPPED_COOLDOWN",
    "ERROR",
]


class StrategySignal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    strategy_name: str
    strategy_version: str
    mode: str
    symbol: str
    direction: Optional[Literal["BUY", "SELL"]] = None
    status: SignalStatus
    confidence: float = 0.0
    entry_reference: Optional[float] = None
    stop_loss_reference: Optional[float] = None
    take_profit_reference: Optional[float] = None
    reasons: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now_iso)
    snapshot_updated_at: Optional[str] = None
    risk_checked: bool = False
    command_id: Optional[str] = None
    context_session: Optional[str] = None
    context_regime: Optional[str] = None
    context_bias: Optional[str] = None
    range_high: Optional[float] = None
    range_low: Optional[float] = None
