from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class OperatorStatus(BaseModel):
    service: str
    timestamp: str
    bridge: dict[str, Any] = Field(default_factory=dict)
    account: dict[str, Any] = Field(default_factory=dict)
    market: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    risk: dict[str, Any] = Field(default_factory=dict)
    strategy: dict[str, Any] = Field(default_factory=dict)
    paper: dict[str, Any] = Field(default_factory=dict)
    supervisor: dict[str, Any] = Field(default_factory=dict)
    commands: dict[str, Any] = Field(default_factory=dict)
    execution: dict[str, Any] = Field(default_factory=dict)
    safety: dict[str, Any] = Field(default_factory=dict)


class OperatorSummary(BaseModel):
    ok: bool
    mode: str = "PAPER"
    symbol: Optional[str] = None
    session: Optional[str] = None
    regime: Optional[str] = None
    spread_points: Optional[float] = None
    market_quality_ok: bool = False
    paper_open_count: int = 0
    supervisor_loop_count: int = 0
    warnings: list[str] = Field(default_factory=list)
