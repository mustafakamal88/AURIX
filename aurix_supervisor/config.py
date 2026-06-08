from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Union

import yaml
from pydantic import BaseModel


class SupervisorConfig(BaseModel):
    enabled: bool = True
    mode: Literal["PAPER"] = "PAPER"
    symbol: str = "XAUUSDm"
    loop_interval_seconds: float = 5
    max_snapshot_age_seconds: float = 10
    require_market_quality_ok: bool = True
    run_context: bool = True
    run_strategy: bool = True
    run_paper_trading: bool = True
    allow_command_queueing: bool = False


def load_supervisor_config(path: Union[str, Path] = "config/supervisor.yaml") -> SupervisorConfig:
    config_path = Path(path)
    if not config_path.exists():
        return SupervisorConfig()
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return SupervisorConfig()
    return SupervisorConfig(**data)
