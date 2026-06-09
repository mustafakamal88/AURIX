from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from aurix_bridge_server.models import utc_now_iso


class SweepResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    params: dict[str, Any] = Field(default_factory=dict)
    candles_used: int = 0
    trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    total_r: float = 0.0
    expectancy_r: float = 0.0
    profit_factor: Optional[float] = None
    max_consecutive_losses: int = 0
    warnings: list[str] = Field(default_factory=list)


class ResearchRun(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    generated_at: str = Field(default_factory=utc_now_iso)
    symbol: str
    candles_used: int = 0
    total_variants: int = 0
    results: list[SweepResult] = Field(default_factory=list)
    best_by_total_r: Optional[SweepResult] = None
    best_by_expectancy: Optional[SweepResult] = None
    best_by_profit_factor: Optional[SweepResult] = None
    warnings: list[str] = Field(default_factory=list)
    safety: dict[str, Any] = Field(default_factory=dict)
