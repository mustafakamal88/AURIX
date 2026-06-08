from __future__ import annotations

from typing import Any, Optional

from .config import ContextConfig


def as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def candle_direction(open_price: Optional[float], close_price: Optional[float]) -> Optional[str]:
    if open_price is None or close_price is None:
        return None
    if close_price > open_price:
        return "BULLISH"
    if close_price < open_price:
        return "BEARISH"
    return "DOJI"


def true_range(candle: dict[str, Any]) -> Optional[float]:
    high = as_float(candle.get("high"))
    low = as_float(candle.get("low"))
    if high is None or low is None:
        return None
    return high - low


def body_size(candle: dict[str, Any]) -> Optional[float]:
    open_price = as_float(candle.get("open"))
    close_price = as_float(candle.get("close"))
    if open_price is None or close_price is None:
        return None
    return abs(close_price - open_price)


def classify_regime(
    candles: list[dict[str, Any]],
    spread_points: Optional[float],
    data_quality_ok: bool,
    config: ContextConfig,
) -> dict[str, Any]:
    reasons: list[str] = []
    if not data_quality_ok:
        reasons.append("data quality not ok")
        return {
            "regime": "INSUFFICIENT_DATA",
            "directional_bias": "NEUTRAL",
            "range_high": None,
            "range_low": None,
            "last_close": None,
            "last_candle_direction": None,
            "volatility_state": "UNKNOWN",
            "reasons": reasons,
        }

    if spread_points is not None and spread_points > config.max_spread_points:
        reasons.append(f"spread {spread_points} exceeds max_spread_points {config.max_spread_points}")
        return {
            "regime": "HIGH_SPREAD",
            "directional_bias": "NEUTRAL",
            "range_high": None,
            "range_low": None,
            "last_close": None,
            "last_candle_direction": None,
            "volatility_state": "UNKNOWN",
            "reasons": reasons,
        }

    if len(candles) < config.min_candles_required:
        reasons.append(f"candles {len(candles)} below min_candles_required {config.min_candles_required}")
        return {
            "regime": "INSUFFICIENT_DATA",
            "directional_bias": "NEUTRAL",
            "range_high": None,
            "range_low": None,
            "last_close": None,
            "last_candle_direction": None,
            "volatility_state": "UNKNOWN",
            "reasons": reasons,
        }

    lookback = candles[-config.lookback_candles :]
    last = lookback[-1]
    prior_range = lookback[-(config.range_lookback_candles + 1) : -1]
    if len(prior_range) < config.range_lookback_candles:
        prior_range = lookback[:-1]

    highs = [as_float(candle.get("high")) for candle in prior_range]
    lows = [as_float(candle.get("low")) for candle in prior_range]
    last_open = as_float(last.get("open"))
    last_close = as_float(last.get("close"))
    if any(value is None for value in highs + lows) or last_close is None:
        reasons.append("required candle fields missing")
        return {
            "regime": "INSUFFICIENT_DATA",
            "directional_bias": "NEUTRAL",
            "range_high": None,
            "range_low": None,
            "last_close": last_close,
            "last_candle_direction": candle_direction(last_open, last_close),
            "volatility_state": "UNKNOWN",
            "reasons": reasons,
        }

    range_high = max(value for value in highs if value is not None)
    range_low = min(value for value in lows if value is not None)
    last_direction = candle_direction(last_open, last_close)

    if last_close > range_high:
        reasons.append("last close above range high")
        return {
            "regime": "BULLISH_BREAKOUT",
            "directional_bias": "BULLISH",
            "range_high": range_high,
            "range_low": range_low,
            "last_close": last_close,
            "last_candle_direction": last_direction,
            "volatility_state": "NORMAL",
            "reasons": reasons,
        }

    if last_close < range_low:
        reasons.append("last close below range low")
        return {
            "regime": "BEARISH_BREAKDOWN",
            "directional_bias": "BEARISH",
            "range_high": range_high,
            "range_low": range_low,
            "last_close": last_close,
            "last_candle_direction": last_direction,
            "volatility_state": "NORMAL",
            "reasons": reasons,
        }

    ranges = [true_range(candle) for candle in lookback[:-1]]
    last_range = true_range(last)
    valid_ranges = [value for value in ranges if value is not None and value > 0]
    if valid_ranges and last_range is not None:
        avg_range = sum(valid_ranges) / len(valid_ranges)
        if last_range > avg_range * config.volatility_expansion_multiplier:
            reasons.append("last candle true range expanded versus average")
            return {
                "regime": "VOLATILITY_EXPANSION",
                "directional_bias": "NEUTRAL",
                "range_high": range_high,
                "range_low": range_low,
                "last_close": last_close,
                "last_candle_direction": last_direction,
                "volatility_state": "EXPANDING",
                "reasons": reasons,
            }

    recent = lookback[-config.range_lookback_candles :]
    body_values = [body_size(candle) for candle in recent]
    range_values = [true_range(candle) for candle in recent]
    if all(value is not None for value in body_values + range_values):
        total_body = sum(value for value in body_values if value is not None)
        total_range = sum(value for value in range_values if value is not None)
        if total_range > 0 and (total_body / total_range) < 0.25:
            reasons.append("recent candle bodies small relative to ranges")
            return {
                "regime": "CHOP",
                "directional_bias": "NEUTRAL",
                "range_high": range_high,
                "range_low": range_low,
                "last_close": last_close,
                "last_candle_direction": last_direction,
                "volatility_state": "NORMAL",
                "reasons": reasons,
            }

    reasons.append("price remains inside recent range")
    return {
        "regime": "RANGE",
        "directional_bias": "NEUTRAL",
        "range_high": range_high,
        "range_low": range_low,
        "last_close": last_close,
        "last_candle_direction": last_direction,
        "volatility_state": "NORMAL",
        "reasons": reasons,
    }
