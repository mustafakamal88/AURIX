from __future__ import annotations

from typing import Any, Optional

from .indicators import calculate_ema


CLOSED_MARKERS = ("closed", "is_closed", "complete", "is_complete")


def _as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _has_closed_marker(candle: dict[str, Any]) -> bool:
    return any(key in candle for key in CLOSED_MARKERS)


def _is_marked_unfinished(candle: dict[str, Any]) -> bool:
    for key in CLOSED_MARKERS:
        if key in candle:
            return not bool(candle.get(key))
    return False


def closed_candles_only(candles: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    cleaned = [item for item in candles if isinstance(item, dict)]
    ignored_latest = bool(cleaned and (_is_marked_unfinished(cleaned[-1]) or not _has_closed_marker(cleaned[-1])))
    if ignored_latest:
        cleaned = cleaned[:-1]
    return [{**item, "closed": True} for item in cleaned], ignored_latest


def _premium_discount(latest_close: float, equilibrium: float, structure_range: float) -> str:
    if structure_range <= 0:
        return "EQUILIBRIUM"
    if abs(latest_close - equilibrium) <= structure_range * 0.05:
        return "EQUILIBRIUM"
    return "PREMIUM" if latest_close > equilibrium else "DISCOUNT"


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def build_closed_candle_context(candles: list[dict[str, Any]], *, symbol: str = "XAUUSDm", timeframe: str = "M15", min_candles: int = 25) -> dict[str, Any]:
    closed, ignored_latest = closed_candles_only(candles)
    available = len(closed)
    latest = closed[-1] if closed else None
    context: dict[str, Any] = {
        "symbol": symbol,
        "timeframe": timeframe,
        "latest_closed_candle": latest,
        "latest_closed_candle_timestamp": (latest or {}).get("time") or (latest or {}).get("timestamp") or (latest or {}).get("datetime"),
        "candles_25": closed[-25:],
        "candles_50": closed[-50:],
        "candles_100": closed[-100:],
        "closed_candles": closed,
        "available_candle_count": available,
        "is_closed_candle_only": True,
        "ignored_unfinished_candle": ignored_latest,
        "candle_memory_status": "READY" if available >= min_candles else "INSUFFICIENT",
        "insufficient_reason": None if available >= min_candles else "insufficient_candle_memory",
    }
    if available < min_candles or latest is None:
        context.update(
            {
                "structure_high": None,
                "structure_low": None,
                "structure_range": None,
                "equilibrium": None,
                "range_position": None,
                "premium_discount_state": "EQUILIBRIUM",
                "bull_power": 0.0,
                "bear_power": 0.0,
                "structure_bias": "BALANCED",
            }
        )
        return context

    structure_window = closed[-100:] if available >= 100 else closed[-50:] if available >= 50 else closed[-25:]
    highs = [_as_float(item.get("high")) for item in structure_window]
    lows = [_as_float(item.get("low")) for item in structure_window]
    closes = [_as_float(item.get("close")) for item in structure_window]
    if any(value is None for value in highs + lows + closes):
        context["candle_memory_status"] = "INVALID"
        context["insufficient_reason"] = "invalid_candle_data"
        return context

    numeric_highs = [float(value) for value in highs if value is not None]
    numeric_lows = [float(value) for value in lows if value is not None]
    numeric_closes = [float(value) for value in closes if value is not None]
    structure_high = max(numeric_highs)
    structure_low = min(numeric_lows)
    structure_range = structure_high - structure_low
    latest_close = float(numeric_closes[-1])
    equilibrium = structure_low + (structure_range * 0.5)
    range_position = _clamp((latest_close - structure_low) / structure_range) if structure_range else 0.5
    state = _premium_discount(latest_close, equilibrium, structure_range)

    recent = closed[-25:]
    bullish = [item for item in recent if _as_float(item.get("close"), 0.0) > _as_float(item.get("open"), 0.0)]
    bearish = [item for item in recent if _as_float(item.get("close"), 0.0) < _as_float(item.get("open"), 0.0)]
    bull_body = sum(abs(float(item.get("close")) - float(item.get("open"))) for item in bullish) / len(bullish) if bullish else 0.0
    bear_body = sum(abs(float(item.get("close")) - float(item.get("open"))) for item in bearish) / len(bearish) if bearish else 0.0
    body_total = bull_body + bear_body
    bull_body_score = bull_body / body_total if body_total else 0.5
    bear_body_score = bear_body / body_total if body_total else 0.5
    ema_values = calculate_ema([_as_float(item.get("close")) for item in recent], 8)
    latest_ema = ema_values[-1]
    prev_ema = ema_values[-4] if len(ema_values) >= 4 else None
    ema_bull = bool(latest_ema is not None and latest_close >= float(latest_ema))
    ema_slope_bull = bool(latest_ema is not None and prev_ema is not None and float(latest_ema) >= float(prev_ema))
    bull_power = _clamp((bull_body_score * 0.35) + ((1.0 - range_position) * 0.25) + (0.20 if ema_bull else 0.0) + (0.20 if ema_slope_bull else 0.0))
    bear_power = _clamp((bear_body_score * 0.35) + (range_position * 0.25) + (0.20 if not ema_bull else 0.0) + (0.20 if not ema_slope_bull else 0.0))
    if abs(bull_power - bear_power) < 0.08:
        bias = "BALANCED"
    else:
        bias = "BULLISH" if bull_power > bear_power else "BEARISH"

    context.update(
        {
            "structure_high": structure_high,
            "structure_low": structure_low,
            "structure_range": structure_range,
            "equilibrium": equilibrium,
            "range_position": range_position,
            "premium_discount_state": state,
            "bull_power": round(bull_power, 6),
            "bear_power": round(bear_power, 6),
            "structure_bias": bias,
            "bullish_candles_25": len(bullish),
            "bearish_candles_25": len(bearish),
            "avg_bullish_body_25": bull_body,
            "avg_bearish_body_25": bear_body,
        }
    )
    return context
