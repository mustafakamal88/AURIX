from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from aurix_bridge_server.models import utc_now_iso


class PaperPerformanceReport(BaseModel):
    generated_at: str = Field(default_factory=utc_now_iso)
    total_trades: int = 0
    open_trades: int = 0
    closed_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    total_pnl_points: float = 0.0
    average_pnl_points: float = 0.0
    total_r: float = 0.0
    average_r: float = 0.0
    best_trade_r: Optional[float] = None
    worst_trade_r: Optional[float] = None
    profit_factor: Optional[float] = None
    expectancy_r: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    by_direction: dict[str, dict[str, Any]] = Field(default_factory=dict)
    by_session: dict[str, dict[str, Any]] = Field(default_factory=dict)
    by_regime: dict[str, dict[str, Any]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
