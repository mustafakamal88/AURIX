from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union


CONFIG_PATH = Path("config/demo_broker_execution.yaml")


def _bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_simple_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    result: dict[str, Any] = {}
    current_list_key: Optional[str] = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current_list_key:
            result.setdefault(current_list_key, []).append(stripped[2:].strip())
            continue
        current_list_key = None
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            result[key] = []
            current_list_key = key
        elif value.lower() == "true":
            result[key] = True
        elif value.lower() == "false":
            result[key] = False
        elif value.lower() in {"null", "none"}:
            result[key] = None
        else:
            try:
                result[key] = float(value) if "." in value else int(value)
            except ValueError:
                result[key] = value
    return result


@dataclass
class DemoBrokerExecutionConfig:
    execution_mode: str = "BROKER_EXECUTION_DISABLED"
    broker_execution_enabled: bool = False
    symbol_allowlist: list[str] = field(default_factory=lambda: ["XAUUSDm"])
    terminal_id_allowlist: list[str] = field(default_factory=lambda: ["AURIX-VPS-001"])
    max_volume: float = 0.01
    max_spread_points: float = 270.0
    risk_per_trade_percent: float = 2.0
    daily_risk_limit_percent: float = 10.0
    max_open_positions: int = 1
    allow_all_sessions: bool = True
    allow_asia_session: bool = True
    allow_london_session: bool = True
    allow_new_york_session: bool = True
    one_trade_per_day_limit: bool = False
    max_trades_per_day: Optional[int] = None
    daily_loss_limit_gbp: float = 5.0
    daily_drawdown_percent: float = 5.0
    require_stop_loss: bool = True
    require_take_profit: bool = True
    require_demo_account_verified: bool = True
    confidence_threshold: float = 0.5
    command_ttl_seconds: int = 45
    magic_number: int = 880001

    @property
    def demo_broker_execution_enabled(self) -> bool:
        return self.broker_execution_enabled

    @property
    def command_queue_enabled(self) -> bool:
        return self.broker_execution_enabled

    @property
    def live_execution_enabled(self) -> bool:
        return False

    def safety_flags(self) -> dict[str, Any]:
        return {
            "broker_execution_enabled": self.broker_execution_enabled,
            "internal_queue_controlled_by_broker_execution": True,
            "max_spread_points": self.max_spread_points,
            "risk_per_trade_percent": self.risk_per_trade_percent,
            "daily_risk_limit_percent": self.daily_risk_limit_percent,
            "max_open_positions": self.max_open_positions,
            "one_trade_per_day_limit": self.one_trade_per_day_limit,
        }


def load_demo_broker_execution_config(path: Union[str, Path] = CONFIG_PATH) -> DemoBrokerExecutionConfig:
    raw = _parse_simple_yaml(Path(path))
    broker_execution_default = bool(
        raw.get("broker_execution_enabled", raw.get("demo_broker_execution_enabled", False))
    )
    config = DemoBrokerExecutionConfig(
        execution_mode=str(raw.get("execution_mode", "BROKER_EXECUTION_DISABLED")),
        broker_execution_enabled=broker_execution_default,
        symbol_allowlist=list(raw.get("symbol_allowlist") or ["XAUUSDm"]),
        terminal_id_allowlist=list(raw.get("terminal_id_allowlist") or ["AURIX-VPS-001"]),
        max_volume=_float(raw.get("max_volume"), 0.01),
        max_spread_points=_float(raw.get("max_spread_points"), 270.0),
        risk_per_trade_percent=_float(raw.get("risk_per_trade_percent"), 2.0),
        daily_risk_limit_percent=_float(raw.get("daily_risk_limit_percent"), 10.0),
        max_open_positions=int(raw.get("max_open_positions") or 1),
        allow_all_sessions=bool(raw.get("allow_all_sessions", True)),
        allow_asia_session=bool(raw.get("allow_asia_session", True)),
        allow_london_session=bool(raw.get("allow_london_session", True)),
        allow_new_york_session=bool(raw.get("allow_new_york_session", True)),
        one_trade_per_day_limit=bool(raw.get("one_trade_per_day_limit", False)),
        max_trades_per_day=raw.get("max_trades_per_day"),
        daily_loss_limit_gbp=_float(raw.get("daily_loss_limit_gbp"), 5.0),
        daily_drawdown_percent=_float(raw.get("daily_drawdown_percent"), 5.0),
        require_stop_loss=bool(raw.get("require_stop_loss", True)),
        require_take_profit=bool(raw.get("require_take_profit", True)),
        require_demo_account_verified=bool(raw.get("require_demo_account_verified", True)),
    )
    config.broker_execution_enabled = _bool(os.getenv("AURIX_BROKER_EXECUTION", config.broker_execution_enabled))
    config.execution_mode = "BROKER_EXECUTION_ENABLED" if config.broker_execution_enabled else "BROKER_EXECUTION_DISABLED"
    return config
