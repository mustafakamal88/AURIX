#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aurix_demo_broker_execution import DemoBrokerExecutionStore


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aurix-mt5-result-check-") as temp_dir:
        store = DemoBrokerExecutionStore(temp_dir)
        result = store.append_execution_result(
            {
                "command_id": "mock-command",
                "terminal_id": "AURIX-VPS-001",
                "status": "BLOCKED_BY_EA",
                "symbol": "XAUUSDm",
                "side": "BUY",
                "volume": 0.01,
                "ticket": 0,
                "error_code": -22,
                "error_message": "broker execution disabled in EA",
            }
        )
        latest = store.latest_execution_result()
        print(f"latest_status: {latest.get('status')}")
        print(f"latest_error: {latest.get('error_message')}")
        if result.get("status") != "BLOCKED_BY_EA" or latest.get("status") != "BLOCKED_BY_EA":
            print("FAIL: execution result was not persisted correctly")
            return 1
    print("OK: MT5 execution result check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
