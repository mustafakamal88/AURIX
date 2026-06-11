from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BrokerReconciliationSafety(BaseModel):
    reconciliation_only: bool = True
    broker_order_creation_allowed: bool = False
    broker_order_modification_allowed: bool = False
    broker_order_close_allowed: bool = False
    demo_execution_allowed: bool = False
    live_execution_allowed: bool = False
    live_arming_allowed: bool = False
    command_queueing_allowed: bool = False
    mt5_commands_queued: bool = False
    broker_order_created: bool = False
    broker_order_modified: bool = False
    broker_order_closed: bool = False
    paper_trade_created: bool = False
    ea_settings_modified: bool = False
    external_llm_used: bool = False
    strategy_config_mutated: bool = False


class BrokerAccountSnapshot(BaseModel):
    balance: Optional[float] = None
    equity: Optional[float] = None
    currency: Optional[str] = None
    login: Optional[Any] = None
    server: Optional[str] = None
    raw: dict[str, Any] = Field(default_factory=dict)


class BrokerPositionSnapshot(BaseModel):
    ticket: Optional[Any] = None
    symbol: Optional[str] = None
    type: Optional[Any] = None
    direction: Optional[str] = None
    volume: Optional[float] = None
    price_open: Optional[float] = None
    profit: Optional[float] = None
    raw: dict[str, Any] = Field(default_factory=dict)


class BrokerOrderSnapshot(BaseModel):
    ticket: Optional[Any] = None
    symbol: Optional[str] = None
    type: Optional[Any] = None
    direction: Optional[str] = None
    volume: Optional[float] = None
    price_open: Optional[float] = None
    raw: dict[str, Any] = Field(default_factory=dict)


class BrokerHistorySnapshot(BaseModel):
    available: bool = False
    count: int = 0
    latest: Optional[dict[str, Any]] = None


class AurixExpectedState(BaseModel):
    symbol: str = "XAUUSDm"
    expected_broker_positions: int = 0
    expected_broker_orders: int = 0
    demo_oms_request_count: int = 0
    latest_demo_oms_request_status: Optional[str] = None
    order_requests_with_mt5_command_id: int = 0
    order_requests_with_broker_order_id: int = 0
    executed_order_request_count: int = 0
    order_filled_event_count: int = 0


class ReconciliationCheck(BaseModel):
    name: str
    status: Literal["PASS", "WARN", "FAIL", "BLOCKED"]
    message: str


class ReconciliationMismatch(BaseModel):
    code: str
    message: str
    severity: Literal["WARNING", "MISMATCH", "BLOCKED"] = "MISMATCH"
    detail: dict[str, Any] = Field(default_factory=dict)


class BrokerReconciliationReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    generated_at: str = Field(default_factory=utc_now_iso)
    symbol: str = "XAUUSDm"
    mode: str = "RECONCILIATION_ONLY"
    status: Literal["CLEAN", "DIRTY", "UNKNOWN", "WARNINGS", "MISMATCH", "BLOCKED", "NO_BROKER_DATA"] = "UNKNOWN"
    account_login_masked: Optional[str] = None
    server: Optional[str] = None
    snapshot_age_seconds: Optional[float] = None
    positions_count: int = 0
    orders_count: int = 0
    expected_positions_count: int = 0
    expected_orders_count: int = 0
    unexpected_exposure: bool = False
    mismatches_count: int = 0
    dirty_evidence_found: bool = False
    reasons: list[str] = Field(default_factory=list)
    account: Optional[BrokerAccountSnapshot] = None
    broker_positions: list[BrokerPositionSnapshot] = Field(default_factory=list)
    broker_orders: list[BrokerOrderSnapshot] = Field(default_factory=list)
    broker_history_summary: BrokerHistorySnapshot = Field(default_factory=BrokerHistorySnapshot)
    aurix_expected_state: AurixExpectedState = Field(default_factory=AurixExpectedState)
    checks: list[ReconciliationCheck] = Field(default_factory=list)
    mismatches: list[ReconciliationMismatch] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    event_id: Optional[str] = None
    safety: BrokerReconciliationSafety = Field(default_factory=BrokerReconciliationSafety)
