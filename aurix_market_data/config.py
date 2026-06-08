from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import yaml
from pydantic import BaseModel


class MarketDataConfig(BaseModel):
    enabled: bool = True
    symbol: str = "XAUUSDm"
    record_ticks: bool = True
    record_candles: bool = True
    record_spread: bool = True
    max_tick_records: int = 5000
    max_candle_records: int = 10000
    max_snapshot_age_seconds: float = 10
    max_spread_points: float = 350
    min_candles_required: int = 20


def load_market_data_config(path: Union[str, Path] = "config/market_data.yaml") -> MarketDataConfig:
    config_path = Path(path)
    if not config_path.exists():
        return MarketDataConfig()
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return MarketDataConfig()
    return MarketDataConfig(**data)
