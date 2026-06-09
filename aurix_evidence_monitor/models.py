from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from aurix_bridge_server.models import utc_now_iso


EvidenceGrowthStatus = Literal["NO_DATA", "COLLECTING", "IMPROVING", "READY_FOR_READINESS_REVIEW", "BLOCKED"]


class EvidenceGrowthReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    generated_at: str = Field(default_factory=utc_now_iso)
    symbol: str
    mode: str = "MONITOR_ONLY"
    status: EvidenceGrowthStatus = "NO_DATA"
    overall_progress: float = 0.0
    targets: dict[str, Any] = Field(default_factory=dict)
    current: dict[str, Any] = Field(default_factory=dict)
    deltas: dict[str, Any] = Field(default_factory=dict)
    checkpoints: dict[str, Any] = Field(default_factory=dict)
    missing_requirements: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    safety: dict[str, Any] = Field(default_factory=dict)
