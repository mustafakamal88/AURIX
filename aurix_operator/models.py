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
    warnings: list[str] = Field(default_factory=list)
