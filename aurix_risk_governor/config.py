from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import yaml
from pydantic import BaseModel, Field


class RiskConfig(BaseModel):
    enabled: bool = True
    max_volume: float = 0.01
    max_open_positions: int = 1
    max_spread_points: float = 350
    require_stop_loss: bool = False
    require_take_profit: bool = False
    max_daily_loss_amount: float = 1.0
    max_daily_loss_percent: float = 2.0
    max_trades_per_day: int = 3
    allowed_symbols: list[str] = Field(default_factory=lambda: ["XAUUSDm"])
    allowed_directions: list[str] = Field(default_factory=lambda: ["BUY", "SELL"])
    live_trading_allowed: bool = False


def load_risk_config(path: Union[str, Path] = "config/risk.yaml") -> RiskConfig:
    config_path = Path(path)
    if not config_path.exists():
        return RiskConfig()

    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return RiskConfig()

    return RiskConfig(**data)
