from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_strategy_engine.config import StrategyConfig
from aurix_strategy_engine.engine import StrategyEngine


def candle(i: int, open_: float, high: float, low: float, close: float) -> dict:
    return {
        "time": i,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "tick_volume": 100,
        "spread": 100,
        "real_volume": 0,
    }


def base_snapshot(candles: list[dict], spread: float = 100) -> dict:
    return {
        "terminal_id": "AURIX-MAC-001",
        "received_at": "2026-06-08T20:00:00+00:00",
        "tick": {
            "symbol": "XAUUSDm",
            "bid": 2300.10,
            "ask": 2300.30,
            "spread_points": spread,
        },
        "candles": candles,
        "account": {"balance": 1000, "equity": 1000},
        "positions": [],
        "orders": [],
        "deals": [],
        "raw": {},
    }


def normal_candles() -> list[dict]:
    return [candle(i, 2290 + i * 0.1, 2291 + i * 0.1, 2289 + i * 0.1, 2290.5 + i * 0.1) for i in range(20)]


def assert_status(engine: StrategyEngine, snapshot: dict, expected: str, label: str) -> None:
    signal = engine.evaluate(snapshot, [])
    if signal.status != expected:
        raise AssertionError(f"{label}: expected {expected}, got {signal.status} reasons={signal.reasons}")


def main() -> int:
    config = StrategyConfig(signal_cooldown_seconds=0)
    engine = StrategyEngine(config)

    assert_status(engine, base_snapshot(normal_candles()[:10]), "SKIPPED_INSUFFICIENT_DATA", "insufficient candles")
    assert_status(engine, base_snapshot(normal_candles(), spread=500), "SKIPPED_SPREAD", "high spread")

    bullish = normal_candles()
    bullish[-2] = candle(18, 2298.0, 2300.0, 2297.0, 2299.0)
    bullish[-1] = candle(19, 2299.5, 2301.5, 2299.0, 2300.5)
    signal = engine.evaluate(base_snapshot(bullish), [])
    if signal.status != "SHADOW_SIGNAL" or signal.direction != "BUY":
        raise AssertionError(f"bullish breakout: got {signal.status} {signal.direction} reasons={signal.reasons}")

    bearish = normal_candles()
    bearish[-2] = candle(18, 2300.0, 2301.0, 2298.0, 2299.0)
    bearish[-1] = candle(19, 2298.5, 2299.0, 2296.0, 2297.5)
    signal = engine.evaluate(base_snapshot(bearish), [])
    if signal.status != "SHADOW_SIGNAL" or signal.direction != "SELL":
        raise AssertionError(f"bearish breakdown: got {signal.status} {signal.direction} reasons={signal.reasons}")

    flat = normal_candles()
    flat[-2] = candle(18, 2298.0, 2300.0, 2297.0, 2299.0)
    flat[-1] = candle(19, 2299.0, 2299.5, 2298.5, 2299.2)
    assert_status(engine, base_snapshot(flat), "NO_SIGNAL", "no signal")

    print("OK: strategy self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
