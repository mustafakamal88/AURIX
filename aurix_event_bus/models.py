from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AurixEventType(str, Enum):
    TICK_EVENT = "TICK_EVENT"
    CANDLE_CLOSED_EVENT = "CANDLE_CLOSED_EVENT"
    ACCOUNT_STATE_EVENT = "ACCOUNT_STATE_EVENT"
    POSITION_STATE_EVENT = "POSITION_STATE_EVENT"
    ORDER_STATE_EVENT = "ORDER_STATE_EVENT"
    TRADE_HISTORY_EVENT = "TRADE_HISTORY_EVENT"
    MARKET_QUALITY_EVENT = "MARKET_QUALITY_EVENT"
    SESSION_STATE_EVENT = "SESSION_STATE_EVENT"
    CONTEXT_STATE_EVENT = "CONTEXT_STATE_EVENT"
    SIGNAL_EVENT = "SIGNAL_EVENT"
    STRATEGY_EVALUATION_EVENT = "STRATEGY_EVALUATION_EVENT"
    STRATEGY_REGISTRY_EVENT = "STRATEGY_REGISTRY_EVENT"
    RISK_DECISION_EVENT = "RISK_DECISION_EVENT"
    ORDER_REQUEST_EVENT = "ORDER_REQUEST_EVENT"
    ORDER_ACCEPTED_EVENT = "ORDER_ACCEPTED_EVENT"
    ORDER_REJECTED_EVENT = "ORDER_REJECTED_EVENT"
    ORDER_FILLED_EVENT = "ORDER_FILLED_EVENT"
    ORDER_CANCELLED_EVENT = "ORDER_CANCELLED_EVENT"
    POSITION_OPENED_EVENT = "POSITION_OPENED_EVENT"
    POSITION_UPDATED_EVENT = "POSITION_UPDATED_EVENT"
    POSITION_CLOSED_EVENT = "POSITION_CLOSED_EVENT"
    PAPER_TRADE_EVENT = "PAPER_TRADE_EVENT"
    PAPER_RISK_DECISION_EVENT = "PAPER_RISK_DECISION_EVENT"
    JOURNAL_EVENT = "JOURNAL_EVENT"
    AI_REVIEW_EVENT = "AI_REVIEW_EVENT"
    ALERT_EVENT = "ALERT_EVENT"
    SYSTEM_HEARTBEAT_EVENT = "SYSTEM_HEARTBEAT_EVENT"
    SAFETY_STATE_EVENT = "SAFETY_STATE_EVENT"
    BROKER_RECONCILIATION_EVENT = "BROKER_RECONCILIATION_EVENT"
    DEMO_COMMAND_PREVIEW_EVENT = "DEMO_COMMAND_PREVIEW_EVENT"
    DEMO_COMMAND_QUEUE_EVENT = "DEMO_COMMAND_QUEUE_EVENT"
    AURIX_DECISION_EVENT = "AURIX_DECISION_EVENT"
    AUTONOMY_STATE_EVENT = "AUTONOMY_STATE_EVENT"


EVENT_TYPES = [item.value for item in AurixEventType]


class EventSafety(BaseModel):
    event_bus_only: bool = True
    live_execution_allowed: bool = False
    live_arming_allowed: bool = False
    command_queueing_allowed: bool = False
    mt5_commands_queued: bool = False
    broker_order_created: bool = False
    ea_settings_modified: bool = False
    external_llm_used: bool = False
    strategy_config_mutated: bool = False


class AurixEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: uuid4().hex)
    event_type: AurixEventType
    event_version: int = 1
    created_at: str = Field(default_factory=utc_now_iso)
    source: str
    symbol: str = "XAUUSDm"
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    sequence: int = 0
    payload: dict[str, Any] = Field(default_factory=dict)
    safety: EventSafety = Field(default_factory=EventSafety)


class AurixRuntimeState(BaseModel):
    generated_at: str = Field(default_factory=utc_now_iso)
    symbol: str = "XAUUSDm"
    mode: str = "EVENT_BUS_ONLY"
    last_sequence: int = 0
    last_event_id: Optional[str] = None
    market: dict[str, Any] = Field(default_factory=dict)
    account: dict[str, Any] = Field(default_factory=dict)
    positions: dict[str, Any] = Field(default_factory=dict)
    orders: dict[str, Any] = Field(default_factory=dict)
    trade_history: dict[str, Any] = Field(default_factory=dict)
    session: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    strategy: dict[str, Any] = Field(default_factory=dict)
    risk: dict[str, Any] = Field(default_factory=dict)
    execution: dict[str, Any] = Field(default_factory=dict)
    paper: dict[str, Any] = Field(default_factory=dict)
    journal: dict[str, Any] = Field(default_factory=dict)
    alerts: dict[str, Any] = Field(default_factory=dict)
    safety: dict[str, Any] = Field(default_factory=lambda: EventSafety().model_dump())
    health: dict[str, Any] = Field(default_factory=dict)
