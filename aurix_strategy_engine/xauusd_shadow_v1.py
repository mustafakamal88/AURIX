from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from .config import StrategyConfig
from .models import StrategySignal


STRATEGY_NAME = "xauusd_shadow_v1"
STRATEGY_VERSION = "0.1.0"


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


def parse_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def recent_shadow_signals(signals: list[dict[str, Any]], symbol: str) -> list[dict[str, Any]]:
    return [
        signal
        for signal in signals
        if signal.get("symbol") == symbol and signal.get("status") == "SHADOW_SIGNAL"
    ]


def in_cooldown(config: StrategyConfig, previous_signals: list[dict[str, Any]]) -> bool:
    shadow_signals = recent_shadow_signals(previous_signals, config.symbol)
    if not shadow_signals:
        return False

    latest = max(shadow_signals, key=lambda item: str(item.get("created_at", "")))
    created_at = parse_time(latest.get("created_at"))
    if created_at is None:
        return False

    age_seconds = (datetime.now(timezone.utc) - created_at).total_seconds()
    return age_seconds < config.signal_cooldown_seconds


def make_signal(
    config: StrategyConfig,
    status: str,
    snapshot: dict[str, Any],
    reasons: list[str],
    direction: Optional[str] = None,
    confidence: float = 0.0,
    entry_reference: Optional[float] = None,
    stop_loss_reference: Optional[float] = None,
    take_profit_reference: Optional[float] = None,
) -> StrategySignal:
    return StrategySignal(
        strategy_name=STRATEGY_NAME,
        strategy_version=STRATEGY_VERSION,
        mode=config.mode,
        symbol=config.symbol,
        direction=direction,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        confidence=confidence,
        entry_reference=entry_reference,
        stop_loss_reference=stop_loss_reference,
        take_profit_reference=take_profit_reference,
        reasons=reasons,
        snapshot_updated_at=snapshot.get("received_at"),
        risk_checked=False,
        command_id=None,
    )


def evaluate_xauusd_shadow_v1(
    snapshot: Optional[dict[str, Any]],
    config: StrategyConfig,
    previous_signals: list[dict[str, Any]],
) -> StrategySignal:
    if not config.enabled:
        return make_signal(config, "NO_SIGNAL", snapshot or {}, ["strategy disabled"])

    if snapshot is None:
        return make_signal(config, "ERROR", {}, ["latest snapshot missing"])

    tick = as_dict(snapshot.get("tick"))
    candles = as_list(snapshot.get("candles"))
    symbol = str(tick.get("symbol") or "")

    if symbol != config.symbol:
        return make_signal(config, "ERROR", snapshot, [f"snapshot symbol {symbol or 'missing'} does not match {config.symbol}"])

    if len(candles) < config.min_candles:
        return make_signal(
            config,
            "SKIPPED_INSUFFICIENT_DATA",
            snapshot,
            [f"need at least {config.min_candles} candles, got {len(candles)}"],
        )

    spread_points = as_float(tick.get("spread_points"))
    if spread_points is None:
        return make_signal(config, "ERROR", snapshot, ["spread missing"])
    if spread_points > config.max_spread_points:
        return make_signal(
            config,
            "SKIPPED_SPREAD",
            snapshot,
            [f"spread {spread_points} exceeds max_spread_points {config.max_spread_points}"],
        )

    bid = as_float(tick.get("bid"))
    ask = as_float(tick.get("ask"))
    if bid is None or bid <= 0 or ask is None or ask <= 0:
        return make_signal(config, "ERROR", snapshot, ["bid/ask missing or invalid"])

    if in_cooldown(config, previous_signals):
        return make_signal(config, "SKIPPED_COOLDOWN", snapshot, ["signal cooldown active"])

    last = as_dict(candles[-1])
    previous = as_dict(candles[-2])
    recent = [as_dict(candle) for candle in candles[-10:]]

    last_open = as_float(last.get("open"))
    last_close = as_float(last.get("close"))
    previous_high = as_float(previous.get("high"))
    previous_low = as_float(previous.get("low"))

    if None in {last_open, last_close, previous_high, previous_low}:
        return make_signal(config, "ERROR", snapshot, ["required candle fields missing"])

    recent_highs = [as_float(candle.get("high")) for candle in recent]
    recent_lows = [as_float(candle.get("low")) for candle in recent]
    if any(value is None for value in recent_highs) or any(value is None for value in recent_lows):
        return make_signal(config, "ERROR", snapshot, ["recent high/low fields missing"])

    recent_high = max(value for value in recent_highs if value is not None)
    recent_low = min(value for value in recent_lows if value is not None)

    bullish = last_close > last_open  # type: ignore[operator]
    bearish = last_close < last_open  # type: ignore[operator]

    if config.allow_buy and bullish and last_close > previous_high:  # type: ignore[operator]
        return make_signal(
            config,
            "SHADOW_SIGNAL",
            snapshot,
            ["bullish close above previous candle high", f"recent_high={recent_high}", f"spread_points={spread_points}"],
            direction="BUY",
            confidence=0.62,
            entry_reference=ask,
            stop_loss_reference=recent_low,
            take_profit_reference=recent_high,
        )

    if config.allow_sell and bearish and last_close < previous_low:  # type: ignore[operator]
        return make_signal(
            config,
            "SHADOW_SIGNAL",
            snapshot,
            ["bearish close below previous candle low", f"recent_low={recent_low}", f"spread_points={spread_points}"],
            direction="SELL",
            confidence=0.62,
            entry_reference=bid,
            stop_loss_reference=recent_high,
            take_profit_reference=recent_low,
        )

    return make_signal(config, "NO_SIGNAL", snapshot, ["no deterministic breakout condition met"])
