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
    url = f"http://{host}:{port}/demo-oms/process-latest-signal"
    req = urllib.request.Request(url, data=b"{}", method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not process latest signal at {url}: {exc}")
        return 1
    intent = data.get("intent") or {}
    request = data.get("request") or {}
    validation = data.get("validation") or {}
    print(f"status: {data.get('status')}")
    print(f"intent_id: {intent.get('id')}")
    print(f"request_id: {request.get('id')}")
    print(f"strategy: {intent.get('strategy_name')}")
    print(f"direction: {intent.get('direction')}")
    print(f"volume: {intent.get('volume')}")
    print(f"validation_status: {validation.get('status')}")
    print(f"rejection_reasons: {validation.get('rejection_reasons')}")
    print(f"request_status: {request.get('status')}")
    print(f"mt5_command_id: {request.get('mt5_command_id')}")
    print(f"broker_order_id: {request.get('broker_order_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
