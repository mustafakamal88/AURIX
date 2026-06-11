from __future__ import annotations

from typing import Any
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from aurix_bridge_server.models import utc_now_iso


SignalStatus = Literal[
    "NO_SIGNAL",
    "SHADOW_SIGNAL",
    "PAPER_SIGNAL",
    "SKIPPED_SESSION",
    "SKIPPED_SPREAD",
    "SKIPPED_MARKET_QUALITY",
    "SKIPPED_CONTEXT",
    "SKIPPED_CHOP",
    "SKIPPED_INSUFFICIENT_DATA",
    "SKIPPED_COOLDOWN",
    "SKIPPED_MAX_SIGNALS",
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
    decision_trace: Optional[dict[str, Any]] = None
    strategy_id: Optional[str] = None
    signal_confidence: Optional[float] = None
    signal_reasons: list[str] = Field(default_factory=list)
    decision_cycle_id: Optional[str] = None
    final_gate_result: Optional[str] = None
    paper_risk_checked: bool = False
    paper_risk_decision_id: Optional[str] = None
    paper_risk_status: Optional[str] = None
    paper_risk_checked_at: Optional[str] = None
    risk_check_source: Optional[str] = None
