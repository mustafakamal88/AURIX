from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from aurix_bridge_server.models import utc_now_iso

from .config import MarketDataConfig


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


def build_quality_report(snapshot: Optional[dict[str, Any]], config: MarketDataConfig) -> dict[str, Any]:
    reasons: list[str] = []
    tick = as_dict(snapshot.get("tick")) if snapshot else {}
    candles = as_list(snapshot.get("candles")) if snapshot else []
    symbol = str(tick.get("symbol") or config.symbol)
    spread_points = as_float(tick.get("spread_points"))
    tick_present = bool(tick)

    snapshot_time = parse_time(snapshot.get("received_at")) if snapshot else None
    age_seconds: Optional[float] = None
    if snapshot_time is not None:
        age_seconds = (datetime.now(timezone.utc) - snapshot_time).total_seconds()

    snapshot_fresh = age_seconds is not None and age_seconds <= config.max_snapshot_age_seconds
    spread_ok = spread_points is not None and spread_points <= config.max_spread_points

    if not snapshot:
        reasons.append("snapshot missing")
    if not tick_present:
        reasons.append("tick missing")
    if symbol != config.symbol:
        reasons.append(f"symbol {symbol} does not match {config.symbol}")
    if len(candles) < config.min_candles_required:
        reasons.append(f"candles {len(candles)} below min_candles_required {config.min_candles_required}")
    if spread_points is None:
        reasons.append("spread missing")
    elif not spread_ok:
        reasons.append(f"spread {spread_points} exceeds max_spread_points {config.max_spread_points}")
    if not snapshot_fresh:
        reasons.append("snapshot stale")

    return {
        "ok": len(reasons) == 0,
        "symbol": symbol,
        "latest_snapshot_age_seconds": age_seconds,
        "tick_present": tick_present,
        "candles_count": len(candles),
        "spread_points": spread_points,
        "spread_ok": spread_ok,
        "snapshot_fresh": snapshot_fresh,
        "reasons": reasons,
        "updated_at": utc_now_iso(),
    }
