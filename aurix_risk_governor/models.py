from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from aurix_bridge_server.models import utc_now_iso


class RiskDecision(BaseModel):
    approved: bool
    decision: Literal["APPROVE", "BLOCK", "REDUCE"]
    reasons: list[str] = Field(default_factory=list)
    command_id: str
    symbol: Optional[str] = None
    direction: Optional[str] = None
    requested_volume: Optional[float] = None
    approved_volume: Optional[float] = None
    spread_points: Optional[float] = None
    open_positions: int = 0
    equity: Optional[float] = None
    balance: Optional[float] = None
    created_at: str = Field(default_factory=utc_now_iso)
