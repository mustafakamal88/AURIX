from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from aurix_bridge_server.models import utc_now_iso


ForwardTestStatus = Literal["NOT_STARTED", "ACTIVE", "PAUSED", "COMPLETED", "BLOCKED"]


class ForwardTestCampaign(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    symbol: str
    mode: Literal["PAPER"] = "PAPER"
    started_at: str = Field(default_factory=utc_now_iso)
    last_updated_at: str = Field(default_factory=utc_now_iso)
    status: ForwardTestStatus = "NOT_STARTED"
    days_observed: int = 0
    sessions_observed: list[str] = Field(default_factory=list)
    recorded_candles: int = 0
    paper_trades: int = 0
    closed_paper_trades: int = 0
    daemon_loops: int = 0
    operator_ok: bool = False
    evidence_status: Optional[str] = None
    progress: dict[str, Any] = Field(default_factory=dict)
    blocking_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    safety: dict[str, Any] = Field(default_factory=dict)
