from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_paper_trading.config import PaperTradingConfig
from aurix_paper_trading.engine import PaperTradingEngine
from aurix_risk_governor.config import RiskConfig
from aurix_strategy_engine.models import StrategySignal


def snapshot(bid: float, ask: float) -> dict:
    return {
        "terminal_id": "AURIX-MAC-001",
        "received_at": "2026-06-08T20:00:00+00:00",
        "tick": {"symbol": "XAUUSDm", "bid": bid, "ask": ask, "spread_points": 20, "point": 0.01},
        "account": {"balance": 1000, "equity": 1000},
        "positions": [],
    }


def signal(status: str, direction: str | None = None) -> StrategySignal:
    return StrategySignal(
        strategy_name="xauusd_shadow_v1",
        strategy_version="0.1.0",
        mode="SHADOW",
        symbol="XAUUSDm",
        direction=direction,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        confidence=0.62,
        entry_reference=100.2,
        reasons=["test"],
    )


def make_engine() -> PaperTradingEngine:
    return PaperTradingEngine(
        PaperTradingConfig(default_stop_points=100, default_take_profit_points=200, max_open_paper_trades=1),
        RiskConfig(max_spread_points=350, max_open_positions=99, max_trades_per_day=99),
    )


def create_trade(engine: PaperTradingEngine, direction: str):
    trade, result = engine.create_from_signal(signal("SHADOW_SIGNAL", direction), snapshot(100.0, 100.2), [], [])
    if trade is None:
        raise AssertionError(f"expected trade for {direction}, got {result}")
    return trade


def main() -> int:
    engine = make_engine()

    trade, result = engine.create_from_signal(signal("NO_SIGNAL"), snapshot(100.0, 100.2), [], [])
    if trade is not None or result.get("created"):
        raise AssertionError("NO_SIGNAL should not create a paper trade")

    buy_tp = create_trade(engine, "BUY").model_dump()
    trades, updated = engine.update_open_trades(snapshot(102.2, 102.4), [buy_tp])
    if trades[0]["status"] != "CLOSED_TP" or not updated:
        raise AssertionError(f"BUY TP expected, got {trades}")

    buy_sl = create_trade(engine, "BUY").model_dump()
    trades, updated = engine.update_open_trades(snapshot(99.2, 99.4), [buy_sl])
    if trades[0]["status"] != "CLOSED_SL" or not updated:
        raise AssertionError(f"BUY SL expected, got {trades}")

    sell_tp = create_trade(engine, "SELL").model_dump()
    trades, updated = engine.update_open_trades(snapshot(97.8, 98.0), [sell_tp])
    if trades[0]["status"] != "CLOSED_TP" or not updated:
        raise AssertionError(f"SELL TP expected, got {trades}")

    sell_sl = create_trade(engine, "SELL").model_dump()
    trades, updated = engine.update_open_trades(snapshot(101.0, 101.2), [sell_sl])
    if trades[0]["status"] != "CLOSED_SL" or not updated:
        raise AssertionError(f"SELL SL expected, got {trades}")

    existing = create_trade(engine, "BUY").model_dump()
    trade, result = engine.create_from_signal(signal("SHADOW_SIGNAL", "SELL"), snapshot(100.0, 100.2), [existing], [])
    if trade is not None or result.get("reason") != "max open paper trades reached":
        raise AssertionError(f"max open paper trades should block, got trade={trade} result={result}")

    print("OK: paper trading self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
