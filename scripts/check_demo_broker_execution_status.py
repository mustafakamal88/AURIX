#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aurix_demo_broker_execution import load_demo_broker_execution_config
from aurix_bridge_server.main import build_demo_broker_execution_status, store


def main() -> int:
    config = load_demo_broker_execution_config()
    status = build_demo_broker_execution_status()
    snapshot = store.latest_snapshot() or {}
    tick = snapshot.get("tick") or {}
    gate = status.get("latest_gate_decision") or {}
    print(f"execution_mode: {config.execution_mode}")
    print(f"broker_execution: {config.broker_execution_enabled}")
    print(f"internal_queue_state: {status.get('queue_state')}")
    print(f"internal_engine_spread_limit: {status.get('engine_max_spread_points')}")
    print(f"current_spread: {tick.get('spread_points')}")
    print(f"spread_gate: {status.get('spread_gate') or gate.get('spread_gate')}")
    print(f"risk_model: {status.get('risk_model')}")
    print(f"calculated_volume: {gate.get('volume')}")
    print(f"selected_strategy: {status.get('selected_strategy')}")
    print(f"selected_signal: {status.get('selected_signal')}")
    print(f"primary_block_reason: {status.get('latest_gate_block') or gate.get('primary_block') or gate.get('reason')}")
    print(f"max_volume: {config.max_volume}")
    print(f"max_spread_points: {config.max_spread_points}")
    if config.max_volume > 0.01:
        print("FAIL: max demo volume exceeds 0.01")
        return 1
    if config.broker_execution_enabled:
        print("WARN: broker execution is enabled by environment/config")
    else:
        print("OK: broker execution is disabled; internal queue will not return broker commands.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
