from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Union

import yaml
from pydantic import BaseModel


class DaemonConfig(BaseModel):
    enabled: bool = True
    mode: Literal["PAPER"] = "PAPER"
    symbol: str = "XAUUSDm"
    interval_seconds: float = 5
    run_context: bool = True
    run_paper_strategy: bool = True
    run_paper_update: bool = True
    run_analytics_every_loops: int = 12
    run_journal_every_loops: int = 12
    run_ai_review_every_loops: int = 60
    run_evidence_every_loops: int = 12
    allow_command_queueing: bool = False
    allow_live_execution: bool = False
    allow_external_llm: bool = False


def load_daemon_config(path: Union[str, Path] = "config/daemon.yaml") -> DaemonConfig:
    config_path = Path(path)
    if not config_path.exists():
        return DaemonConfig()
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return DaemonConfig()
    return DaemonConfig(**data)
