from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

import yaml
from pydantic import BaseModel, Field

from .models import StrategySignal
from .xauusd_shadow_v1 import as_dict, as_float, as_list


STRATEGY_NAME = "xauusd_paper_v2"
STRATEGY_VERSION = "0.2.0"
BLOCKED_REGIMES = {"HIGH_SPREAD", "INSUFFICIENT_DATA"}


class XauusdPaperV2Config(BaseModel):
    enabled: bool = True
    mode: str = "PAPER"
    symbol: str = "XAUUSDm"
    timeframe: str = "M1"
    min_candles: int = 30
    lookback_range_candles: int = 5
    max_spread_points: float = 280
    allowed_sessions: list[str] = Field(default_factory=lambda: ["LONDON", "NY_PRE_MARKET", "NY_OPEN", "NY_LATE"])
    block_closed_session: bool = True
    allow_buy: bool = True
    allow_sell: bool = True
    signal_cooldown_seconds: int = 180
    default_stop_points: float = 400
    default_take_profit_points: float = 600
    min_rr: float = 1.5
    require_context_quality: bool = True
    require_market_quality: bool = True
    avoid_chop: bool = True
    avoid_high_spread: bool = True
    require_reclaim_close: bool = True
    require_impulse_confirmation: bool = True
    max_signals_per_session: int = 2


def load_xauusd_paper_v2_config(path: Union[str, Path] = "config/strategy_xauusd_paper_v2.yaml") -> XauusdPaperV2Config:
    config_path = Path(path)
    if not config_path.exists():
        return XauusdPaperV2Config()
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return XauusdPaperV2Config()
    return XauusdPaperV2Config(**data)


def make_signal(
    config: XauusdPaperV2Config,
    snapshot: Optional[dict[str, Any]],
    context: Optional[dict[str, Any]],
    status: str,
    reasons: list[str],
    direction: Optional[str] = None,
    confidence: float = 0.0,
    entry_reference: Optional[float] = None,
    stop_loss_reference: Optional[float] = None,
    take_profit_reference: Optional[float] = None,
    range_high: Optional[float] = None,
    range_low: Optional[float] = None,
) -> StrategySignal:
    return StrategySignal(
        strategy_name=STRATEGY_NAME,
        strategy_version=STRATEGY_VERSION,
        mode="PAPER",
        symbol=config.symbol,
        direction=direction,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        confidence=confidence,
        entry_reference=entry_reference,
        stop_loss_reference=stop_loss_reference,
        take_profit_reference=take_profit_reference,
        reasons=reasons,
        snapshot_updated_at=snapshot.get("received_at") if snapshot else None,
        risk_checked=False,
        command_id=None,
        context_session=context.get("session_name") if context else None,
        context_regime=context.get("regime") if context else None,
        context_bias=context.get("directional_bias") if context else None,
        range_high=range_high,
        range_low=range_low,
    )


