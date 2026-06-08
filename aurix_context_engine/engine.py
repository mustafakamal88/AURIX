from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from .config import ContextConfig
from .models import ContextSnapshot
from .regime import as_float, classify_regime
from .session import classify_session


class ContextEngine:
    def __init__(self, data_dir: str | Path, config: ContextConfig):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config = config
        self.context_file = self.data_dir / "context_snapshots.json"
        if not self.context_file.exists():
            self.context_file.write_text("[]", encoding="utf-8")

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _write_json(self, path: Path, value: Any) -> None:
        path.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")

    def history(self) -> list[dict[str, Any]]:
        data = self._read_json(self.context_file, [])
        return data if isinstance(data, list) else []

    def latest(self) -> Optional[dict[str, Any]]:
        items = self.history()
        return items[-1] if items else None

    def reset(self) -> None:
        self._write_json(self.context_file, [])

    def evaluate(
        self,
        snapshot: Optional[dict[str, Any]],
        recorded_candles: list[dict[str, Any]],
        market_quality: dict[str, Any],
    ) -> ContextSnapshot:
        tick = snapshot.get("tick", {}) if snapshot else {}
        snapshot_candles = snapshot.get("candles", []) if snapshot else []
        candles = recorded_candles if recorded_candles else snapshot_candles
        candles = [candle for candle in candles if isinstance(candle, dict)]
        spread_points = as_float(tick.get("spread_points")) if isinstance(tick, dict) else None
        data_quality_ok = self._quality_for_regime(snapshot, market_quality)
        session_name, session_open, market_open = classify_session(snapshot.get("received_at") if snapshot else None, self.config)
        regime = classify_regime(candles, spread_points, data_quality_ok, self.config)
        spread_ok = spread_points is not None and spread_points <= self.config.max_spread_points

        reasons = list(regime["reasons"])
        if not spread_ok:
            reasons.append("spread not ok")
        if not data_quality_ok:
            reasons.append("data quality not ok")

        return ContextSnapshot(
            symbol=str(tick.get("symbol") if isinstance(tick, dict) and tick.get("symbol") else self.config.symbol),
            session_name=session_name,  # type: ignore[arg-type]
            session_open=session_open,
            market_open=market_open,
            spread_points=spread_points,
            spread_ok=spread_ok,
            data_quality_ok=data_quality_ok,
            regime=regime["regime"],  # type: ignore[arg-type]
            directional_bias=regime["directional_bias"],  # type: ignore[arg-type]
            range_high=regime["range_high"],
            range_low=regime["range_low"],
            last_close=regime["last_close"],
            last_candle_direction=regime["last_candle_direction"],  # type: ignore[arg-type]
            volatility_state=regime["volatility_state"],  # type: ignore[arg-type]
            reasons=reasons,
            snapshot_updated_at=snapshot.get("received_at") if snapshot else None,
        )

    def store(self, context: ContextSnapshot) -> None:
        items = self.history()
        items.append(context.model_dump())
        self._write_json(self.context_file, items)

    def status(self) -> dict[str, Any]:
        latest = self.latest()
        return {
            "enabled": self.config.enabled,
            "symbol": self.config.symbol,
            "contexts_count": len(self.history()),
            "latest": latest,
            "config": self.config.model_dump(),
        }

    def _snapshot_quality(self, snapshot: Optional[dict[str, Any]]) -> bool:
        if not snapshot:
            return False
        tick = snapshot.get("tick")
        candles = snapshot.get("candles")
        spread = as_float(tick.get("spread_points")) if isinstance(tick, dict) else None
        return (
            isinstance(tick, dict)
            and isinstance(candles, list)
            and len(candles) >= self.config.min_candles_required
            and spread is not None
            and spread <= self.config.max_spread_points
        )

    def _quality_for_regime(self, snapshot: Optional[dict[str, Any]], market_quality: dict[str, Any]) -> bool:
        if market_quality.get("ok"):
            return True
        reasons = market_quality.get("reasons") or []
        non_spread_reasons = [reason for reason in reasons if not str(reason).startswith("spread ")]
        if market_quality and not non_spread_reasons:
            return True
        return self._snapshot_quality(snapshot)
