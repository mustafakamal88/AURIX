from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


QuickValidationStatus = Literal["PASS", "WARN", "FAIL"]
QuickValidationCheckStatus = Literal["PASS", "WARN", "FAIL"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class QuickValidationCheck(BaseModel):
    name: str
    status: QuickValidationCheckStatus
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class QuickValidationSafety(BaseModel):
    paper_only: bool = True
    broker_execution_enabled: bool = False
    mt5_commands_queued: bool = False
    open_market_called: bool = False
    ea_execution_required: bool = False
    external_llm_used: bool = False
    strategy_config_mutated: bool = False


class QuickValidationReport(BaseModel):
    id: str = Field(default_factory=lambda: f"qv-{uuid4().hex[:12]}")
    generated_at: str = Field(default_factory=utc_now_iso)
    symbol: str = "XAUUSDm"
    status: QuickValidationStatus = "WARN"
    checks: list[QuickValidationCheck] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    safety: QuickValidationSafety = Field(default_factory=QuickValidationSafety)
    recommendations: list[str] = Field(default_factory=list)

