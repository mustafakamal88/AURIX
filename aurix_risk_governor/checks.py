from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from aurix_bridge_server.models import Command, LIVE_CONFIRM_PHRASE

from .config import RiskConfig


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_test_command(command: Command) -> bool:
    text = f"{command.comment or ''}".upper()
    return any(marker in text for marker in ["TEST", "DRY", "SIM", "PAPER"])


def trades_today(decisions: list[dict[str, Any]]) -> int:
    today = datetime.now(timezone.utc).date()
    count = 0
    for decision in decisions:
        if not decision.get("approved"):
            continue
        created_at = str(decision.get("created_at", ""))
        try:
            created_date = datetime.fromisoformat(created_at).date()
        except ValueError:
            continue
        if created_date == today:
            count += 1
    return count


def evaluate_command(
    command: Command,
    snapshot: Optional[dict[str, Any]],
    config: RiskConfig,
    previous_decisions: list[dict[str, Any]],
) -> tuple[list[str], dict[str, Any]]:
    reasons: list[str] = []
    context: dict[str, Any] = {
        "spread_points": None,
        "open_positions": 0,
        "equity": None,
        "balance": None,
    }

    if not config.enabled:
        return reasons, context

    if snapshot is None:
        reasons.append("account snapshot missing")
        return reasons, context

    account = as_dict(snapshot.get("account"))
    tick = as_dict(snapshot.get("tick"))
    positions = as_list(snapshot.get("positions"))

    context["open_positions"] = len(positions)
    context["equity"] = as_float(account.get("equity"))
    context["balance"] = as_float(account.get("balance"))
    context["spread_points"] = as_float(tick.get("spread_points"))

    if not account:
        reasons.append("account snapshot missing")

    if not tick:
        reasons.append("tick missing")

    if context["spread_points"] is None:
        reasons.append("spread missing")

    symbol = command.symbol
    direction = command.direction
    volume = command.volume

    if symbol not in config.allowed_symbols:
        reasons.append(f"symbol not allowed: {symbol}")

    if direction not in config.allowed_directions:
        reasons.append(f"direction not allowed: {direction}")

    if volume is None or volume <= 0:
        reasons.append("volume must be greater than zero")
    elif volume > config.max_volume:
        reasons.append(f"volume {volume} exceeds max_volume {config.max_volume}")

    if len(positions) >= config.max_open_positions:
        reasons.append(f"open positions {len(positions)} reached max_open_positions {config.max_open_positions}")

    spread_points = context["spread_points"]
    if spread_points is not None and spread_points > config.max_spread_points:
        reasons.append(f"spread {spread_points} exceeds max_spread_points {config.max_spread_points}")

    if config.require_stop_loss and command.sl is None:
        reasons.append("stop loss is required")

    if config.require_take_profit and command.tp is None:
        reasons.append("take profit is required")

    if not config.live_trading_allowed and command.live_confirm == LIVE_CONFIRM_PHRASE and not is_test_command(command):
        reasons.append("live execution commands are blocked by Risk Governor")

    balance = context["balance"]
    equity = context["equity"]
    if balance is not None and equity is not None:
        current_loss = max(0.0, balance - equity)
        if current_loss >= config.max_daily_loss_amount:
            reasons.append(f"daily loss amount {current_loss} reached max_daily_loss_amount {config.max_daily_loss_amount}")
        if balance > 0:
            loss_percent = (current_loss / balance) * 100
            if loss_percent >= config.max_daily_loss_percent:
                reasons.append(f"daily loss percent {loss_percent:.2f} reached max_daily_loss_percent {config.max_daily_loss_percent}")

    today_trades = trades_today(previous_decisions)
    if today_trades >= config.max_trades_per_day:
        reasons.append(f"approved trades today {today_trades} reached max_trades_per_day {config.max_trades_per_day}")

    return reasons, context
