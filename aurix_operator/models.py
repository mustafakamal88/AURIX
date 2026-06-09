from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class OperatorStatus(BaseModel):
    service: str
    timestamp: str
    bridge: dict[str, Any] = Field(default_factory=dict)
    account: dict[str, Any] = Field(default_factory=dict)
    market: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    risk: dict[str, Any] = Field(default_factory=dict)
    strategy: dict[str, Any] = Field(default_factory=dict)
    paper: dict[str, Any] = Field(default_factory=dict)
    paper_risk_audit: dict[str, Any] = Field(default_factory=dict)
    supervisor: dict[str, Any] = Field(default_factory=dict)
    analytics: dict[str, Any] = Field(default_factory=dict)
    journal: dict[str, Any] = Field(default_factory=dict)
    ai_review: dict[str, Any] = Field(default_factory=dict)
    backtest: dict[str, Any] = Field(default_factory=dict)
    research: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    daemon: dict[str, Any] = Field(default_factory=dict)
    forward_test: dict[str, Any] = Field(default_factory=dict)
    orchestrator: dict[str, Any] = Field(default_factory=dict)
    long_forward_test: dict[str, Any] = Field(default_factory=dict)
    live_readiness: dict[str, Any] = Field(default_factory=dict)
    evidence_growth: dict[str, Any] = Field(default_factory=dict)
    signal_certification: dict[str, Any] = Field(default_factory=dict)
    event_bus: dict[str, Any] = Field(default_factory=dict)
    strategy_agents: dict[str, Any] = Field(default_factory=dict)
    demo_oms: dict[str, Any] = Field(default_factory=dict)
    broker_reconciliation: dict[str, Any] = Field(default_factory=dict)
    demo_command_queue: dict[str, Any] = Field(default_factory=dict)
    decision_engine: dict[str, Any] = Field(default_factory=dict)
    runtime_provenance: dict[str, Any] = Field(default_factory=dict)
    evidence_integrity: dict[str, Any] = Field(default_factory=dict)
    commands: dict[str, Any] = Field(default_factory=dict)
    execution: dict[str, Any] = Field(default_factory=dict)
    safety: dict[str, Any] = Field(default_factory=dict)


class OperatorSummary(BaseModel):
    ok: bool
    mode: str = "PAPER"
    symbol: Optional[str] = None
    session: Optional[str] = None
    regime: Optional[str] = None
    spread_points: Optional[float] = None
    market_quality_ok: bool = False
    paper_open_count: int = 0
    paper_closed_trades: int = 0
    paper_win_rate: float = 0.0
    paper_total_r: float = 0.0
    paper_expectancy_r: float = 0.0
    paper_risk_decision_count: int = 0
    paper_risk_latest_status: Optional[str] = None
    paper_risk_latest_signal_id: Optional[str] = None
    paper_risk_latest_trade_id: Optional[str] = None
    supervisor_loop_count: int = 0
    journal_entry_count: int = 0
    journal_latest_classification: Optional[str] = None
    ai_review_latest_summary: Optional[str] = None
    ai_review_action_items_count: int = 0
    backtest_trade_count: int = 0
    backtest_expectancy_r: float = 0.0
    research_best_expectancy_r: float = 0.0
    research_warning_count: int = 0
    evidence_status: Optional[str] = None
    evidence_live_ready: bool = False
    evidence_blocking_reasons_count: int = 0
    daemon_running: bool = False
    daemon_loop_count: int = 0
    daemon_last_heartbeat_at: Optional[str] = None
    daemon_errors: list[str] = Field(default_factory=list)
    forward_test_status: Optional[str] = None
    forward_test_progress_percent: float = 0.0
    forward_test_closed_paper_trades: int = 0
    orchestrator_running: bool = False
    orchestrator_current_session: Optional[str] = None
    orchestrator_session_allowed: bool = False
    orchestrator_forward_test_progress: float = 0.0
    orchestrator_evidence_status: Optional[str] = None
    long_forward_test_running: bool = False
    long_forward_test_progress: float = 0.0
    long_forward_test_evidence_status: Optional[str] = None
    live_readiness_status: Optional[str] = None
    live_readiness_score: float = 0.0
    live_readiness_arming_allowed: bool = False
    live_readiness_execution_allowed: bool = False
    evidence_growth_status: Optional[str] = None
    evidence_growth_overall_progress: float = 0.0
    signal_certification_status: Optional[str] = None
    signal_certification_trade_id: Optional[str] = None
    signal_certification_strategy: Optional[str] = None
    signal_certification_direction: Optional[str] = None
    signal_certification_trade_status: Optional[str] = None
    signal_certification_warning_count: int = 0
    signal_certification_failed_count: int = 0
    v2_signal_status: Optional[str] = None
    backtest_v2_trade_count: int = 0
    backtest_v2_expectancy_r: float = 0.0
    backtest_v1_v2_expectancy_delta_r: Optional[float] = None
    event_bus_enabled: bool = False
    event_count: int = 0
    last_sequence: int = 0
    last_event_type: Optional[str] = None
    runtime_state_generated_at: Optional[str] = None
    strategy_agents_enabled: bool = False
    strategy_agents_registered: int = 0
    strategy_agents_latest_status_counts: dict[str, int] = Field(default_factory=dict)
    latest_strategy_agent_signal: Optional[str] = None
    latest_fast_rsi_status: Optional[str] = None
    demo_oms_mode: Optional[str] = None
    demo_oms_intent_count: int = 0
    demo_oms_request_count: int = 0
    demo_oms_latest_request_status: Optional[str] = None
    demo_execution_allowed: bool = False
    live_execution_allowed: bool = False
    command_queueing_allowed: bool = False
    broker_reconciliation_status: Optional[str] = None
    broker_position_count: int = 0
    broker_order_count: int = 0
    broker_mismatch_count: int = 0
    broker_warning_count: int = 0
    demo_command_queue_mode: Optional[str] = None
    demo_command_preview_count: int = 0
    demo_command_payload_count: int = 0
    demo_command_queueing_allowed: bool = False
    mt5_command_queueing_allowed: bool = False
    latest_demo_command_payload_status: Optional[str] = None
    decision_engine_action: Optional[str] = None
    decision_engine_direction: Optional[str] = None
    decision_engine_score: float = 0.0
    decision_engine_strategy: Optional[str] = None
    decision_engine_blocking_reason_count: int = 0
    decision_engine_warning_count: int = 0
    autonomy_level: Optional[str] = None
    runtime_session_id: Optional[str] = None
    runtime_started_at: Optional[str] = None
    runtime_uptime_seconds: Optional[float] = None
    runtime_session_safe: bool = True
    evidence_integrity_status: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
