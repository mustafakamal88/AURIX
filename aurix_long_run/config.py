from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import yaml
from pydantic import BaseModel


class LongForwardTestConfig(BaseModel):
    enabled: bool = True
    mode: str = "PAPER"
    symbol: str = "XAUUSDm"
    target_days: int = 10
    target_sessions: list[str] = ["LONDON", "NY_PRE_MARKET", "NY_OPEN", "NY_LATE"]
    orchestrator_interval_seconds: int = 10
    heartbeat_interval_seconds: int = 30
    daily_report_enabled: bool = True
    daily_report_time_uk: str = "21:15"
    auto_start_orchestrator: bool = True
    auto_start_daemon: bool = False
    allow_command_queueing: bool = False
    allow_live_execution: bool = False
    allow_external_llm: bool = False
    autostart_on_server_boot: bool = False


def load_long_forward_test_config(path: Union[str, Path] = "config/long_forward_test.yaml") -> LongForwardTestConfig:
    config_path = Path(path)
    if not config_path.exists():
        return LongForwardTestConfig()
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return LongForwardTestConfig()
    return LongForwardTestConfig(**data)
