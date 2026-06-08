from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union

import yaml
from pydantic import BaseModel, Field

from .models import StrategySignal
from .xauusd_shadow_v1 import as_dict, as_float, as_list, in_cooldown


STRATEGY_NAME = "xauusd_paper_v1"
STRATEGY_VERSION = "0.1.0"


class XauusdPaperV1Config(BaseModel):
    enabled: bool = True
    mode: str = "PAPER"
    symbol: str = "XAUUSDm"
    timeframe: str = "M1"
    min_candles: int = 20
    lookback_range_candles: int = 10
    max_spread_points: float = 350
    allowed_sessions: list[str] = Field(default_factory=lambda: ["LONDON", "NY_PRE_MARKET", "NY_OPEN", "NY_LATE"])
    block_closed_session: bool = True
    allow_buy: bool = True
    allow_sell: bool = True
    signal_cooldown_seconds: int = 120
    default_stop_points: float = 300
    default_take_profit_points: float = 600


def load_xauusd_paper_v1_config(path: Union[str, Path] = "config/strategy_xauusd_paper_v1.yaml") -> XauusdPaperV1Config:
    config_path = Path(path)
    if not config_path.exists():
        return XauusdPaperV1Config()
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return XauusdPaperV1Config()
    return XauusdPaperV1Config(**data)


def make_signal(
    config: XauusdPaperV1Config,
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
        mode=config.mode,
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


def evaluate_xauusd_paper_v1(
    snapshot: Optional[dict[str, Any]],
    context: Optional[dict[str, Any]],
    candles: list[dict[str, Any]],
    previous_signals: list[dict[str, Any]],
    config: XauusdPaperV1Config,
) -> StrategySignal:
    if not config.enabled:
        return make_signal(config, snapshot, context, "NO_SIGNAL", ["strategy disabled"])

    if snapshot is None:
        return make_signal(config, snapshot, context, "ERROR", ["latest snapshot missing"])

    tick = as_dict(snapshot.get("tick"))
    symbol = str(tick.get("symbol") or "")
    if symbol != config.symbol:
        return make_signal(config, snapshot, context, "ERROR", [f"snapshot symbol {symbol or 'missing'} does not match {config.symbol}"])

    session = context.get("session_name") if context else None
    regime = context.get("regime") if context else None
    if config.block_closed_session and session == "CLOSED":
        return make_signal(config, snapshot, context, "NO_SIGNAL", ["session is CLOSED"])
    if session and session not in config.allowed_sessions:
        return make_signal(config, snapshot, context, "NO_SIGNAL", [f"session {session} is not allowed"])

    spread_points = as_float(tick.get("spread_points"))
    if spread_points is None:
        return make_signal(config, snapshot, context, "ERROR", ["spread missing"])
    if spread_points > config.max_spread_points or regime == "HIGH_SPREAD":
        return make_signal(config, snapshot, context, "SKIPPED_SPREAD", [f"spread {spread_points} exceeds max_spread_points {config.max_spread_points}"])

    source_candles = candles if candles else as_list(snapshot.get("candles"))
    source_candles = [candle for candle in source_candles if isinstance(candle, dict)]
    if len(source_candles) < config.min_candles:
        return make_signal(config, snapshot, context, "SKIPPED_INSUFFICIENT_DATA", [f"need at least {config.min_candles} candles, got {len(source_candles)}"])

    if in_paper_cooldown(config, previous_signals):
        return make_signal(config, snapshot, context, "SKIPPED_COOLDOWN", ["signal cooldown active"])

    current = as_dict(source_candles[-1])
    previous = as_dict(source_candles[-2])
    prior_range = source_candles[-(config.lookback_range_candles + 2) : -2]
    if len(prior_range) < config.lookback_range_candles:
        prior_range = source_candles[:-2]

    highs = [as_float(candle.get("high")) for candle in prior_range]
    lows = [as_float(candle.get("low")) for candle in prior_range]
    if any(value is None for value in highs + lows):
        return make_signal(config, snapshot, context, "ERROR", ["range candle high/low missing"])
    range_high = max(value for value in highs if value is not None)
    range_low = min(value for value in lows if value is not None)

    current_open = as_float(current.get("open"))
    current_close = as_float(current.get("close"))
    previous_high = as_float(previous.get("high"))
    previous_low = as_float(previous.get("low"))
    bid = as_float(tick.get("bid"))
    ask = as_float(tick.get("ask"))
    point = as_float(tick.get("point")) or 0.01
    if None in {current_open, current_close, previous_high, previous_low, bid, ask}:
        return make_signal(config, snapshot, context, "ERROR", ["required candle or tick fields missing"])

    bullish = current_close > current_open  # type: ignore[operator]
    bearish = current_close < current_open  # type: ignore[operator]
    stop_distance = config.default_stop_points * point
    take_profit_distance = config.default_take_profit_points * point

    if config.allow_buy and previous_low < range_low and current_close > range_low and bullish:  # type: ignore[operator]
        entry = ask
        return make_signal(
            config,
            snapshot,
            context,
            "SHADOW_SIGNAL",
            ["previous candle swept range low", "current bullish candle reclaimed range low"],
            direction="BUY",
            confidence=0.68,
            entry_reference=entry,
            stop_loss_reference=entry - stop_distance,  # type: ignore[operator]
            take_profit_reference=entry + take_profit_distance,  # type: ignore[operator]
            range_high=range_high,
            range_low=range_low,
        )

    if config.allow_sell and previous_high > range_high and current_close < range_high and bearish:  # type: ignore[operator]
        entry = bid
        return make_signal(
            config,
            snapshot,
            context,
            "SHADOW_SIGNAL",
            ["previous candle swept range high", "current bearish candle reclaimed range high"],
            direction="SELL",
            confidence=0.68,
            entry_reference=entry,
            stop_loss_reference=entry + stop_distance,  # type: ignore[operator]
            take_profit_reference=entry - take_profit_distance,  # type: ignore[operator]
            range_high=range_high,
            range_low=range_low,
        )

    return make_signal(
        config,
        snapshot,
        context,
        "NO_SIGNAL",
        ["no sweep reclaim setup"],
        range_high=range_high,
        range_low=range_low,
    )


def in_paper_cooldown(config: XauusdPaperV1Config, previous_signals: list[dict[str, Any]]) -> bool:
    shim = type("CooldownConfig", (), {"symbol": config.symbol, "signal_cooldown_seconds": config.signal_cooldown_seconds})()
    return in_cooldown(shim, previous_signals)
