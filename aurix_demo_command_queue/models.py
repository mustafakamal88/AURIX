from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DemoCommandQueueSafety(BaseModel):
    demo_command_queue_only: bool = True
    dry_run_default: bool = True
    command_preview_allowed: bool = True
    demo_command_queueing_allowed: bool = False
    mt5_command_queueing_allowed: bool = False
    demo_execution_allowed: bool = False
    live_execution_allowed: bool = False
    live_arming_allowed: bool = False
    real_account_execution_allowed: bool = False
    mt5_commands_queued: bool = False
    broker_order_created: bool = False
    paper_trade_created: bool = False
    ea_settings_modified: bool = False
    external_llm_used: bool = False
    strategy_config_mutated: bool = False


class DemoCommandQueueRejection(BaseModel):
    code: str
    message: str


class DemoCommandPreview(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: str = Field(default_factory=utc_now_iso)
    source_oms_request_id: Optional[str] = None
    source_oms_intent_id: Optional[str] = None
    source_signal_id: Optional[str] = None
    source_signal_event_id: Optional[str] = None
    strategy_name: Optional[str] = None
    strategy_version: Optional[str] = None
    symbol: str = "XAUUSDm"
    direction: Optional[str] = None
    order_type: Optional[str] = None
    volume: float = 0.01
    entry_reference: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    max_slippage_points: int = 50
    ttl_seconds: int = 30
    status: str = "PREVIEW_CREATED"
    validation_status: str = "PENDING"
    rejection_reasons: list[DemoCommandQueueRejection] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    safety: DemoCommandQueueSafety = Field(default_factory=DemoCommandQueueSafety)
    provenance: dict[str, Any] = Field(default_factory=dict)


class DemoCommandValidationResult(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: str = Field(default_factory=utc_now_iso)
    preview_id: Optional[str] = None
    approved: bool = False
    status: str = "BLOCK"
    rejection_reasons: list[DemoCommandQueueRejection] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    safety: DemoCommandQueueSafety = Field(default_factory=DemoCommandQueueSafety)


class DemoMt5CommandPayload(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: str = Field(default_factory=utc_now_iso)
    preview_id: str
    command_type: str = "OPEN_MARKET"
    symbol: str
    side: Optional[str] = None
    volume: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    deviation_points: int = 50
    magic: int = 320032
    comment: str = "AURIX-DEMO-DRY-RUN"
    ttl_seconds: int = 30
    status: str = "READY_FOR_BROKER_EXECUTION"
    mt5_command_id: Optional[str] = None
    queued_at: Optional[str] = None
    broker_order_id: Optional[str] = None
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    safety: DemoCommandQueueSafety = Field(default_factory=DemoCommandQueueSafety)
    provenance: dict[str, Any] = Field(default_factory=dict)


class DemoCommandAuditRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: str = Field(default_factory=utc_now_iso)
    action: str
    preview_id: Optional[str] = None
    payload_id: Optional[str] = None
    status: Optional[str] = None
    safety: DemoCommandQueueSafety = Field(default_factory=DemoCommandQueueSafety)


class DemoCommandQueueStatus(BaseModel):
    enabled: bool = True
    symbol: str = "XAUUSDm"
    mode: str = "DEMO_COMMAND_QUEUE_DRY_RUN"
    preview_count: int = 0
    payload_count: int = 0
    latest_preview_status: Optional[str] = None
    latest_payload_status: Optional[str] = None
    demo_execution_allowed: bool = False
    live_execution_allowed: bool = False
    broker_order_created: bool = False
    mt5_commands_queued: bool = False
    updated_at: str = Field(default_factory=utc_now_iso)
    safety: DemoCommandQueueSafety = Field(default_factory=DemoCommandQueueSafety)
