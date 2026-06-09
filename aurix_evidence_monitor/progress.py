from __future__ import annotations

from typing import Any


WEIGHTS = {
    "closed_paper_trades": 0.30,
    "recorded_candles": 0.20,
    "forward_tested_days": 0.20,
    "evidence_gate_status": 0.15,
    "command_cleanliness": 0.05,
    "market_quality": 0.05,
    "operator_status": 0.05,
}


def ratio(current: int | float, target: int | float) -> float:
    if target <= 0:
        return 1.0
    return clamp(float(current) / float(target))


def clamp(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return round(value, 6)


def weighted_progress(checkpoints: dict[str, dict[str, Any]]) -> float:
    total = 0.0
    for name, weight in WEIGHTS.items():
        total += float(checkpoints.get(name, {}).get("progress") or 0.0) * weight
    return clamp(total)
