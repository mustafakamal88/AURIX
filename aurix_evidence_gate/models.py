from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from aurix_bridge_server.models import utc_now_iso


EvidenceGateStatus = Literal["BLOCKED", "WATCHLIST", "ELIGIBLE_PAPER_ONLY"]


class EvidenceGateReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    generated_at: str = Field(default_factory=utc_now_iso)
    symbol: str
    status: EvidenceGateStatus = "BLOCKED"
    live_ready: bool = False
    score: float = 0.0
    checks: dict[str, Any] = Field(default_factory=dict)
    blocking_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    data_summary: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    safety: dict[str, Any] = Field(default_factory=dict)
