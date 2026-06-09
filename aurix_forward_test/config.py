from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Union

import yaml
from pydantic import BaseModel


class ForwardTestConfig(BaseModel):
    enabled: bool = True
    symbol: str = "XAUUSDm"
    mode: Literal["PAPER"] = "PAPER"
    target_days: int = 10
    target_closed_paper_trades: int = 50
    target_recorded_candles: int = 1000
    target_sessions: list[str] = ["LONDON", "NY_PRE_MARKET", "NY_OPEN", "NY_LATE"]
    minimum_sessions_covered: int = 3
    require_daemon_runs: bool = True
    require_operator_ok: bool = True
    allow_live_trading: bool = False


def load_forward_test_config(path: Union[str, Path] = "config/forward_test.yaml") -> ForwardTestConfig:
    config_path = Path(path)
    if not config_path.exists():
        return ForwardTestConfig()
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return ForwardTestConfig()
    return ForwardTestConfig(**data)
