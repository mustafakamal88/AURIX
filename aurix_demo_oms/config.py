from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import yaml
from pydantic import BaseModel, Field


class DemoOmsConfig(BaseModel):
    enabled: bool = True
    symbol: str = "XAUUSDm"
    mode: str = "DEMO_OMS_DRY_RUN"
    account_currency: str = "GBP"
    allow_order_intent_creation: bool = True
    allow_order_request_event_creation: bool = True
    allow_demo_execution: bool = False
    allow_demo_command_queueing: bool = False
    allow_live_arming: bool = False
    allow_live_execution: bool = False
    allow_real_account_execution: bool = False
    allow_command_queueing: bool = False
    require_demo_account: bool = True
    require_real_account_blocked: bool = True
    require_manual_demo_arm: bool = True
    require_ea_live_trading_disabled_now: bool = True
    require_signal_command_id_null: bool = True
    require_event_bus_enabled: bool = True
    require_risk_governor_approval: bool = True
    require_strategy_signal_event: bool = True
    require_symbol_match: bool = True
    require_account_currency_match: bool = True
    require_no_open_oms_order_for_symbol: bool = True
    require_no_open_broker_position_for_symbol: bool = False
    max_volume: float = 0.01
    max_trades_per_day: int = 1
    max_open_orders: int = 1
    max_spread_points: float = 250
    max_slippage_points: float = 50
    max_daily_loss_amount: float = 1.0
    max_order_age_seconds: int = 30
    allowed_order_types: list[str] = Field(default_factory=lambda: ["MARKET_BUY", "MARKET_SELL"])
    allowed_strategies: list[str] = Field(default_factory=lambda: ["fast_rsi_first_reversal", "xauusd_paper_v1", "xauusd_paper_v2"])
    write_history: bool = True
    history_limit: int = 500


def load_demo_oms_config(path: Union[str, Path] = "config/demo_oms.yaml") -> DemoOmsConfig:
    config_path = Path(path)
    if not config_path.exists():
        return DemoOmsConfig()
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return DemoOmsConfig()
    return DemoOmsConfig(**data)