def evaluate_xauusd_paper_v2(
    snapshot: Optional[dict[str, Any]],
    context: Optional[dict[str, Any]],
    candles: list[dict[str, Any]],
    market_quality: Optional[dict[str, Any]],
    previous_signals: list[dict[str, Any]],
    config: XauusdPaperV2Config,
) -> StrategySignal:
    if not config.enabled:
        return make_signal(config, snapshot, context, "NO_SIGNAL", ["strategy disabled"])
    if config.mode != "PAPER":
        return make_signal(config, snapshot, context, "ERROR", ["strategy v2 must run in PAPER mode"])
    if snapshot is None:
        return make_signal(config, snapshot, context, "ERROR", ["latest snapshot missing"])

    tick = as_dict(snapshot.get("tick"))
    symbol = str(tick.get("symbol") or "")
    if symbol != config.symbol:
        return make_signal(config, snapshot, context, "ERROR", [f"snapshot symbol {symbol or 'missing'} does not match {config.symbol}"])

    if config.require_market_quality:
        quality = as_dict(market_quality)
        if not quality or not quality.get("ok"):
            return make_signal(config, snapshot, context, "SKIPPED_MARKET_QUALITY", [str(reason) for reason in quality.get("reasons") or ["market quality not ok"]])

    if config.require_context_quality and not context:
        return make_signal(config, snapshot, context, "SKIPPED_CONTEXT", ["context missing"])

    session = context.get("session_name") if context else None
    regime = context.get("regime") if context else None
    if config.block_closed_session and session == "CLOSED":
        return make_signal(config, snapshot, context, "SKIPPED_SESSION", ["session is CLOSED"])
    if not session or session not in config.allowed_sessions:
        return make_signal(config, snapshot, context, "SKIPPED_SESSION", [f"session {session or 'missing'} is not allowed"])
    if regime in BLOCKED_REGIMES:
        status = "SKIPPED_SPREAD" if regime == "HIGH_SPREAD" else "SKIPPED_INSUFFICIENT_DATA"
        return make_signal(config, snapshot, context, status, [f"context regime is {regime}"])
    if config.avoid_chop and regime == "CHOP":
        return make_signal(config, snapshot, context, "SKIPPED_CHOP", ["context regime is CHOP"])

    spread_points = as_float(tick.get("spread_points"))
    if spread_points is None:
        return make_signal(config, snapshot, context, "ERROR", ["spread missing"])
    if config.avoid_high_spread and spread_points > config.max_spread_points:
        return make_signal(config, snapshot, context, "SKIPPED_SPREAD", [f"spread {spread_points} exceeds max_spread_points {config.max_spread_points}"])

    source_candles = candles if candles else as_list(snapshot.get("candles"))
    source_candles = [candle for candle in source_candles if isinstance(candle, dict)]
    if len(source_candles) < config.min_candles:
        return make_signal(config, snapshot, context, "SKIPPED_INSUFFICIENT_DATA", [f"need at least {config.min_candles} candles, got {len(source_candles)}"])

    if in_v2_cooldown(config, previous_signals):
        return make_signal(config, snapshot, context, "SKIPPED_COOLDOWN", ["signal cooldown active"])
    if max_signals_for_session_reached(config, previous_signals, str(session)):
        return make_signal(config, snapshot, context, "SKIPPED_MAX_SIGNALS", [f"max signals for session {session} reached"])

    current = as_dict(source_candles[-1])
    previous = as_dict(source_candles[-2])
    prior_range = source_candles[-(config.lookback_range_candles + 2) : -2]
    if len(prior_range) < config.lookback_range_candles:
        return make_signal(config, snapshot, context, "SKIPPED_INSUFFICIENT_DATA", ["insufficient range candles"])

    highs = [as_float(candle.get("high")) for candle in prior_range]
    lows = [as_float(candle.get("low")) for candle in prior_range]
    if any(value is None for value in highs + lows):
        return make_signal(config, snapshot, context, "ERROR", ["range candle high/low missing"])
    range_high = max(value for value in highs if value is not None)
    range_low = min(value for value in lows if value is not None)

    values = {
        "current_open": as_float(current.get("open")),
        "current_high": as_float(current.get("high")),
        "current_low": as_float(current.get("low")),
        "current_close": as_float(current.get("close")),
        "previous_high": as_float(previous.get("high")),
        "previous_low": as_float(previous.get("low")),
        "previous_close": as_float(previous.get("close")),
        "bid": as_float(tick.get("bid")),
        "ask": as_float(tick.get("ask")),
    }
    if any(value is None for value in values.values()):
        return make_signal(config, snapshot, context, "ERROR", ["required candle or tick fields missing"], range_high=range_high, range_low=range_low)

    current_open = float(values["current_open"])
    current_high = float(values["current_high"])
    current_low = float(values["current_low"])
    current_close = float(values["current_close"])
    previous_high = float(values["previous_high"])
    previous_low = float(values["previous_low"])
    previous_close = float(values["previous_close"])
    bid = float(values["bid"])
    ask = float(values["ask"])
    point = as_float(tick.get("point")) or 0.01
    stop_distance = config.default_stop_points * point
    take_profit_distance = config.default_take_profit_points * point
    rr = config.default_take_profit_points / config.default_stop_points if config.default_stop_points else 0.0
    if rr < config.min_rr:
        return make_signal(config, snapshot, context, "ERROR", [f"configured rr {rr:.2f} below min_rr {config.min_rr}"], range_high=range_high, range_low=range_low)

    candle_range = max(current_high - current_low, 0.0)
    body = abs(current_close - current_open)
    meaningful_body = candle_range > 0 and body / candle_range >= 0.45
    bullish = current_close > current_open
    bearish = current_close < current_open

    if (
        config.allow_buy
        and previous_low < range_low
        and (not config.require_reclaim_close or current_close > range_low)
        and bullish
        and meaningful_body
        and (not config.require_impulse_confirmation or current_close > previous_close)
    ):
        return make_signal(
            config,
            snapshot,
            context,
            "PAPER_SIGNAL",
            ["previous candle swept range low", "current bullish candle reclaimed range low", "impulse confirmation passed"],
            direction="BUY",
            confidence=0.72,
            entry_reference=ask,
            stop_loss_reference=ask - stop_distance,
            take_profit_reference=ask + take_profit_distance,
            range_high=range_high,
            range_low=range_low,
        )

    if (
        config.allow_sell
        and previous_high > range_high
        and (not config.require_reclaim_close or current_close < range_high)
        and bearish
        and meaningful_body
        and (not config.require_impulse_confirmation or current_close < previous_close)
    ):
        return make_signal(
            config,
            snapshot,
            context,
            "PAPER_SIGNAL",
            ["previous candle swept range high", "current bearish candle reclaimed range high", "impulse confirmation passed"],
            direction="SELL",
            confidence=0.72,
            entry_reference=bid,
            stop_loss_reference=bid + stop_distance,
            take_profit_reference=bid - take_profit_distance,
            range_high=range_high,
            range_low=range_low,
        )

    return make_signal(config, snapshot, context, "NO_SIGNAL", ["no v2 sweep reclaim setup"], range_high=range_high, range_low=range_low)


def in_v2_cooldown(config: XauusdPaperV2Config, previous_signals: list[dict[str, Any]]) -> bool:
    now = datetime.now(timezone.utc)
    for signal in reversed(previous_signals):
        if signal.get("strategy_name") != STRATEGY_NAME or signal.get("symbol") != config.symbol:
            continue
        if signal.get("status") != "PAPER_SIGNAL":
            continue
        created_at = _parse_time(signal.get("created_at"))
        if created_at is None:
            continue
        return (now - created_at).total_seconds() < config.signal_cooldown_seconds
    return False


def max_signals_for_session_reached(config: XauusdPaperV2Config, previous_signals: list[dict[str, Any]], session: str) -> bool:
    count = 0
    for signal in previous_signals:
        if (
            signal.get("strategy_name") == STRATEGY_NAME
            and signal.get("symbol") == config.symbol
            and signal.get("status") == "PAPER_SIGNAL"
            and signal.get("context_session") == session
        ):
            count += 1
    return count >= config.max_signals_per_session


def _parse_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
