from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class OrchestratorStatus(BaseModel):
    enabled: bool
    mode: Literal["PAPER"] = "PAPER"
    running: bool = False
    started_at: Optional[str] = None
    stopped_at: Optional[str] = None
    last_heartbeat_at: Optional[str] = None
    loop_count: int = 0
    symbol: str = "XAUUSDm"
    current_session: Optional[str] = None
    session_allowed: bool = False
    market_quality_ok: bool = False
    daemon_running: bool = False
    daemon_loop_count: int = 0
    forward_test_status: Optional[str] = None
    forward_test_progress: float = 0.0
    evidence_status: Optional[str] = None
    evidence_live_ready: bool = False
    operator_ok: bool = False
    actions_taken: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    safety: dict[str, Any] = Field(default_factory=dict)
