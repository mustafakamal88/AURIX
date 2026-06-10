from __future__ import annotations

import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_trade_explanations import TradeExplanationStore, build_trade_explanation


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    trace_sell = build_trade_explanation(
        oms_request={
            "id": "oms-request-1",
            "intent_id": "intent-1",
            "symbol": "XAUUSDm",
            "direction": "SELL",
            "volume": 0.01,
            "entry_reference": 4174.178,
            "stop_loss": 4192.438,
            "take_profit": 4162.438,
            "strategy_name": "xauusd_v2",
        },
        oms_intent={
            "id": "intent-1",
            "strategy_name": "xauusd_v2",
            "direction": "SELL",
            "confidence": 0.82,
            "setup_reason": "trap + reclaim + accept + continuation",
            "decision_trace": {
                "rule_checks": {
                    "trap_detected": True,
                    "reclaim_detected": True,
                    "accept_detected": True,
                    "continuation_detected": True,
                    "execute_triggered": True,
                },
                "value_area_high": 4188.0,
                "value_area_low": 4168.0,
                "poc": 4178.0,
            },
        },
        preview={"id": "preview-1", "direction": "SELL", "symbol": "XAUUSDm"},
        validation={"status": "PASS", "approved": True, "spread_points": 42.0},
        payload={"id": "payload-1", "side": "SELL", "volume": 0.01, "sl": 4192.438, "tp": 4162.438, "mt5_command_id": None, "queued_at": None, "broker_order_id": None},
        snapshot={"received_at": "2026-06-10T09:39:08+00:00", "tick": {"symbol": "XAUUSDm", "spread_points": 42.0}},
        decision={"action": "TRADE_SHORT", "score": 0.91, "generated_at": "2026-06-10T09:39:08+00:00"},
        strategy_diagnostics={"strategy_family": "TRACE"},
    )
    require(trace_sell["strategy_family"] == "TRACE", f"TRACE family missing: {trace_sell}")
    require(trace_sell["action"] == "TRADE_SHORT", f"TRACE sell action missing: {trace_sell}")
    require(trace_sell["reason_summary"] == "trap + reclaim + accept + continuation", f"TRACE reason missing: {trace_sell}")
    require(trace_sell["entry"] == 4174.178 and trace_sell["stop_loss"] == 4192.438 and trace_sell["take_profit"] == 4162.438, f"entry/SL/TP references missing: {trace_sell}")
    require(trace_sell["trace_setup"]["trap_detected"] is True and trace_sell["trace_setup"]["execute_triggered"] is True, f"TRACE setup components missing: {trace_sell}")

    missing = build_trade_explanation(payload={"id": "payload-missing", "mt5_command_id": None, "queued_at": None, "broker_order_id": None})
    for field in ["strategy_name", "reason_summary", "entry", "stop_loss", "take_profit"]:
        require(missing[field] == "unknown", f"missing historical field should be unknown, got {field}={missing[field]}")

    with tempfile.TemporaryDirectory(prefix="aurix-trade-explanations-") as tmpdir:
        store = TradeExplanationStore(tmpdir)
        written = store.write(trace_sell)
        latest = store.latest()
        require(latest["trade_id"] == written["trade_id"], f"latest index wrong: {latest}")
        require(written["safety"]["mt5_commands_queued"] is False, f"explanation should not queue MT5 commands: {written}")
        require(written["safety"]["broker_order_created"] is False, f"explanation should not create broker orders: {written}")

    print("OK: trade explanation self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
