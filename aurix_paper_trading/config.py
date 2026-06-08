from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import yaml
from pydantic import BaseModel


class PaperTradingConfig(BaseModel):
    enabled: bool = True
    symbol: str = "XAUUSDm"
    default_volume: float = 0.01
    default_stop_points: float = 300
    default_take_profit_points: float = 600
    max_open_paper_trades: int = 1
    allow_multiple_same_direction: bool = False
    spread_points_for_entry: str = "snapshot"
    commission_per_lot: float = 0.0
    slippage_points: float = 0


def load_paper_trading_config(path: Union[str, Path] = "config/paper_trading.yaml") -> PaperTradingConfig:
    config_path = Path(path)
    if not config_path.exists():
        return PaperTradingConfig()
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return PaperTradingConfig()
    return PaperTradingConfig(**data)
