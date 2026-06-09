from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import yaml
from pydantic import BaseModel


class LiveReadinessConfig(BaseModel):
    enabled: bool = True
    symbol: str = "XAUUSDm"
    mode: str = "READINESS_ONLY"
    allow_live_arming: bool = False
    allow_live_execution: bool = False
    allow_command_queueing: bool = False
    require_evidence_gate_eligible: bool = True
    require_forward_test_completed: bool = True
    require_min_closed_paper_trades: int = 50
    require_min_recorded_candles: int = 1000
    require_min_forward_days: int = 10
    require_operator_ok: bool = True
    require_no_open_commands: bool = True
    require_market_quality_ok: bool = True
    require_ea_live_trading_disabled_now: bool = True
    require_manual_human_approval: bool = True
    require_no_open_paper_trades: bool = True
    micro_live_max_volume: float = 0.01
    micro_live_max_daily_loss_amount: float = 1.0
    micro_live_max_trades_per_day: int = 1
    micro_live_requires_new_branch: bool = True


def load_live_readiness_config(path: Union[str, Path] = "config/live_readiness.yaml") -> LiveReadinessConfig:
    config_path = Path(path)
    if not config_path.exists():
        return LiveReadinessConfig()
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return LiveReadinessConfig()
    return LiveReadinessConfig(**data)
