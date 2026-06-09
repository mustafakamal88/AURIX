from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


StrategyAgentResultStatus = Literal["NO_SIGNAL", "SIGNAL", "SKIPPED", "ERROR"]


class StrategyAgentSafety(BaseModel):
    strategy_observation_only: bool = True
    paper_trade_creation_allowed: bool = False
    order_request_creation_allowed: bool = False
    demo_execution_allowed: bool = False
    live_execution_allowed: bool = False
    live_arming_allowed: bool = False
    command_queueing_allowed: bool = False
    mt5_commands_queued: bool = False
    broker_order_created: bool = False
    ea_settings_modified: bool = False
    external_llm_used: bool = False
    strategy_config_mutated: bool = False


class StrategyAgentSpec(BaseModel):
    id: str
    name: str
    version: str = "0.1.0"
    symbol: str = "XAUUSDm"
    enabled: bool = True
    mode: str = "ADAPTER_ONLY"
    timeframe: str = "M15"
    strategy_type: str = "ADAPTER"
    description: str = ""
    supports_buy: bool = True
    supports_sell: bool = True
    supports_decision_trace: bool = True
    supports_event_bus: bool = True
    source_module: str = ""
    safety: StrategyAgentSafety = Field(default_factory=StrategyAgentSafety)


class StrategyAgentStatus(BaseModel):
    id: str
    enabled: bool
    mode: str
    last_status: Optional[str] = None
    last_evaluation_at: Optional[str] = None
    last_event_id: Optional[str] = None
    safety: StrategyAgentSafety = Field(default_factory=StrategyAgentSafety)


class StrategyEvaluationInput(BaseModel):
    agent_id: str
    symbol: str = "XAUUSDm"
    runtime_state: dict[str, Any] = Field(default_factory=dict)
    latest_signal: Optional[dict[str, Any]] = None
    candles: list[dict[str, Any]] = Field(default_factory=list)
    context: Optional[dict[str, Any]] = None


class StrategyDecisionTrace(BaseModel):
    available: bool = False
    data: dict[str, Any] = Field(default_factory=dict)


class StrategyRejectionReason(BaseModel):
    code: str
    message: str


class StrategySignalCandidate(BaseModel):
    signal_id: str = Field(default_factory=lambda: uuid4().hex)
    agent_id: str
    strategy_name: str
    strategy_version: str
    symbol: str
    direction: Optional[str] = None
    status: str = "NO_SIGNAL"
    confidence: float = 0.0
    entry_reference: Optional[float] = None
    stop_loss_reference: Optional[float] = None
    take_profit_reference: Optional[float] = None
    setup_reason: Optional[str] = None
    decision_trace: Optional[dict[str, Any]] = None
    command_id: Optional[str] = None


class StrategyEvaluationResult(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    generated_at: str = Field(default_factory=utc_now_iso)
    agent_id: str
    strategy_name: str
    strategy_version: str
    symbol: str = "XAUUSDm"
    mode: str = "STRATEGY_OBSERVATION_ONLY"
    status: StrategyAgentResultStatus = "NO_SIGNAL"
    direction: Optional[str] = None
    confidence: float = 0.0
    entry_reference: Optional[float] = None
    stop_loss_reference: Optional[float] = None
    take_profit_reference: Optional[float] = None
    setup_reason: Optional[str] = None
    decision_trace: Optional[dict[str, Any]] = None
    rejection_reasons: list[StrategyRejectionReason] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    event_id: Optional[str] = None
    correlation_id: Optional[str] = None
    command_id: Optional[str] = None
    safety: StrategyAgentSafety = Field(default_factory=StrategyAgentSafety)


class StrategyRegistryStatus(BaseModel):
    enabled: bool = True
    symbol: str = "XAUUSDm"
    mode: str = "STRATEGY_OBSERVATION_ONLY"
    registered_count: int = 0
    enabled_count: int = 0
    latest_exists: bool = False
    latest_status_counts: dict[str, int] = Field(default_factory=dict)
    last_evaluation_at: Optional[str] = None
    event_bus_publish_enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)
    safety: StrategyAgentSafety = Field(default_factory=StrategyAgentSafety)
