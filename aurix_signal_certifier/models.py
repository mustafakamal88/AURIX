from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from aurix_bridge_server.models import utc_now_iso


SignalCertificationStatus = Literal["NO_SIGNAL", "CERTIFIED", "CERTIFIED_WITH_WARNINGS", "FAILED"]


class SignalPathCertificationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    generated_at: str = Field(default_factory=utc_now_iso)
    symbol: str
    mode: str = "CERTIFICATION_ONLY"
    status: SignalCertificationStatus = "NO_SIGNAL"
    certified_trade_id: Optional[str] = None
    certified_signal_id: Optional[str] = None
    strategy: Optional[str] = None
    strategy_version: Optional[str] = None
    direction: Optional[str] = None
    trade_status: Optional[str] = None
    snapshot_trace: dict[str, Any] = Field(default_factory=dict)
    context_trace: dict[str, Any] = Field(default_factory=dict)
    strategy_trace: dict[str, Any] = Field(default_factory=dict)
    paper_engine_trace: dict[str, Any] = Field(default_factory=dict)
    risk_trace: dict[str, Any] = Field(default_factory=dict)
    ledger_trace: dict[str, Any] = Field(default_factory=dict)
    analytics_trace: dict[str, Any] = Field(default_factory=dict)
    visibility_trace: dict[str, Any] = Field(default_factory=dict)
    passed_checks: list[str] = Field(default_factory=list)
    skipped_checks: list[str] = Field(default_factory=list)
    failed_checks: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    safety: dict[str, Any] = Field(default_factory=dict)
