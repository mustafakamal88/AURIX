from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    url = f"http://{host}:{port}/demo-oms/status"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read Demo OMS at {url}: {exc}")
        return 1
    fields = [
        "enabled",
        "symbol",
        "mode",
        "order_intent_count",
        "order_request_count",
        "latest_intent_status",
        "latest_request_status",
        "demo_execution_allowed",
        "live_execution_allowed",
        "broker_order_created",
        "mt5_commands_queued",
    ]
    for field in fields:
        print(f"{field}: {data.get(field)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
