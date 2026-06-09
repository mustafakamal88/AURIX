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
    url = f"http://{host}:{port}/strategy-agents/status"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read strategy agents at {url}: {exc}")
        return 1
    print(f"enabled: {data.get('enabled')}")
    print(f"symbol: {data.get('symbol')}")
    print(f"mode: {data.get('mode')}")
    print(f"registered_count: {data.get('registered_count')}")
    print(f"enabled_count: {data.get('enabled_count')}")
    print(f"latest_exists: {data.get('latest_exists')}")
    print(f"latest_status_counts: {data.get('latest_status_counts')}")
    print(f"last_evaluation_at: {data.get('last_evaluation_at')}")
    print(f"event_bus_publish_enabled: {data.get('event_bus_publish_enabled')}")
    print(f"paper_trade_creation_allowed: {data.get('paper_trade_creation_allowed')}")
    print(f"order_request_creation_allowed: {data.get('order_request_creation_allowed')}")
    print(f"live_execution_allowed: {data.get('live_execution_allowed')}")
    print(f"command_queueing_allowed: {data.get('command_queueing_allowed')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
