from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import yaml
from pydantic import BaseModel, Field


class StrategyAgentConfigEntry(BaseModel):
    id: str
    enabled: bool = True
    source_strategy: str
    mode: str = "ADAPTER_ONLY"


class StrategyAgentsConfig(BaseModel):
    enabled: bool = True
    symbol: str = "XAUUSDm"
    mode: str = "STRATEGY_OBSERVATION_ONLY"
    publish_to_event_bus: bool = True
    allow_signal_generation: bool = True
    allow_paper_trade_creation: bool = False
    allow_order_request_creation: bool = False
    allow_demo_execution: bool = False
    allow_live_arming: bool = False
    allow_live_execution: bool = False
    allow_command_queueing: bool = False
    require_event_bus_enabled: bool = True
    require_paper_mode_or_observation: bool = True
    require_command_id_null: bool = True
    registered_agents: list[StrategyAgentConfigEntry] = Field(default_factory=list)


def default_registered_agents() -> list[StrategyAgentConfigEntry]:
    return [
        StrategyAgentConfigEntry(id="xauusd_paper_v1_adapter", enabled=True, source_strategy="xauusd_paper_v1"),
        StrategyAgentConfigEntry(id="xauusd_paper_v2_adapter", enabled=True, source_strategy="xauusd_paper_v2"),
    ]


def load_strategy_agent_config(path: Union[str, Path] = "config/strategy_agents.yaml") -> StrategyAgentsConfig:
    config_path = Path(path)
    if not config_path.exists():
        return StrategyAgentsConfig(registered_agents=default_registered_agents())
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return StrategyAgentsConfig(registered_agents=default_registered_agents())
    config = StrategyAgentsConfig(**data)
    if not config.registered_agents:
        config.registered_agents = default_registered_agents()
    return config
