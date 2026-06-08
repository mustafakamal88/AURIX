from __future__ import annotations

from typing import Any, Optional

from .config import StrategyConfig
from .models import StrategySignal
from .xauusd_shadow_v1 import STRATEGY_NAME, STRATEGY_VERSION, evaluate_xauusd_shadow_v1


class StrategyEngine:
    def __init__(self, config: StrategyConfig):
        self.config = config
        self.strategy_name = STRATEGY_NAME
        self.strategy_version = STRATEGY_VERSION

    def evaluate(
        self,
        snapshot: Optional[dict[str, Any]],
        previous_signals: list[dict[str, Any]],
    ) -> StrategySignal:
        return evaluate_xauusd_shadow_v1(snapshot, self.config, previous_signals)

    def status(self, snapshot: Optional[dict[str, Any]], signals: list[dict[str, Any]]) -> dict[str, Any]:
        tick = snapshot.get("tick", {}) if snapshot else {}
        candles = snapshot.get("candles", []) if snapshot else []
        latest_signal = signals[-1] if signals else None
        return {
            "enabled": self.config.enabled,
            "mode": self.config.mode,
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "symbol": self.config.symbol,
            "timeframe": self.config.timeframe,
            "snapshot_received_at": snapshot.get("received_at") if snapshot else None,
            "snapshot_symbol": tick.get("symbol") if isinstance(tick, dict) else None,
            "candles": len(candles) if isinstance(candles, list) else 0,
            "spread_points": tick.get("spread_points") if isinstance(tick, dict) else None,
            "signals_count": len(signals),
            "latest_signal": latest_signal,
            "config": self.config.model_dump(),
        }
