from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from .candle_context import CLOSED_MARKERS


TIMEFRAME_SECONDS = {
    "M1": 60,
    "M5": 300,
    "M15": 900,
}


def _as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(float(value))
    except (TypeError, ValueError):
        if isinstance(value, str):
            try:
                return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
            except ValueError:
                return None
        return None


def candle_timestamp(candle: dict[str, Any]) -> Optional[int]:
    for key in ("time", "timestamp", "datetime"):
        if key in candle and candle.get(key) is not None:
            return _as_int(candle.get(key))
    return None


def _has_closed_marker(candle: dict[str, Any]) -> bool:
    return any(key in candle for key in CLOSED_MARKERS)


def _is_closed(candle: dict[str, Any]) -> bool:
    for key in CLOSED_MARKERS:
        if key in candle:
            return bool(candle.get(key))
    return True


def detect_raw_timeframe(candles: list[dict[str, Any]]) -> str:
    timestamps = sorted({ts for item in candles if isinstance(item, dict) for ts in [candle_timestamp(item)] if ts is not None})
    deltas = [b - a for a, b in zip(timestamps, timestamps[1:]) if b > a]
    if not deltas:
        return "UNKNOWN"
    common = max(set(deltas), key=deltas.count)
    if abs(common - 60) <= 5:
        return "M1"
    if abs(common - 300) <= 10:
        return "M5"
    if abs(common - 900) <= 30:
        return "M15"
    return f"{common}s"


def _timeframe_seconds(timeframe: str) -> Optional[int]:
    return TIMEFRAME_SECONDS.get(str(timeframe).upper())


def _closed_source_candles(candles: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    cleaned = [item for item in candles if isinstance(item, dict) and candle_timestamp(item) is not None]
    cleaned.sort(key=lambda item: candle_timestamp(item) or 0)
    ignored_latest = bool(cleaned and (_has_closed_marker(cleaned[-1]) and not _is_closed(cleaned[-1])))
    if ignored_latest:
        cleaned = cleaned[:-1]
    return [{**item, "closed": True} for item in cleaned if _is_closed(item)], ignored_latest


def _resample_m1_to_m15(candles: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    buckets: dict[int, list[dict[str, Any]]] = {}
    for candle in candles:
        timestamp = candle_timestamp(candle)
        if timestamp is None:
            continue
        bucket_start = timestamp - (timestamp % TIMEFRAME_SECONDS["M15"])
        buckets.setdefault(bucket_start, []).append(candle)

    result: list[dict[str, Any]] = []
    incomplete = 0
    for bucket_start in sorted(buckets):
        bucket = sorted(buckets[bucket_start], key=lambda item: candle_timestamp(item) or 0)
        minute_slots = {((candle_timestamp(item) or 0) - bucket_start) // 60 for item in bucket}
        complete = len(bucket) >= 15 and len(minute_slots) == 15 and all(_is_closed(item) for item in bucket)
        if not complete:
            incomplete += 1
            continue
        first = bucket[0]
        last = bucket[-1]
        highs = [_as_float(item.get("high")) for item in bucket]
        lows = [_as_float(item.get("low")) for item in bucket]
        if any(value is None for value in highs + lows):
            incomplete += 1
            continue
        tick_volume = sum(int(_as_float(item.get("tick_volume") or item.get("volume"), 0.0) or 0) for item in bucket)
        real_volume_values = [_as_float(item.get("real_volume")) for item in bucket]
        candle: dict[str, Any] = {
            "symbol": last.get("symbol") or first.get("symbol"),
            "time": bucket_start,
            "open": first.get("open"),
            "high": max(float(value) for value in highs if value is not None),
            "low": min(float(value) for value in lows if value is not None),
            "close": last.get("close"),
            "tick_volume": tick_volume,
            "volume": tick_volume,
            "spread": last.get("spread"),
            "closed": True,
            "source_timeframe": "M1",
            "timeframe": "M15",
            "source_candle_count": len(bucket),
            "bucket_start": bucket_start,
            "bucket_end": bucket_start + TIMEFRAME_SECONDS["M15"],
        }
        if any(value is not None for value in real_volume_values):
            candle["real_volume"] = sum(float(value or 0.0) for value in real_volume_values)
        result.append(candle)
    return result, incomplete


def normalize_candles_for_timeframe(candles: list[dict[str, Any]], *, strategy_timeframe: str = "M15") -> dict[str, Any]:
    raw = [item for item in candles if isinstance(item, dict)]
    raw_timeframe = detect_raw_timeframe(raw)
    strategy_timeframe = str(strategy_timeframe or "M15").upper()
    source_closed, ignored_latest_raw = _closed_source_candles(raw)
    latest_raw = raw[-1] if raw else None
    latest_raw_ts = candle_timestamp(latest_raw) if isinstance(latest_raw, dict) else None

    resampled = False
    incomplete_bucket_count = 0
    normalized = source_closed
    if raw_timeframe == "M1" and strategy_timeframe == "M15":
        normalized, incomplete_bucket_count = _resample_m1_to_m15(source_closed)
        resampled = True
    elif raw_timeframe == strategy_timeframe:
        normalized = source_closed
    elif _timeframe_seconds(raw_timeframe) == _timeframe_seconds(strategy_timeframe):
        normalized = source_closed

    latest_strategy_ts = candle_timestamp(normalized[-1]) if normalized else None
    return {
        "candles": normalized,
        "raw_timeframe": raw_timeframe,
        "strategy_timeframe": strategy_timeframe,
        "resampled": resampled,
        "source_candle_count": len(raw),
        "source_closed_candle_count": len(source_closed),
        "strategy_candle_count": len(normalized),
        "latest_raw_candle_timestamp": latest_raw_ts,
        "latest_strategy_closed_candle_timestamp": latest_strategy_ts,
        "ignored_unfinished_raw_candle": ignored_latest_raw,
        "incomplete_strategy_bucket_count": incomplete_bucket_count,
        "spread_method": "latest_m1_spread_in_bucket" if resampled else "source_candle_spread",
    }
