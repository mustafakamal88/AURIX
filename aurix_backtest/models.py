from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from aurix_bridge_server.models import utc_now_iso


BacktestTradeStatus = Literal["WIN", "LOSS", "OPEN", "EXPIRED"]


class BacktestTrade(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    symbol: str
    direction: Literal["BUY", "SELL"]
    entry_time: Any
    entry_price: float
    stop_loss: float
    take_profit: float
    exit_time: Optional[Any] = None
    exit_price: Optional[float] = None
    status: BacktestTradeStatus = "OPEN"
    pnl_points: float = 0.0
    r_multiple: float = 0.0
    setup_name: str = "xauusd_paper_v1_replay"
    reasons: list[str] = Field(default_factory=list)


class BacktestReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    generated_at: str = Field(default_factory=utc_now_iso)
    symbol: str
    candles_used: int = 0
    signals: int = 0
    trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    total_r: float = 0.0
    expectancy_r: float = 0.0
    profit_factor: Optional[float] = None
    max_consecutive_losses: int = 0
    warnings: list[str] = Field(default_factory=list)
    safety: dict[str, Any] = Field(default_factory=dict)
