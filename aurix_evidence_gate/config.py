from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import yaml
from pydantic import BaseModel


class EvidenceGateConfig(BaseModel):
    enabled: bool = True
    symbol: str = "XAUUSDm"
    minimum_closed_paper_trades: int = 50
    minimum_backtest_trades: int = 50
    minimum_recorded_candles: int = 1000
    minimum_profitable_sessions: int = 3
    minimum_expectancy_r: float = 0.10
    minimum_profit_factor: float = 1.20
    maximum_consecutive_losses: int = 5
    minimum_days_forward_tested: int = 10
    require_operator_ok: bool = True
    require_market_quality_ok: bool = True
    require_no_open_commands: bool = True
    require_live_trading_disabled: bool = True
    allow_live_readiness: bool = False


def load_evidence_gate_config(path: Union[str, Path] = "config/evidence_gate.yaml") -> EvidenceGateConfig:
    config_path = Path(path)
    if not config_path.exists():
        return EvidenceGateConfig()
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return EvidenceGateConfig()
    return EvidenceGateConfig(**data)
