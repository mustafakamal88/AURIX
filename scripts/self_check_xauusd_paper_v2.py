from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aurix_strategy_engine.xauusd_paper_v2 import XauusdPaperV2Config, evaluate_xauusd_paper_v2


def candles_for_buy(count: int = 30) -> list[dict]:
    candles = [{"time": i, "open": 2400.0, "high": 2401.0, "low": 2399.0, "close": 2400.2, "point": 0.01, "spread_points": 100} for i in range(count - 2)]
    candles.append({"time": count - 2, "open": 2400.0, "high": 2400.6, "low": 2398.5, "close": 2399.4, "point": 0.01, "spread_points": 100})
    candles.append({"time": count - 1, "open": 2399.2, "high": 2402.2, "low": 2399.0, "close": 2401.6, "point": 0.01, "spread_points": 100})
    return candles


def candles_for_sell(count: int = 30) -> list[dict]:
    candles = [{"time": i, "open": 2400.0, "high": 2401.0, "low": 2399.0, "close": 2399.8, "point": 0.01, "spread_points": 100} for i in range(count - 2)]
    candles.append({"time": count - 2, "open": 2400.0, "high": 2402.0, "low": 2399.4, "close": 2400.8, "point": 0.01, "spread_points": 100})
    candles.append({"time": count - 1, "open": 2400.9, "high": 2401.0, "low": 2397.8, "close": 2398.4, "point": 0.01, "spread_points": 100})
    return candles


def snapshot(candles: list[dict], spread: float = 100) -> dict:
    return {
        "received_at": datetime.now(timezone.utc).isoformat(),
        "terminal_id": "TEST",
        "tick": {"symbol": "XAUUSDm", "bid": 2400.0, "ask": 2400.1, "point": 0.01, "spread_points": spread},
        "candles": candles,
    }


def context(session: str = "LONDON", regime: str = "RANGE") -> dict:
    return {"session_name": session, "session_open": session != "CLOSED", "regime": regime, "directional_bias": "NEUTRAL"}


def quality(ok: bool = True) -> dict:
    return {"ok": ok, "reasons": [] if ok else ["market quality not ok"]}


def assert_status(name: str, signal, status: str) -> None:
    assert signal.status == status, f"{name}: expected {status}, got {signal.status} {signal.reasons}"
    assert signal.command_id is None, f"{name}: command_id must remain null"


def main() -> int:
    config = XauusdPaperV2Config()
    buy_candles = candles_for_buy()
    sell_candles = candles_for_sell()

    assert_status("missing snapshot", evaluate_xauusd_paper_v2(None, context(), buy_candles, quality(), [], config), "ERROR")
    assert_status("closed session", evaluate_xauusd_paper_v2(snapshot(buy_candles), context("CLOSED"), buy_candles, quality(), [], config), "SKIPPED_SESSION")
    assert_status("market quality", evaluate_xauusd_paper_v2(snapshot(buy_candles), context(), buy_candles, quality(False), [], config), "SKIPPED_MARKET_QUALITY")
    assert_status("high spread", evaluate_xauusd_paper_v2(snapshot(buy_candles, 300), context(), buy_candles, quality(), [], config), "SKIPPED_SPREAD")
    assert_status("insufficient candles", evaluate_xauusd_paper_v2(snapshot(buy_candles[:10]), context(), buy_candles[:10], quality(), [], config), "SKIPPED_INSUFFICIENT_DATA")
    assert_status("chop", evaluate_xauusd_paper_v2(snapshot(buy_candles), context(regime="CHOP"), buy_candles, quality(), [], config), "SKIPPED_CHOP")

    buy_signal = evaluate_xauusd_paper_v2(snapshot(buy_candles), context(), buy_candles, quality(), [], config)
    assert_status("buy", buy_signal, "PAPER_SIGNAL")
    assert buy_signal.direction == "BUY"

    sell_signal = evaluate_xauusd_paper_v2(snapshot(sell_candles), context(), sell_candles, quality(), [], config)
    assert_status("sell", sell_signal, "PAPER_SIGNAL")
    assert sell_signal.direction == "SELL"

    previous = [buy_signal.model_dump()]
    assert_status("cooldown", evaluate_xauusd_paper_v2(snapshot(buy_candles), context(), buy_candles, quality(), previous, config), "SKIPPED_COOLDOWN")

    old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    old_signal = buy_signal.model_dump()
    old_signal["created_at"] = old_time
    old_signal_2 = sell_signal.model_dump()
    old_signal_2["created_at"] = old_time
    assert_status("max signals", evaluate_xauusd_paper_v2(snapshot(buy_candles), context(), buy_candles, quality(), [old_signal, old_signal_2], config), "SKIPPED_MAX_SIGNALS")

    assert all(item.get("command_id") is None for item in [buy_signal.model_dump(), sell_signal.model_dump()])
    print("OK: XAUUSD Paper V2 self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
