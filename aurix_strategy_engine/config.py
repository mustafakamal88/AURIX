from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import yaml
from pydantic import BaseModel


class StrategyConfig(BaseModel):
    enabled: bool = True
    mode: str = "SHADOW"
    symbol: str = "XAUUSDm"
    timeframe: str = "M1"
    min_candles: int = 20
    max_spread_points: float = 350
    allow_buy: bool = True
    allow_sell: bool = True
    signal_cooldown_seconds: int = 60
    session_filter_enabled: bool = False


def load_strategy_config(path: Union[str, Path] = "config/strategy_xauusd_shadow_v1.yaml") -> StrategyConfig:
    config_path = Path(path)
    if not config_path.exists():
        return StrategyConfig()

    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return StrategyConfig()

    return StrategyConfig(**data)
