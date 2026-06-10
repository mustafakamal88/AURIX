#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aurix_demo_broker_execution import load_demo_broker_execution_config


def main() -> int:
    config = load_demo_broker_execution_config()
    print(f"execution_mode: {config.execution_mode}")
    print(f"demo_broker_execution_enabled: {config.demo_broker_execution_enabled}")
    print(f"command_queue_enabled: {config.command_queue_enabled}")
    print(f"live_execution_enabled: {config.live_execution_enabled}")
    print(f"max_volume: {config.max_volume}")
    print(f"max_spread_points: {config.max_spread_points}")
    if config.live_execution_enabled:
        print("FAIL: live execution is enabled")
        return 1
    if config.max_volume > 0.01:
        print("FAIL: max demo volume exceeds 0.01")
        return 1
    if config.demo_broker_execution_enabled or config.command_queue_enabled:
        print("WARN: demo broker execution or command queue is enabled by environment/config")
    else:
        print("OK: default demo broker execution and command queue are disabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
