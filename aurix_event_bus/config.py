from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import yaml
from pydantic import BaseModel


class EventBusConfig(BaseModel):
    enabled: bool = True
    symbol: str = "XAUUSDm"
    mode: str = "EVENT_BUS_ONLY"
    write_event_log: bool = True
    write_state_snapshot: bool = True
    event_history_limit: int = 5000
    state_history_limit: int = 500
    allow_paper_trade_creation: bool = False
    allow_demo_execution: bool = False
    allow_live_arming: bool = False
    allow_live_execution: bool = False
    allow_command_queueing: bool = False
    require_paper_mode_or_observation: bool = True
    require_ea_live_trading_disabled_now: bool = True


def load_event_bus_config(path: Union[str, Path] = "config/event_bus.yaml") -> EventBusConfig:
    config_path = Path(path)
    if not config_path.exists():
        return EventBusConfig()
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return EventBusConfig()
    return EventBusConfig(**data)
