from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import yaml
from pydantic import BaseModel


class EvidenceMonitorConfig(BaseModel):
    enabled: bool = True
    symbol: str = "XAUUSDm"
    mode: str = "MONITOR_ONLY"
    target_closed_paper_trades: int = 50
    target_recorded_candles: int = 1000
    target_forward_days: int = 10
    target_evidence_gate_status: str = "ELIGIBLE"
    require_no_open_commands: bool = True
    require_no_open_paper_trades_for_completion: bool = True
    require_market_quality_ok: bool = True
    require_operator_ok: bool = True
    require_live_readiness_blocked_or_manual_review_only: bool = True
    allow_live_arming: bool = False
    allow_live_execution: bool = False
    allow_command_queueing: bool = False
    snapshot_history_limit: int = 500
    write_history: bool = True


def load_evidence_monitor_config(path: Union[str, Path] = "config/evidence_monitor.yaml") -> EvidenceMonitorConfig:
    config_path = Path(path)
    if not config_path.exists():
        return EvidenceMonitorConfig()
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return EvidenceMonitorConfig()
    return EvidenceMonitorConfig(**data)
