from __future__ import annotations

from .config import DecisionEngineConfig
from .models import AurixDecisionScore


def spread_quality(spread_points: float | None, max_spread_points: float) -> float:
    if spread_points is None:
        return 0.0
    if spread_points <= max_spread_points * 0.5:
        return 1.0
    if spread_points <= max_spread_points:
        return 0.5
    return 0.0


def calculate_score(*, confidence: float, spread_points: float | None, broker_clean: bool, session_ok: bool, system_ok: bool, config: DecisionEngineConfig) -> AurixDecisionScore:
    signal = max(0.0, min(float(confidence or 0.0), 1.0))
    spread = spread_quality(spread_points, config.max_spread_points)
    broker = 1.0 if broker_clean else 0.0
    session = 1.0 if session_ok else 0.0
    system = 1.0 if system_ok else 0.0
    total = signal * 0.40 + spread * 0.20 + broker * 0.20 + session * 0.10 + system * 0.10
    return AurixDecisionScore(total=round(total, 4), signal_confidence=signal, spread_quality=spread, broker_cleanliness=broker, session_quality=session, system_health=system)
