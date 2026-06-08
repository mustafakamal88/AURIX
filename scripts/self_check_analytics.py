from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_analytics.performance import generate_paper_performance_report


def trade(
    trade_id: str,
    direction: str,
    status: str,
    r_multiple: float,
    pnl_points: float,
    signal_id: str,
    closed_at: str,
) -> dict:
    return {
        "id": trade_id,
        "signal_id": signal_id,
        "strategy_name": "xauusd_paper_v1",
        "strategy_version": "1.0",
        "symbol": "XAUUSDm",
        "direction": direction,
        "status": status,
        "entry_price": 2300.0,
        "stop_loss": 2299.0,
        "take_profit": 2302.0,
        "volume": 0.01,
        "opened_at": "2026-01-01T00:00:00+00:00",
        "closed_at": closed_at,
        "close_price": 2302.0,
        "pnl_points": pnl_points,
        "r_multiple": r_multiple,
    }


def signal(signal_id: str, session: str, regime: str) -> dict:
    return {
        "id": signal_id,
        "context_session": session,
        "context_regime": regime,
    }


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected}, got {actual}")


def main() -> int:
    empty = generate_paper_performance_report([], [], [], {})
    assert_equal(empty.total_trades, 0, "empty total trades")
    assert_equal(empty.closed_trades, 0, "empty closed trades")
    if "no closed paper trades yet" not in empty.warnings:
        raise AssertionError(f"empty warnings missing no closed trades: {empty.warnings}")

    one_win = generate_paper_performance_report(
        [trade("t1", "BUY", "CLOSED_TP", 2.0, 200.0, "s1", "2026-01-01T01:00:00+00:00")],
        [signal("s1", "LONDON", "RANGE")],
        [],
        {"ok": True},
    )
    assert_equal(one_win.closed_trades, 1, "one win closed trades")
    assert_equal(one_win.wins, 1, "one win wins")
    assert_equal(one_win.win_rate, 1.0, "one win win rate")
    assert_equal(one_win.total_r, 2.0, "one win total r")
    assert_equal(one_win.profit_factor, float("inf"), "one win profit factor")

    one_loss = generate_paper_performance_report(
        [trade("t1", "SELL", "CLOSED_SL", -1.0, -100.0, "s1", "2026-01-01T01:00:00+00:00")],
        [signal("s1", "NY_OPEN", "BEARISH_BREAKDOWN")],
        [],
        {"ok": True},
    )
    assert_equal(one_loss.losses, 1, "one loss losses")
    assert_equal(one_loss.max_consecutive_losses, 1, "one loss streak")
    assert_equal(one_loss.profit_factor, 0.0, "one loss profit factor")

    mixed_trades = [
        trade("t1", "BUY", "CLOSED_TP", 2.0, 200.0, "s1", "2026-01-01T01:00:00+00:00"),
        trade("t2", "SELL", "CLOSED_SL", -1.0, -100.0, "s2", "2026-01-01T02:00:00+00:00"),
        trade("t3", "SELL", "CLOSED_SL", -1.0, -100.0, "s3", "2026-01-01T03:00:00+00:00"),
        trade("t4", "BUY", "CLOSED_TP", 1.5, 150.0, "s4", "2026-01-01T04:00:00+00:00"),
        {**trade("t5", "BUY", "OPEN", 0.0, 0.0, "s5", "2026-01-01T05:00:00+00:00"), "status": "OPEN", "closed_at": None},
    ]
    mixed_signals = [
        signal("s1", "LONDON", "RANGE"),
        signal("s2", "LONDON", "RANGE"),
        signal("s3", "NY_OPEN", "BEARISH_BREAKDOWN"),
        signal("s4", "NY_OPEN", "RANGE"),
        signal("s5", "ASIA", "CHOP"),
    ]
    mixed = generate_paper_performance_report(mixed_trades, mixed_signals, [], {"ok": True})
    assert_equal(mixed.total_trades, 5, "mixed total trades")
    assert_equal(mixed.open_trades, 1, "mixed open trades")
    assert_equal(mixed.closed_trades, 4, "mixed closed trades")
    assert_equal(mixed.wins, 2, "mixed wins")
    assert_equal(mixed.losses, 2, "mixed losses")
    assert_equal(mixed.win_rate, 0.5, "mixed win rate")
    assert_equal(mixed.total_r, 1.5, "mixed total r")
    assert_equal(mixed.expectancy_r, 0.375, "mixed expectancy")
    assert_equal(mixed.max_consecutive_losses, 2, "mixed max consecutive losses")
    assert_equal(mixed.profit_factor, 1.75, "mixed profit factor")
    assert_equal(mixed.by_direction["BUY"]["trades"], 2, "group by direction BUY")
    assert_equal(mixed.by_direction["SELL"]["trades"], 2, "group by direction SELL")
    assert_equal(mixed.by_session["LONDON"]["trades"], 2, "group by session")
    assert_equal(mixed.by_regime["RANGE"]["trades"], 3, "group by regime")

    print("OK: analytics self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
