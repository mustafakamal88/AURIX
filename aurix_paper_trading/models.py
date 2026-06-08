from __future__ import annotations

from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from aurix_bridge_server.models import utc_now_iso


PaperTradeStatus = Literal["OPEN", "CLOSED_TP", "CLOSED_SL", "CLOSED_MANUAL", "EXPIRED"]


class PaperTrade(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    signal_id: str
    strategy_name: str
    strategy_version: str
    symbol: str
    direction: Literal["BUY", "SELL"]
    status: PaperTradeStatus = "OPEN"
    entry_price: float
    stop_loss: float
    take_profit: float
    volume: float
    opened_at: str = Field(default_factory=utc_now_iso)
    closed_at: Optional[str] = None
    close_price: Optional[float] = None
    pnl_points: Optional[float] = None
    r_multiple: Optional[float] = None
    reasons: list[str] = Field(default_factory=list)
    snapshot_opened_at: Optional[str] = None
    snapshot_closed_at: Optional[str] = None
