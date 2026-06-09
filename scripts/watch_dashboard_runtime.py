from __future__ import annotations

import json
import os
import signal
import sys
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv()
BASE_URL = os.getenv("AURIX_BASE_URL") or f"http://{os.getenv('AURIX_HOST', '127.0.0.1')}:{os.getenv('AURIX_PORT', '8765')}"
POLL_SECONDS = 5
running = True


def stop(_signum, _frame) -> None:
    global running
    running = False


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
    signal.signal(signal.SIGINT, stop)
    print("time health decision score spread fast_rsi_status broker_status demo_oms_status command_queue_status top_block")
    while running:
        try:
            summary = get_summary()
            row = [
                datetime.now().strftime("%H:%M:%S"),
                str(summary.get("health") or "--"),
                str(value(summary, "decision", "action") or "--"),
                str(value(summary, "decision", "score") or "--"),
                str(value(summary, "market", "spread_points") or "--"),
                str(value(summary, "fast_rsi", "status") or "--"),
                str(value(summary, "broker_reconciliation", "status") or "--"),
                str(value(summary, "demo_oms", "latest_request_status") or "--"),
                str(value(summary, "demo_command_queue", "latest_payload_status") or "--"),
                str((summary.get("top_blocks") or ["--"])[0]),
            ]
            print(" | ".join(row), flush=True)
        except (HTTPError, URLError, TimeoutError) as exc:
            print(f"{datetime.now().strftime('%H:%M:%S')} | ERROR | {exc}", flush=True)
        for _ in range(POLL_SECONDS):
            if not running:
                break
            time.sleep(1)
    print("Stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
