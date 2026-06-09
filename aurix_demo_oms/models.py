from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OmsOrderState(str, Enum):
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    DRY_RUN_READY = "DRY_RUN_READY"
    BLOCKED = "BLOCKED"


class DemoOmsSafety(BaseModel):
    demo_oms_only: bool = True
    dry_run_default: bool = True
    demo_execution_allowed: bool = False
    live_execution_allowed: bool = False
    live_arming_allowed: bool = False
    real_account_execution_allowed: bool = False
    command_queueing_allowed: bool = False
    demo_command_queueing_allowed: bool = False
    mt5_commands_queued: bool = False
    broker_order_created: bool = False
    paper_trade_created: bool = False
    ea_settings_modified: bool = False
    external_llm_used: bool = False
    strategy_config_mutated: bool = False


class OmsRejectionReason(BaseModel):
    code: str
    message: str


class OmsOrderIntent(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: str = Field(default_factory=utc_now_iso)
    source_signal_event_id: Optional[str] = None
    source_signal_id: Optional[str] = None
    strategy_name: Optional[str] = None
    strategy_version: Optional[str] = None
    symbol: str = "XAUUSDm"
    direction: Optional[str] = None
    order_type: Optional[str] = None
    entry_reference: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    volume: float = 0.01
    confidence: float = 0.0
    setup_reason: Optional[str] = None
    decision_trace: dict[str, Any] = Field(default_factory=dict)
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    status: OmsOrderState = OmsOrderState.CREATED
    rejection_reasons: list[OmsRejectionReason] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    safety: DemoOmsSafety = Field(default_factory=DemoOmsSafety)


class OmsValidationResult(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: str = Field(default_factory=utc_now_iso)
    intent_id: Optional[str] = None
    approved: bool = False
    status: str = "BLOCK"
    rejection_reasons: list[OmsRejectionReason] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    risk_governor_checked: bool = False
    risk_governor_approved: bool = False
    risk_governor_decision: Optional[str] = None
    spread_points: Optional[float] = None
    account_currency: Optional[str] = None
    open_oms_orders: int = 0
    trades_today: int = 0
    safety: DemoOmsSafety = Field(default_factory=DemoOmsSafety)


class OmsOrderRequest(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: str = Field(default_factory=utc_now_iso)
    intent_id: str
    symbol: str
    direction: Optional[str]
    order_type: Optional[str]
    volume: float
    entry_reference: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    status: str = "DRY_RUN_ONLY"
    mt5_command_id: Optional[str] = None
    broker_order_id: Optional[str] = None
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    safety: DemoOmsSafety = Field(default_factory=DemoOmsSafety)


class OmsExecutionPlan(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: str = Field(default_factory=utc_now_iso)
    intent_id: str
    request_id: Optional[str] = None
    mode: str = "DEMO_OMS_DRY_RUN"
    status: str = "DRY_RUN_ONLY"
    safety: DemoOmsSafety = Field(default_factory=DemoOmsSafety)


class OmsAuditRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: str = Field(default_factory=utc_now_iso)
    action: str
    intent_id: Optional[str] = None
    request_id: Optional[str] = None
    status: Optional[str] = None
    detail: dict[str, Any] = Field(default_factory=dict)
    safety: DemoOmsSafety = Field(default_factory=DemoOmsSafety)


class DemoOmsStatus(BaseModel):
    enabled: bool = True
    symbol: str = "XAUUSDm"
    mode: str = "DEMO_OMS_DRY_RUN"
    order_intent_count: int = 0
    order_request_count: int = 0
    latest_intent_status: Optional[str] = None
    latest_request_status: Optional[str] = None
    demo_execution_allowed: bool = False
    live_execution_allowed: bool = False
    command_queueing_allowed: bool = False
    demo_command_queueing_allowed: bool = False
    broker_order_created: bool = False
    mt5_commands_queued: bool = False
    paper_trade_created: bool = False
    updated_at: str = Field(default_factory=utc_now_iso)
    safety: DemoOmsSafety = Field(default_factory=DemoOmsSafety)
