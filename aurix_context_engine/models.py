from __future__ import annotations

from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from aurix_bridge_server.models import utc_now_iso


SessionName = Literal["ASIA", "LONDON", "NY_PRE_MARKET", "NY_OPEN", "NY_LATE", "CLOSED"]
Regime = Literal[
    "INSUFFICIENT_DATA",
    "HIGH_SPREAD",
    "RANGE",
    "BULLISH_BREAKOUT",
    "BEARISH_BREAKDOWN",
    "VOLATILITY_EXPANSION",
    "CHOP",
]
DirectionalBias = Literal["BULLISH", "BEARISH", "NEUTRAL"]
VolatilityState = Literal["NORMAL", "EXPANDING", "UNKNOWN"]


class ContextSnapshot(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    symbol: str
    session_name: SessionName
    session_open: bool
    market_open: bool
    spread_points: Optional[float] = None
    spread_ok: bool
    data_quality_ok: bool
    regime: Regime
    directional_bias: DirectionalBias
    range_high: Optional[float] = None
    range_low: Optional[float] = None
    last_close: Optional[float] = None
    last_candle_direction: Optional[Literal["BULLISH", "BEARISH", "DOJI"]] = None
    volatility_state: VolatilityState = "UNKNOWN"
    reasons: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now_iso)
    snapshot_updated_at: Optional[str] = None
