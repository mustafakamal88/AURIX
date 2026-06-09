from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import yaml
from pydantic import BaseModel


class ResearchConfig(BaseModel):
    enabled: bool = True
    symbol: str = "XAUUSDm"
    source_candles_file: str = "data/market_candles_m1.json"
    stop_points_values: list[float] = [200, 300, 400]
    take_profit_points_values: list[float] = [400, 600, 800]
    lookback_range_candles_values: list[int] = [5, 10, 15]
    max_spread_points_values: list[float] = [280, 350]
    min_trades_required: int = 5
    max_results: int = 100
    allow_config_mutation: bool = False


def load_research_config(path: Union[str, Path] = "config/research.yaml") -> ResearchConfig:
    config_path = Path(path)
    if not config_path.exists():
        return ResearchConfig()
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return ResearchConfig()
    return ResearchConfig(**data)
