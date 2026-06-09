from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class LongForwardTestStatus(BaseModel):
    enabled: bool = True
    mode: Literal["PAPER"] = "PAPER"
    running: bool = False
    started_at: Optional[str] = None
    stopped_at: Optional[str] = None
    last_heartbeat_at: Optional[str] = None
    loop_count: int = 0
    symbol: str = "XAUUSDm"
    current_session: Optional[str] = None
    session_allowed: bool = False
    orchestrator_running: bool = False
    orchestrator_loop_count: int = 0
    daemon_running: bool = False
    forward_test_status: Optional[str] = None
    forward_test_progress: float = 0.0
    recorded_candles: int = 0
    paper_open_trades: int = 0
    paper_closed_trades: int = 0
    latest_expectancy_r: float = 0.0
    evidence_status: Optional[str] = None
    evidence_live_ready: bool = False
    operator_ok: bool = False
    daily_report_generated_at: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    safety: dict[str, Any] = Field(default_factory=dict)


class LongForwardDailyReport(BaseModel):
    date: str
    generated_at: str
    sessions_observed: list[str] = Field(default_factory=list)
    candles_recorded: int = 0
    paper_trades_opened: int = 0
    paper_trades_closed: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    total_r: float = 0.0
    expectancy_r: float = 0.0
    evidence_status: Optional[str] = None
    blocking_reasons: list[str] = Field(default_factory=list)
    safety_status: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
