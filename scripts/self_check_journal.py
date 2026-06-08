from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_journal import JournalConfig, JournalReviewer


def trade(trade_id: str, status: str, r: float, signal_id: str = "s1") -> dict:
    return {
        "id": trade_id,
        "signal_id": signal_id,
        "strategy_name": "xauusd_paper_v1",
        "strategy_version": "1.0",
        "symbol": "XAUUSDm",
        "direction": "BUY",
        "status": status,
        "entry_price": 2300.0,
        "stop_loss": 2299.0,
        "take_profit": 2302.0,
        "close_price": 2302.0 if r > 0 else 2299.0,
        "pnl_points": r * 100.0,
        "r_multiple": r,
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "closed_at": datetime.now(timezone.utc).isoformat(),
    }


def signal(signal_id: str, status: str, reasons: list[str]) -> dict:
    return {
        "id": signal_id,
        "strategy_name": "xauusd_paper_v1",
        "strategy_version": "1.0",
        "mode": "PAPER",
        "symbol": "XAUUSDm",
        "status": status,
        "confidence": 0.7,
        "reasons": reasons,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "context_session": "LONDON",
        "context_regime": "RANGE",
        "context_bias": "NEUTRAL",
        "stop_loss_reference": 2299.0,
        "take_profit_reference": 2302.0,
    }


def assert_classification(entries, expected: str, label: str) -> None:
    if not entries or entries[0].classification != expected:
        got = entries[0].classification if entries else None
        raise AssertionError(f"{label}: expected {expected}, got {got}")


def main() -> int:
    reviewer = JournalReviewer(JournalConfig())

    if reviewer.review_paper_trades([], [], [], {}) != []:
        raise AssertionError("no trades should produce no paper entries")
    if reviewer.review_signals([], [], [], {}) != []:
        raise AssertionError("no signals should produce no signal entries")

    assert_classification(
        reviewer.review_paper_trades([trade("t1", "CLOSED_TP", 2.0)], [], [], {"ok": True}),
        "VALID_WIN",
        "closed TP",
    )
    assert_classification(
        reviewer.review_paper_trades([trade("t2", "CLOSED_SL", -1.0)], [], [], {"ok": True}),
        "VALID_LOSS",
        "closed SL",
    )
    assert_classification(
        reviewer.review_signals([signal("s1", "NO_SIGNAL", ["session is CLOSED"])], [], [], {"ok": True}),
        "SESSION_BLOCKED",
        "closed session signal",
    )
    assert_classification(
        reviewer.review_signals([signal("s2", "SKIPPED_SPREAD", ["spread 500 exceeds max_spread_points 350"])], [], [], {"ok": False, "spread_ok": False}),
        "HIGH_SPREAD_BLOCKED",
        "high spread signal",
    )

    summary = reviewer.daily_summary(
        [trade("t3", "CLOSED_TP", 1.0)],
        [signal("s3", "SHADOW_SIGNAL", ["bullish setup"])],
        {"warnings": []},
        {"ok": True},
    )
    if summary.entry_type != "DAILY_SUMMARY" or not any("total_signals=" in note for note in summary.notes):
        raise AssertionError(f"daily summary not generated correctly: {summary}")

    print("OK: journal self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
