from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from aurix_bridge_server.models import utc_now_iso


LiveReadinessStatus = Literal["BLOCKED", "PAPER_ONLY", "READY_FOR_MANUAL_REVIEW"]


class LiveReadinessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    generated_at: str = Field(default_factory=utc_now_iso)
    symbol: str
    mode: str = "READINESS_ONLY"
    status: LiveReadinessStatus = "BLOCKED"
    live_arming_allowed: bool = False
    live_execution_allowed: bool = False
    score: float = 0.0
    checks: dict[str, Any] = Field(default_factory=dict)
    blocking_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    manual_requirements: list[str] = Field(default_factory=list)
    micro_live_plan: dict[str, Any] = Field(default_factory=dict)
    safety: dict[str, Any] = Field(default_factory=dict)
