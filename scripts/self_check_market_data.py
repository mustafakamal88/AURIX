from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_market_data.config import MarketDataConfig
from aurix_market_data.quality import build_quality_report
from aurix_market_data.recorder import MarketDataRecorder


def candle(time_value: int) -> dict:
    return {
        "time": time_value,
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "tick_volume": 10,
        "spread": 20,
        "real_volume": 0,
    }


def snapshot(spread: float = 20, age_seconds: float = 0, candle_count: int = 20) -> dict:
    received_at = (datetime.now(timezone.utc) - timedelta(seconds=age_seconds)).isoformat()
    return {
        "terminal_id": "AURIX-MAC-001",
        "received_at": received_at,
        "tick": {
            "symbol": "XAUUSDm",
            "bid": 100.0,
            "ask": 100.2,
            "spread_points": spread,
            "time": 123456,
        },
        "candles": [candle(i) for i in range(candle_count)],
    }


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        config = MarketDataConfig(max_tick_records=2, max_candle_records=3, max_snapshot_age_seconds=10)
        recorder = MarketDataRecorder(tmpdir, config)

        recorder.record_snapshot(snapshot(candle_count=2))
        if len(recorder.list_ticks()) != 1:
            raise AssertionError("tick recording failed")

        duplicate_snapshot = snapshot(candle_count=2)
        recorder.record_snapshot(duplicate_snapshot)
        if len(recorder.list_candles()) != 2:
            raise AssertionError("candle deduplication failed")

        recorder.record_snapshot({"received_at": datetime.now(timezone.utc).isoformat(), "tick": snapshot()["tick"], "candles": [candle(i) for i in range(10)]})
        if len(recorder.list_ticks()) != 2:
            raise AssertionError("max tick cap failed")
        if len(recorder.list_candles()) != 3:
            raise AssertionError("max candle cap failed")

        spread_quality = build_quality_report(snapshot(spread=500), config)
        if spread_quality["ok"] or not any("spread 500.0 exceeds max_spread_points" in reason for reason in spread_quality["reasons"]):
            raise AssertionError(f"spread quality fail expected, got {spread_quality}")

        stale_quality = build_quality_report(snapshot(age_seconds=60), config)
        if stale_quality["ok"] or "snapshot stale" not in stale_quality["reasons"]:
            raise AssertionError(f"stale quality fail expected, got {stale_quality}")

        healthy = build_quality_report(snapshot(), config)
        if not healthy["ok"]:
            raise AssertionError(f"healthy market quality expected, got {healthy}")

    print("OK: market data self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
