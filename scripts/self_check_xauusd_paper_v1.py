from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_strategy_engine.xauusd_paper_v1 import XauusdPaperV1Config, evaluate_xauusd_paper_v1


def candle(i: int, open_: float, high: float, low: float, close: float) -> dict:
    return {"time": i, "open": open_, "high": high, "low": low, "close": close}


def base_candles() -> list[dict]:
    return [candle(i, 100.0, 101.0, 99.0, 100.2) for i in range(20)]


def snapshot(spread: float = 100) -> dict:
    return {
        "terminal_id": "AURIX-MAC-001",
        "received_at": "2026-06-08T14:00:00+01:00",
        "tick": {"symbol": "XAUUSDm", "bid": 100.0, "ask": 100.2, "spread_points": spread, "point": 0.01},
        "candles": base_candles(),
    }


def context(session: str = "LONDON", regime: str = "RANGE", bias: str = "NEUTRAL") -> dict:
    return {"session_name": session, "regime": regime, "directional_bias": bias}


def evaluate(candles: list[dict], ctx: dict, spread: float = 100):
    config = XauusdPaperV1Config(signal_cooldown_seconds=0)
    snap = snapshot(spread)
    snap["candles"] = candles
    return evaluate_xauusd_paper_v1(snap, ctx, candles, [], config)


def main() -> int:
    signal = evaluate(base_candles(), context("CLOSED"))
    if signal.status != "NO_SIGNAL" or "session is CLOSED" not in signal.reasons:
        raise AssertionError(f"blocked closed session failed: {signal}")

    signal = evaluate(base_candles(), context(regime="HIGH_SPREAD"), spread=500)
    if signal.status != "SKIPPED_SPREAD":
        raise AssertionError(f"blocked high spread failed: {signal}")

    signal = evaluate(base_candles()[:10], context())
    if signal.status != "SKIPPED_INSUFFICIENT_DATA":
        raise AssertionError(f"insufficient candles failed: {signal}")

    buy = base_candles()
    buy[-2] = candle(18, 100.2, 100.7, 98.5, 99.4)
    buy[-1] = candle(19, 99.3, 100.5, 99.2, 99.8)
    signal = evaluate(buy, context())
    if signal.status != "SHADOW_SIGNAL" or signal.direction != "BUY":
        raise AssertionError(f"buy sweep reclaim failed: {signal}")

    sell = base_candles()
    sell[-2] = candle(18, 99.8, 101.5, 99.5, 100.6)
    sell[-1] = candle(19, 100.7, 100.8, 99.6, 100.2)
    signal = evaluate(sell, context())
    if signal.status != "SHADOW_SIGNAL" or signal.direction != "SELL":
        raise AssertionError(f"sell sweep reclaim failed: {signal}")

    signal = evaluate(base_candles(), context())
    if signal.status != "NO_SIGNAL":
        raise AssertionError(f"no signal failed: {signal}")

    print("OK: XAUUSD Paper V1 self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
