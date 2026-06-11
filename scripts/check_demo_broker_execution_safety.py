#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aurix_demo_broker_execution import DemoBrokerExecutionGate, DemoBrokerExecutionStore, load_demo_broker_execution_config


def snapshot(**overrides):
    base = {
        "terminal_id": "AURIX-VPS-001",
        "received_at": datetime.now(timezone.utc).isoformat(),
        "account": {
            "server": "Exness-MT5Trial15",
            "name": "mk-demo",
            "currency": "GBP",
            "balance": 100.0,
            "equity": 100.0,
            "is_demo": True,
        },
        "tick": {"symbol": "XAUUSDm", "spread_points": 100.0, "time": datetime.now(timezone.utc).isoformat()},
        "positions": [],
        "orders": [],
    }
    base.update(overrides)
    return base


def signal(**overrides):
    base = {
        "id": "mock-signal-1",
        "strategy_name": "mock_strategy",
        "symbol": "XAUUSDm",
        "status": "SIGNAL",
        "direction": "BUY",
        "confidence": 0.9,
        "stop_loss_reference": 2290.0,
        "take_profit_reference": 2310.0,
    }
    base.update(overrides)
    return base


def assert_blocked(gate, name, snap=None, sig=None):
    result = gate.evaluate(snapshot=snap or snapshot(), signal=sig or signal(), runtime_session_id="test", runtime_health="HEALTHY")
    print(f"{name}: allowed={result['allowed']} reason={result.get('reason')}")
    if result["allowed"]:
        raise AssertionError(f"{name} should be blocked")


def main() -> int:
    base_config = load_demo_broker_execution_config()
    enabled = replace(base_config, broker_execution_enabled=True, execution_mode="BROKER_EXECUTION_ENABLED")
    with tempfile.TemporaryDirectory(prefix="aurix-demo-broker-safety-") as temp_dir:
        store = DemoBrokerExecutionStore(temp_dir)
        gate = DemoBrokerExecutionGate(enabled, store)
        assert_blocked(DemoBrokerExecutionGate(base_config, store), "default_disabled")
        assert_blocked(gate, "non_demo_account", snap=snapshot(account={"server": "Exness-Real", "balance": 100.0, "equity": 100.0}))
        assert_blocked(gate, "non_xauusd_symbol", snap=snapshot(tick={"symbol": "EURUSD", "spread_points": 10.0}))
        assert_blocked(gate, "spread_too_high", snap=snapshot(tick={"symbol": "XAUUSDm", "spread_points": 999.0}))
        assert_blocked(gate, "missing_sl", sig=signal(stop_loss_reference=None))
        assert_blocked(gate, "missing_tp", sig=signal(take_profit_reference=None))
        assert_blocked(gate, "open_position_exists", snap=snapshot(positions=[{"ticket": 1, "symbol": "XAUUSDm"}]))
        no_signal = gate.evaluate(snapshot=snapshot(), signal=None, runtime_session_id="test", runtime_health="HEALTHY")
        if no_signal.get("primary_block") != "no actionable signal":
            raise AssertionError(f"no signal primary block wrong: {no_signal}")
        no_direction = gate.evaluate(snapshot=snapshot(), signal=signal(direction=None), runtime_session_id="test", runtime_health="HEALTHY")
        if no_direction.get("primary_block") != "signal direction missing":
            raise AssertionError(f"missing direction primary block wrong: {no_direction}")
        allowed = gate.evaluate(snapshot=snapshot(), signal=signal(), runtime_session_id="test", runtime_health="HEALTHY")
        print(f"mock_allowed_decision: {allowed['allowed']} action={allowed['action']}")
        if not allowed["allowed"]:
            print("FAIL: mocked all-clear decision was blocked")
            return 1
        if store.list_commands():
            print("FAIL: safety gate created a command during isolated check")
            return 1
    print("OK: demo broker execution safety check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
