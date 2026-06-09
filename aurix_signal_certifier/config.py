from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import yaml
from pydantic import BaseModel


class SignalCertifierConfig(BaseModel):
    enabled: bool = True
    symbol: str = "XAUUSDm"
    mode: str = "CERTIFICATION_ONLY"
    certify_latest_open_trade: bool = True
    certify_latest_closed_trade: bool = True
    certify_latest_signal: bool = True
    require_command_id_null_for_paper: bool = True
    require_no_mt5_command_for_paper: bool = True
    require_paper_mode: bool = True
    require_live_execution_disabled: bool = True
    require_live_arming_disabled: bool = True
    require_ea_live_trading_disabled_now: bool = True
    allow_live_arming: bool = False
    allow_live_execution: bool = False
    allow_command_queueing: bool = False
    write_history: bool = True
    history_limit: int = 500


def load_signal_certifier_config(path: Union[str, Path] = "config/signal_certifier.yaml") -> SignalCertifierConfig:
    config_path = Path(path)
    if not config_path.exists():
        return SignalCertifierConfig()
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return SignalCertifierConfig()
    return SignalCertifierConfig(**data)
