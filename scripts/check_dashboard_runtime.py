from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv()
BASE_URL = os.getenv("AURIX_BASE_URL") or f"http://{os.getenv('AURIX_HOST', '127.0.0.1')}:{os.getenv('AURIX_PORT', '8765')}"


def get_summary() -> dict:
    request = Request(f"{BASE_URL}/dashboard/runtime-summary", method="GET")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def value(data: dict, *path: str):
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def main() -> int:
    try:
        summary = get_summary()
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"ERROR: cannot load runtime summary from {BASE_URL}: {exc}", file=sys.stderr)
        return 1

    lines = {
        "symbol": summary.get("symbol"),
        "health": summary.get("health"),
        "decision_action": value(summary, "decision", "action"),
        "decision_score": value(summary, "decision", "score"),
        "spread_points": value(summary, "market", "spread_points"),
        "spread_status": value(summary, "market", "spread_status"),
        "fast_rsi_status": value(summary, "fast_rsi", "status"),
        "broker_reconciliation_status": value(summary, "broker_reconciliation", "status"),
        "demo_oms_latest_request_status": value(summary, "demo_oms", "latest_request_status"),
        "demo_command_queue_latest_payload_status": value(summary, "demo_command_queue", "latest_payload_status"),
        "live_execution_allowed": value(summary, "safety", "live_execution_allowed"),
        "command_queueing_allowed": bool(value(summary, "safety", "demo_command_queueing_allowed") or value(summary, "safety", "mt5_command_queueing_allowed")),
        "top_block": (summary.get("top_blocks") or [None])[0],
        "top_warning": (summary.get("top_warnings") or [None])[0],
    }
    for key, item in lines.items():
        print(f"{key}: {item if item is not None else '--'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
