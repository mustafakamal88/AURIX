from __future__ import annotations

from typing import Any

from .config import ForwardTestConfig


def progress_summary(config: ForwardTestConfig, values: dict[str, Any]) -> dict[str, Any]:
    days = _ratio(int(values.get("days_observed") or 0), config.target_days)
    trades = _ratio(int(values.get("closed_paper_trades") or 0), config.target_closed_paper_trades)
    candles = _ratio(int(values.get("recorded_candles") or 0), config.target_recorded_candles)
    sessions = _ratio(len(values.get("sessions_observed") or []), config.minimum_sessions_covered)
    components = {
        "days": days,
        "closed_paper_trades": trades,
        "recorded_candles": candles,
        "sessions": sessions,
    }
    return {
        "percent": round(sum(components.values()) / len(components) * 100, 2),
        "components": components,
    }


def _ratio(value: int, target: int) -> float:
    if target <= 0:
        return 1.0
    return min(round(value / target, 6), 1.0)
