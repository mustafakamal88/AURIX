from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import yaml
from pydantic import BaseModel


class PaperRiskAuditConfig(BaseModel):
    enabled: bool = True
    symbol: str = "XAUUSDm"
    mode: str = "PAPER_AUDIT_ONLY"
    write_history: bool = True
    history_limit: int = 500
    allow_live_arming: bool = False
    allow_live_execution: bool = False
    allow_command_queueing: bool = False
    require_paper_mode: bool = True
    require_command_id_null_for_paper: bool = True


def load_paper_risk_audit_config(path: Union[str, Path] = "config/paper_risk_audit.yaml") -> PaperRiskAuditConfig:
    config_path = Path(path)
    if not config_path.exists():
        return PaperRiskAuditConfig()
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return PaperRiskAuditConfig()
    return PaperRiskAuditConfig(**data)
