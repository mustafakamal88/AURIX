from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import yaml
from pydantic import BaseModel, Field


class DecisionEngineConfig(BaseModel):
    enabled: bool = True
    symbol: str = "XAUUSDm"
    mode: str = "DECISION_ONLY"
    account_currency: str = "GBP"
    autonomy_level: str = "ADVISORY_ONLY"
    allowed_autonomy_levels: list[str] = Field(default_factory=lambda: ["OBSERVE_ONLY", "ADVISORY_ONLY", "DEMO_DRY_RUN_ONLY", "DEMO_AUTONOMY_DISABLED", "MICRO_LIVE_DISABLED"])
    allow_trade_decision: bool = True
    allow_order_request_creation: bool = False
    allow_demo_command_queueing: bool = False
    allow_mt5_command_queueing: bool = False
    allow_demo_execution: bool = False
    allow_live_execution: bool = False
    allow_live_arming: bool = False
    allow_real_account_execution: bool = False
    allow_paper_trade_creation: bool = False
    require_event_bus_state: bool = True
    require_strategy_agent_status: bool = True
    require_broker_reconciliation_clean: bool = True
    require_demo_oms_safe: bool = True
    require_demo_command_queue_safe: bool = True
    require_ea_live_trading_disabled_now: bool = True
    require_account_currency_match: bool = True
    require_symbol_match: bool = True
    min_signal_confidence: float = 0.60
    max_spread_points: float = 270
    max_broker_positions: int = 0
    max_broker_orders: int = 0
    max_daily_loss_amount: float = 1.0
    max_trades_per_day: int = 1
    block_when_command_queue_disabled: bool = False
    block_when_execution_disabled: bool = False
    strategy_priority: list[str] = Field(default_factory=lambda: ["fast_rsi_first_reversal", "xauusd_paper_v1", "xauusd_paper_v2"])
    write_history: bool = True
    history_limit: int = 1000


def load_decision_engine_config(path: Union[str, Path] = "config/decision_engine.yaml") -> DecisionEngineConfig:
    config_path = Path(path)
    if not config_path.exists():
        return DecisionEngineConfig()
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return DecisionEngineConfig()
    return DecisionEngineConfig(**data)
