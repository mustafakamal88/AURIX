from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from aurix_bridge_server.models import utc_now_iso


class SupervisorStatus(BaseModel):
    enabled: bool
    mode: Literal["PAPER"] = "PAPER"
    running: bool = False
    last_heartbeat_at: str = Field(default_factory=utc_now_iso)
    last_snapshot_updated_at: Optional[str] = None
    market_quality_ok: bool = False
    context_id: Optional[str] = None
    strategy_signal_id: Optional[str] = None
    paper_created: bool = False
    paper_open_count: int = 0
    paper_closed_now_count: int = 0
    errors: list[str] = Field(default_factory=list)
    safety: dict[str, Any] = Field(default_factory=dict)
    loop_count: int = 0
