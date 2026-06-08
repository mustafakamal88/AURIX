from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from aurix_bridge_server.models import utc_now_iso


class MarketTick(BaseModel):
    received_at: str = Field(default_factory=utc_now_iso)
    snapshot_updated_at: Optional[str] = None
    symbol: str
    bid: Optional[float] = None
    ask: Optional[float] = None
    spread_points: Optional[float] = None
    raw_time: Optional[int] = None


class MarketCandle(BaseModel):
    symbol: str
    time: int
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    tick_volume: Optional[float] = None
    spread: Optional[int] = None
    real_volume: Optional[float] = None
    recorded_at: str = Field(default_factory=utc_now_iso)


class MarketQualityReport(BaseModel):
    ok: bool
    symbol: str
    latest_snapshot_age_seconds: Optional[float] = None
    tick_present: bool
    candles_count: int
    spread_points: Optional[float] = None
    spread_ok: bool
    snapshot_fresh: bool
    reasons: list[str]
    updated_at: str = Field(default_factory=utc_now_iso)
