from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union

from .adapters import XauusdPaperV1Adapter, XauusdPaperV2Adapter
from .base import StrategyAgent
from .config import StrategyAgentsConfig
from .blackcat_cloud_v1 import BlackCatCloudV1Agent
from .fast_rsi_reversal import FastRsiFirstReversalAgent
from .models import StrategyAgentSafety, StrategyAgentSpec, StrategyRegistryStatus


def _spec_for_entry(entry: Any, symbol: str, config: StrategyAgentsConfig) -> StrategyAgentSpec:
    source = entry.source_strategy
    fast_config = config.fast_rsi_first_reversal or {}
    blackcat_config = config.blackcat_cloud_v1 or {}
    if source == "xauusd_paper_v1":
        name = "XAUUSD Paper Strategy V1 Adapter"
        version = "0.1.0"
        source_module = "aurix_strategy_engine.xauusd_paper_v1"
        strategy_type = "ADAPTER"
        timeframe = "M15"
        description = f"Read-only adapter for existing {source} output."
    elif source == "xauusd_paper_v2":
        name = "XAUUSD Paper Strategy V2 Adapter"
        version = "0.2.0"
        source_module = "aurix_strategy_engine.xauusd_paper_v2"
        strategy_type = "ADAPTER"
        timeframe = "M15"
        description = f"Read-only adapter for existing {source} output."
    elif source == "fast_rsi_first_reversal":
        name = "XAUUSDm Fast RSI First-Reversal Scalper"
        version = str(fast_config.get("strategy_version") or "1.0.0")
        source_module = "aurix_strategy_agents.fast_rsi_reversal"
        strategy_type = "STRATEGY_AGENT"
        timeframe = str(fast_config.get("timeframe") or "M1")
        description = "Observation-only Fast RSI first-reversal strategy agent."
    elif source == "blackcat_cloud_v1":
        name = "BlackCat Cloud V1"
        version = str(blackcat_config.get("strategy_version") or "1.0.0")
        source_module = "aurix_strategy_agents.blackcat_cloud_v1"
        strategy_type = "STRATEGY_AGENT"
        timeframe = str(blackcat_config.get("timeframe") or "M15")
        description = "Observation-only BlackCat EMA cloud signal provider."
    else:
        name = f"{source} Adapter"
        version = "0.1.0"
        source_module = "unknown"
        strategy_type = "ADAPTER"
        timeframe = "M15"
        description = f"Read-only adapter for existing {source} output."
    return StrategyAgentSpec(
        id=entry.id,
        name=name,
        version=version,
        symbol=symbol,
        enabled=bool(entry.enabled),
        mode=entry.mode,
        timeframe=timeframe,
        strategy_type=strategy_type,
        description=description,
        source_module=source_module,
        safety=StrategyAgentSafety(),
    )


def create_agent(spec: StrategyAgentSpec, source_strategy: str, config: StrategyAgentsConfig, data_dir: Union[str, Path]) -> StrategyAgent:
    if source_strategy == "xauusd_paper_v1":
        return XauusdPaperV1Adapter(spec)
    if source_strategy == "xauusd_paper_v2":
        return XauusdPaperV2Adapter(spec)
    if source_strategy == "fast_rsi_first_reversal":
        return FastRsiFirstReversalAgent(spec, config.fast_rsi_first_reversal, data_dir)
    if source_strategy == "blackcat_cloud_v1":
        return BlackCatCloudV1Agent(spec, config.blackcat_cloud_v1)
    raise KeyError(f"Unsupported strategy agent source_strategy: {source_strategy}")


class StrategyAgentRegistry:
    def __init__(self, config: StrategyAgentsConfig, data_dir: Union[str, Path] = "data"):
        self.config = config
        self.data_dir = Path(data_dir)
        self._agents: dict[str, StrategyAgent] = {}
        self._sources: dict[str, str] = {}
        for entry in config.registered_agents:
            spec = _spec_for_entry(entry, config.symbol, config)
            try:
                self._agents[spec.id] = create_agent(spec, entry.source_strategy, config, self.data_dir)
                self._sources[spec.id] = entry.source_strategy
            except KeyError:
                continue

    def list_registered_agents(self) -> list[StrategyAgentSpec]:
        return [agent.spec for agent in self._agents.values()]

    def get_agent(self, agent_id: str) -> Optional[StrategyAgent]:
        return self._agents.get(agent_id)

    def get_enabled_agents(self) -> list[StrategyAgent]:
        return [agent for agent in self._agents.values() if agent.spec.enabled]

    def source_strategy(self, agent_id: str) -> Optional[str]:
        return self._sources.get(agent_id)

    def get_registry_status(self, latest_status_counts: Optional[dict[str, int]] = None, last_evaluation_at: Optional[str] = None) -> StrategyRegistryStatus:
        registered = self.list_registered_agents()
        enabled = [agent for agent in registered if agent.enabled]
        return StrategyRegistryStatus(
            enabled=self.config.enabled,
            symbol=self.config.symbol,
            mode=self.config.mode,
            registered_count=len(registered),
            enabled_count=len(enabled),
            latest_exists=bool(latest_status_counts),
            latest_status_counts=latest_status_counts or {},
            last_evaluation_at=last_evaluation_at,
            event_bus_publish_enabled=bool(self.config.publish_to_event_bus),
            config=self.config.model_dump(),
            safety=StrategyAgentSafety(),
        )
