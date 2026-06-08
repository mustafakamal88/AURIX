from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aurix_bridge_server.models import utc_now_iso

from .config import MarketDataConfig
from .models import MarketCandle, MarketTick
from .quality import build_quality_report


class MarketDataRecorder:
    def __init__(self, data_dir: str | Path, config: MarketDataConfig):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config = config
        self.ticks_file = self.data_dir / "market_ticks.json"
        self.candles_file = self.data_dir / "market_candles_m1.json"
        self.quality_file = self.data_dir / "market_quality.json"
        for path in [self.ticks_file, self.candles_file]:
            if not path.exists():
                path.write_text("[]", encoding="utf-8")
        if not self.quality_file.exists():
            path = self.quality_file
            path.write_text("{}", encoding="utf-8")

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _write_json(self, path: Path, value: Any) -> None:
        path.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")

    def record_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        if not self.config.enabled:
            quality = build_quality_report(snapshot, self.config)
            self._write_json(self.quality_file, quality)
            return quality

        tick = snapshot.get("tick") if isinstance(snapshot.get("tick"), dict) else {}
        candles = snapshot.get("candles") if isinstance(snapshot.get("candles"), list) else []

        if self.config.record_ticks and tick:
            self.record_tick(snapshot, tick)
        if self.config.record_candles and candles:
            self.record_candles(snapshot, candles)

        quality = build_quality_report(snapshot, self.config)
        self._write_json(self.quality_file, quality)
        return quality

    def record_tick(self, snapshot: dict[str, Any], tick: dict[str, Any]) -> None:
        record = MarketTick(
            received_at=utc_now_iso(),
            snapshot_updated_at=snapshot.get("received_at"),
            symbol=str(tick.get("symbol") or self.config.symbol),
            bid=tick.get("bid"),
            ask=tick.get("ask"),
            spread_points=tick.get("spread_points") if self.config.record_spread else None,
            raw_time=tick.get("time"),
        ).model_dump()
        records = self.list_ticks()
        records.append(record)
        self._write_json(self.ticks_file, records[-self.config.max_tick_records :])

    def record_candles(self, snapshot: dict[str, Any], candles: list[Any]) -> None:
        records = self.list_candles()
        by_time = {str(record.get("time")): record for record in records if record.get("time") is not None}
        recorded_at = utc_now_iso()
        symbol = str(snapshot.get("tick", {}).get("symbol") or self.config.symbol)
        for candle in candles:
            if not isinstance(candle, dict) or candle.get("time") is None:
                continue
            record = MarketCandle(
                symbol=symbol,
                time=int(candle.get("time")),
                open=candle.get("open"),
                high=candle.get("high"),
                low=candle.get("low"),
                close=candle.get("close"),
                tick_volume=candle.get("tick_volume"),
                spread=candle.get("spread"),
                real_volume=candle.get("real_volume"),
                recorded_at=recorded_at,
            ).model_dump()
            by_time[str(record["time"])] = record

        deduped = sorted(by_time.values(), key=lambda item: int(item.get("time") or 0))
        self._write_json(self.candles_file, deduped[-self.config.max_candle_records :])

    def list_ticks(self) -> list[dict[str, Any]]:
        data = self._read_json(self.ticks_file, [])
        return data if isinstance(data, list) else []

    def list_candles(self) -> list[dict[str, Any]]:
        data = self._read_json(self.candles_file, [])
        return data if isinstance(data, list) else []

    def quality(self) -> dict[str, Any]:
        data = self._read_json(self.quality_file, {})
        return data if isinstance(data, dict) else {}

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.config.enabled,
            "symbol": self.config.symbol,
            "tick_count": len(self.list_ticks()),
            "candle_count": len(self.list_candles()),
            "quality": self.quality(),
            "config": self.config.model_dump(),
        }

    def reset(self) -> None:
        self._write_json(self.ticks_file, [])
        self._write_json(self.candles_file, [])
        self._write_json(self.quality_file, {})
