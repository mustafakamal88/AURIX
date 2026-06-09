from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AurixDecisionAction(str, Enum):
    WAIT = "WAIT"
    TRADE_LONG = "TRADE_LONG"
    TRADE_SHORT = "TRADE_SHORT"
    BLOCKED_BY_SPREAD = "BLOCKED_BY_SPREAD"
    BLOCKED_BY_RISK = "BLOCKED_BY_RISK"
    BLOCKED_BY_BROKER_STATE = "BLOCKED_BY_BROKER_STATE"
    BLOCKED_BY_SESSION = "BLOCKED_BY_SESSION"
    BLOCKED_BY_NO_SIGNAL = "BLOCKED_BY_NO_SIGNAL"
    BLOCKED_BY_LOW_CONFIDENCE = "BLOCKED_BY_LOW_CONFIDENCE"
    BLOCKED_BY_COMMAND_QUEUE_DISABLED = "BLOCKED_BY_COMMAND_QUEUE_DISABLED"
    BLOCKED_BY_EXECUTION_DISABLED = "BLOCKED_BY_EXECUTION_DISABLED"
    MANUAL_MODE_REQUIRED = "MANUAL_MODE_REQUIRED"
    SYSTEM_NOT_READY = "SYSTEM_NOT_READY"
    ERROR = "ERROR"


class AurixAutonomyMode(str, Enum):
    OBSERVE_ONLY = "OBSERVE_ONLY"
    ADVISORY_ONLY = "ADVISORY_ONLY"
    DEMO_DRY_RUN_ONLY = "DEMO_DRY_RUN_ONLY"
    DEMO_AUTONOMY_DISABLED = "DEMO_AUTONOMY_DISABLED"
    MICRO_LIVE_DISABLED = "MICRO_LIVE_DISABLED"


class AurixDecisionStatus(str, Enum):
    READY = "READY"
    BLOCKED = "BLOCKED"
    WAITING = "WAITING"
    ERROR = "ERROR"


class AurixDecisionSafety(BaseModel):
    decision_only: bool = True
    paper_trade_creation_allowed: bool = False
    order_request_creation_allowed: bool = False
    demo_command_queueing_allowed: bool = False
    mt5_command_queueing_allowed: bool = False
    demo_execution_allowed: bool = False
    live_execution_allowed: bool = False
    live_arming_allowed: bool = False
    real_account_execution_allowed: bool = False
    mt5_commands_queued: bool = False
    broker_order_created: bool = False
    broker_order_modified: bool = False
    broker_order_closed: bool = False
    paper_trade_created: bool = False
    ea_settings_modified: bool = False
    external_llm_used: bool = False
    strategy_config_mutated: bool = False


class AurixDecisionReason(BaseModel):
    code: str
    message: str


class AurixDecisionRecommendation(BaseModel):
    message: str


class AurixDecisionScore(BaseModel):
    total: float = 0.0
    signal_confidence: float = 0.0
    spread_quality: float = 0.0
    broker_cleanliness: float = 0.0
    session_quality: float = 0.0
    system_health: float = 0.0


class AurixDecisionSourceState(BaseModel):
    event_bus_available: bool = False
    strategy_agent_available: bool = False
    broker_reconciliation_available: bool = False
    demo_oms_available: bool = False
    demo_command_queue_available: bool = False
    account_available: bool = False
    market_available: bool = False


class AurixDecisionInput(BaseModel):
    runtime_state: dict[str, Any] = Field(default_factory=dict)
    strategy_agents_status: dict[str, Any] = Field(default_factory=dict)
    strategy_agent_latest: list[dict[str, Any]] = Field(default_factory=list)
    broker_reconciliation: dict[str, Any] = Field(default_factory=dict)
    demo_oms_status: dict[str, Any] = Field(default_factory=dict)
    demo_command_queue_status: dict[str, Any] = Field(default_factory=dict)
    snapshot: Optional[dict[str, Any]] = None


class AurixDecisionReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    generated_at: str = Field(default_factory=utc_now_iso)
    symbol: str = "XAUUSDm"
    mode: str = "DECISION_ONLY"
    autonomy_level: str = "ADVISORY_ONLY"
    action: AurixDecisionAction = AurixDecisionAction.WAIT
    direction: Optional[str] = None
    status: AurixDecisionStatus = AurixDecisionStatus.WAITING
    confidence: float = 0.0
    score: AurixDecisionScore = Field(default_factory=AurixDecisionScore)
    strategy: Optional[str] = None
    strategy_version: Optional[str] = None
    signal_id: Optional[str] = None
    signal_event_id: Optional[str] = None
    setup_reason: Optional[str] = None
    decision_reasons: list[AurixDecisionReason] = Field(default_factory=list)
    blocking_reasons: list[AurixDecisionReason] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[AurixDecisionRecommendation] = Field(default_factory=list)
    source_state: AurixDecisionSourceState = Field(default_factory=AurixDecisionSourceState)
    risk_view: dict[str, Any] = Field(default_factory=dict)
    execution_view: dict[str, Any] = Field(default_factory=dict)
    broker_view: dict[str, Any] = Field(default_factory=dict)
    safety: AurixDecisionSafety = Field(default_factory=AurixDecisionSafety)
    event_id: Optional[str] = None
