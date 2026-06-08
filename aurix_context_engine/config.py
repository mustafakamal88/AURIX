from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import yaml
from pydantic import BaseModel, Field


class SessionWindow(BaseModel):
    start: str
    end: str


class ContextConfig(BaseModel):
    enabled: bool = True
    symbol: str = "XAUUSDm"
    timezone: str = "Europe/London"
    sessions: dict[str, SessionWindow] = Field(
        default_factory=lambda: {
            "ASIA": SessionWindow(start="00:00", end="07:00"),
            "LONDON": SessionWindow(start="07:00", end="12:00"),
            "NY_PRE_MARKET": SessionWindow(start="12:00", end="14:30"),
            "NY_OPEN": SessionWindow(start="14:30", end="17:00"),
            "NY_LATE": SessionWindow(start="17:00", end="21:00"),
        }
    )
    max_spread_points: float = 350
    min_candles_required: int = 20
    lookback_candles: int = 20
    range_lookback_candles: int = 10
    volatility_expansion_multiplier: float = 1.5


def load_context_config(path: Union[str, Path] = "config/context.yaml") -> ContextConfig:
    config_path = Path(path)
    if not config_path.exists():
        return ContextConfig()
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return ContextConfig()
    return ContextConfig(**data)
