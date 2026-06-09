from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from aurix_bridge_server.models import utc_now_iso


PaperRiskStatus = Literal["APPROVED", "REJECTED"]


class PaperRiskDecision(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: str = Field(default_factory=utc_now_iso)
    mode: str = "PAPER"
    decision_type: str = "PAPER_SIMULATED_RISK"
    symbol: str
    strategy_name: str
    strategy_version: str
    signal_id: str
    trade_id: Optional[str] = None
    direction: str
    entry_reference: Optional[float] = None
    stop_loss_reference: Optional[float] = None
    take_profit_reference: Optional[float] = None
    volume: float
    risk_status: PaperRiskStatus
    risk_reason: str = ""
    checks: dict[str, Any] = Field(default_factory=dict)
    limits: dict[str, Any] = Field(default_factory=dict)
    account_snapshot: dict[str, Any] = Field(default_factory=dict)
    market_snapshot: dict[str, Any] = Field(default_factory=dict)
    safety: dict[str, Any] = Field(default_factory=dict)
