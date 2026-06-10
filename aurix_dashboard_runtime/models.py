from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RuntimeDashboardSafety(BaseModel):
    read_only_dashboard: bool = True
    paper_trade_creation_allowed: bool = False
    order_request_creation_allowed: bool = False
    broker_execution_enabled: bool = False
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


class AurixRuntimeDashboardSummary(BaseModel):
    generated_at: str = Field(default_factory=utc_now_iso)
    symbol: Optional[str] = None
    account: dict[str, Any] = Field(default_factory=dict)
    market: dict[str, Any] = Field(default_factory=dict)
    session: dict[str, Any] = Field(default_factory=dict)
    decision: dict[str, Any] = Field(default_factory=dict)
    strategy_agents: dict[str, Any] = Field(default_factory=dict)
    fast_rsi: dict[str, Any] = Field(default_factory=dict)
    event_bus: dict[str, Any] = Field(default_factory=dict)
    demo_oms: dict[str, Any] = Field(default_factory=dict)
    demo_command_queue: dict[str, Any] = Field(default_factory=dict)
    demo_broker_execution: dict[str, Any] = Field(default_factory=dict)
    broker_reconciliation: dict[str, Any] = Field(default_factory=dict)
    live_readiness: dict[str, Any] = Field(default_factory=dict)
    evidence_growth: dict[str, Any] = Field(default_factory=dict)
    signal_certification: dict[str, Any] = Field(default_factory=dict)
    paper_risk_audit: dict[str, Any] = Field(default_factory=dict)
    quick_validation: dict[str, Any] = Field(default_factory=dict)
    broker_execution_cockpit: dict[str, Any] = Field(default_factory=dict)
    runtime_provenance: dict[str, Any] = Field(default_factory=dict)
    evidence_integrity: dict[str, Any] = Field(default_factory=dict)
    runtime_environment: dict[str, Any] = Field(default_factory=dict)
    safety: RuntimeDashboardSafety = Field(default_factory=RuntimeDashboardSafety)
    health: str = "HEALTHY"
    health_reason: str = "runtime freshness not evaluated"
    top_blocks: list[str] = Field(default_factory=list)
    top_warnings: list[str] = Field(default_factory=list)
    next_expected_action: str = "Monitor runtime state."
