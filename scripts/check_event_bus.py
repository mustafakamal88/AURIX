from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv


def read_json(path: str) -> dict:
    with urllib.request.urlopen(path, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    url = f"http://{host}:{port}/event-bus/status"
    try:
        data = read_json(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read event bus at {url}: {exc}")
        return 1
    safety = data.get("safety") or {}
    print(f"enabled: {data.get('enabled')}")
    print(f"symbol: {data.get('symbol')}")
    print(f"mode: {data.get('mode')}")
    print(f"latest_exists: {data.get('latest_exists')}")
    print(f"event_count: {data.get('event_count')}")
    print(f"last_sequence: {data.get('last_sequence')}")
    print(f"last_event_type: {data.get('last_event_type')}")
    print(f"state_exists: {data.get('state_exists')}")
    print(f"live_execution_allowed: {safety.get('live_execution_allowed')}")
    print(f"command_queueing_allowed: {safety.get('command_queueing_allowed')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
