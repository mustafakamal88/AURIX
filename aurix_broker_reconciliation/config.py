from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import yaml
from pydantic import BaseModel


class BrokerReconciliationConfig(BaseModel):
    enabled: bool = True
    symbol: str = "XAUUSDm"
    mode: str = "RECONCILIATION_ONLY"
    account_currency: str = "GBP"
    read_broker_account: bool = True
    read_broker_positions: bool = True
    read_broker_orders: bool = True
    read_broker_history: bool = True
    require_event_bus_enabled: bool = True
    require_demo_oms_available: bool = True
    require_ea_live_trading_disabled_now: bool = True
    allow_broker_order_creation: bool = False
    allow_broker_order_modification: bool = False
    allow_broker_order_close: bool = False
    allow_demo_execution: bool = False
    allow_live_execution: bool = False
    allow_live_arming: bool = False
    allow_command_queueing: bool = False
    allow_mt5_command_queueing: bool = False
    expected_max_broker_positions: int = 0
    expected_max_broker_orders: int = 0
    alert_on_unexpected_broker_position: bool = True
    alert_on_unexpected_broker_order: bool = True
    alert_on_account_currency_mismatch: bool = True
    alert_on_symbol_mismatch: bool = True
    write_history: bool = True
    history_limit: int = 500


def load_broker_reconciliation_config(path: Union[str, Path] = "config/broker_reconciliation.yaml") -> BrokerReconciliationConfig:
    config_path = Path(path)
    if not config_path.exists():
        return BrokerReconciliationConfig()
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return BrokerReconciliationConfig()
    return BrokerReconciliationConfig(**data)
