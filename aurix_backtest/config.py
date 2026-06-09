from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import yaml
from pydantic import BaseModel


class BacktestConfig(BaseModel):
    enabled: bool = True
    symbol: str = "XAUUSDm"
    timeframe: str = "M1"
    source_candles_file: str = "data/market_candles_m1.json"
    default_volume: float = 0.01
    default_stop_points: float = 300
    default_take_profit_points: float = 600
    max_spread_points: float = 350
    lookback_range_candles: int = 10
    min_candles: int = 20
    allowed_sessions: list[str] = ["LONDON", "NY_PRE_MARKET", "NY_OPEN", "NY_LATE"]
    block_closed_session: bool = True


def load_backtest_config(path: Union[str, Path] = "config/backtest.yaml") -> BacktestConfig:
    config_path = Path(path)
    if not config_path.exists():
        return BacktestConfig()
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return BacktestConfig()
    return BacktestConfig(**data)
