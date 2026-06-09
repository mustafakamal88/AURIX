from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from aurix_bridge_server.models import utc_now_iso


class AIReviewReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    generated_at: str = Field(default_factory=utc_now_iso)
    symbol: str
    mode: str
    period: str = "latest"
    summary: str
    performance_observations: list[str] = Field(default_factory=list)
    behaviour_observations: list[str] = Field(default_factory=list)
    strategy_observations: list[str] = Field(default_factory=list)
    risk_observations: list[str] = Field(default_factory=list)
    data_quality_observations: list[str] = Field(default_factory=list)
    mistake_patterns: list[str] = Field(default_factory=list)
    positive_patterns: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    blocked_items: list[str] = Field(default_factory=list)
    safety: dict[str, Any] = Field(default_factory=dict)
    source_counts: dict[str, int] = Field(default_factory=dict)
