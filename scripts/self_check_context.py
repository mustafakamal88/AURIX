from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_context_engine.config import ContextConfig
from aurix_context_engine.regime import classify_regime
from aurix_context_engine.session import classify_session


def candle(i: int, open_: float, high: float, low: float, close: float) -> dict:
    return {"time": i, "open": open_, "high": high, "low": low, "close": close}


def range_candles() -> list[dict]:
    candles = []
    for i in range(20):
        candles.append(candle(i, 100.0, 101.0, 99.0, 100.8))
    return candles


def assert_regime(candles: list[dict], expected: str, label: str, spread: float = 100, quality: bool = True) -> None:
    config = ContextConfig()
    result = classify_regime(candles, spread, quality, config)
    if result["regime"] != expected:
        raise AssertionError(f"{label}: expected {expected}, got {result}")


def main() -> int:
    config = ContextConfig()
    session_tests = [
        ("2026-06-08T01:00:00+01:00", "ASIA"),
        ("2026-06-08T08:00:00+01:00", "LONDON"),
        ("2026-06-08T13:00:00+01:00", "NY_PRE_MARKET"),
        ("2026-06-08T15:00:00+01:00", "NY_OPEN"),
        ("2026-06-08T18:00:00+01:00", "NY_LATE"),
        ("2026-06-08T22:00:00+01:00", "CLOSED"),
    ]
    for timestamp, expected in session_tests:
        actual, _, _ = classify_session(timestamp, config)
        if actual != expected:
            raise AssertionError(f"session {timestamp}: expected {expected}, got {actual}")

    assert_regime(range_candles()[:5], "INSUFFICIENT_DATA", "insufficient data")
    assert_regime(range_candles(), "HIGH_SPREAD", "high spread", spread=500)

    bullish = range_candles()
    bullish[-1] = candle(19, 100.0, 103.0, 99.5, 102.0)
    assert_regime(bullish, "BULLISH_BREAKOUT", "bullish breakout")

    bearish = range_candles()
    bearish[-1] = candle(19, 100.0, 100.5, 97.0, 98.0)
    assert_regime(bearish, "BEARISH_BREAKDOWN", "bearish breakdown")

    assert_regime(range_candles(), "RANGE", "range")

    volatile = []
    for i in range(19):
        volatile.append(candle(i, 100.0, 101.0, 99.0, 100.3))
    volatile.append(candle(19, 100.0, 102.8, 97.2, 100.5))
    assert_regime(volatile, "VOLATILITY_EXPANSION", "volatility expansion")

    chop = []
    for i in range(20):
        chop.append(candle(i, 100.0, 101.0, 99.0, 100.05))
    assert_regime(chop, "CHOP", "chop")

    print("OK: context self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
