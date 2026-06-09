from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class DaemonStatus(BaseModel):
    enabled: bool
    mode: Literal["PAPER"] = "PAPER"
    running: bool = False
    started_at: Optional[str] = None
    stopped_at: Optional[str] = None
    last_heartbeat_at: Optional[str] = None
    loop_count: int = 0
    last_snapshot_updated_at: Optional[str] = None
    market_quality_ok: bool = False
    last_context_id: Optional[str] = None
    last_signal_id: Optional[str] = None
    last_paper_created: bool = False
    open_paper_trades: int = 0
    last_analytics_generated_at: Optional[str] = None
    last_journal_updated_at: Optional[str] = None
    last_ai_review_id: Optional[str] = None
    last_evidence_status: Optional[str] = None
    errors: list[str] = Field(default_factory=list)
    safety: dict[str, Any] = Field(default_factory=dict)
