from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Union

import yaml
from pydantic import BaseModel


class OrchestratorConfig(BaseModel):
    enabled: bool = True
    mode: Literal["PAPER"] = "PAPER"
    symbol: str = "XAUUSDm"
    interval_seconds: float = 10
    allowed_sessions: list[str] = ["LONDON", "NY_PRE_MARKET", "NY_OPEN", "NY_LATE"]
    run_daemon_during_allowed_sessions: bool = True
    update_forward_test_every_loops: int = 1
    evaluate_evidence_every_loops: int = 6
    generate_analytics_every_loops: int = 6
    generate_journal_every_loops: int = 6
    generate_ai_review_every_loops: int = 30
    stop_daemon_when_session_closed: bool = True
    allow_command_queueing: bool = False
    allow_live_execution: bool = False
    allow_external_llm: bool = False
    autostart_on_server_boot: bool = False


def load_orchestrator_config(path: Union[str, Path] = "config/orchestrator.yaml") -> OrchestratorConfig:
    config_path = Path(path)
    if not config_path.exists():
        return OrchestratorConfig()
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return OrchestratorConfig()
    return OrchestratorConfig(**data)
