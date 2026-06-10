from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import yaml
from pydantic import BaseModel, Field


class DemoCommandQueueConfig(BaseModel):
    enabled: bool = True
    symbol: str = "XAUUSDm"
    mode: str = "DEMO_COMMAND_QUEUE_DRY_RUN"
    account_currency: str = "GBP"
    allow_command_preview: bool = True
    allow_demo_command_queueing: bool = False
    allow_mt5_command_queueing: bool = False
    allow_demo_execution: bool = False
    allow_live_execution: bool = False
    allow_live_arming: bool = False
    allow_real_account_execution: bool = False
    require_manual_demo_arm: bool = True
    manual_demo_arm: bool = False
    require_demo_account: bool = True
    require_real_account_blocked: bool = True
    require_ea_live_trading_disabled_now: bool = True
    require_broker_reconciliation_clean: bool = True
    require_demo_oms_request: bool = True
    require_demo_oms_request_dry_run: bool = True
    require_signal_command_id_null: bool = True
    require_mt5_command_id_null: bool = True
    require_broker_order_id_null: bool = True
    require_symbol_match: bool = True
    require_account_currency_match: bool = True
    require_max_volume: bool = True
    require_max_trades_per_day: bool = True
    require_no_open_broker_position_for_symbol: bool = True
    require_no_open_broker_order_for_symbol: bool = True
    max_volume: float = 0.01
    max_trades_per_day: int = 1
    max_open_broker_positions: int = 0
    max_open_broker_orders: int = 0
    max_spread_points: float = 270
    max_slippage_points: int = 50
    command_ttl_seconds: int = 30
    allowed_order_types: list[str] = Field(default_factory=lambda: ["MARKET_BUY", "MARKET_SELL"])
    allowed_strategies: list[str] = Field(default_factory=lambda: ["fast_rsi_first_reversal", "xauusd_paper_v1", "xauusd_paper_v2"])
    write_history: bool = True
    history_limit: int = 500


def load_demo_command_queue_config(path: Union[str, Path] = "config/demo_command_queue.yaml") -> DemoCommandQueueConfig:
    config_path = Path(path)
    if not config_path.exists():
        return DemoCommandQueueConfig()
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return DemoCommandQueueConfig()
    return DemoCommandQueueConfig(**data)
