from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


load_dotenv()
BASE_URL = os.getenv("AURIX_BASE_URL") or f"http://{os.getenv('AURIX_HOST', '127.0.0.1')}:{os.getenv('AURIX_PORT', '8765')}"


def get_json(path: str) -> dict:
    request = Request(f"{BASE_URL}{path}", method="GET")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    try:
        summary = get_json("/dashboard/runtime-summary")
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot load runtime provenance from {BASE_URL}: {exc}", file=sys.stderr)
        return 1

    provenance = summary.get("runtime_provenance") or {}
    assertion = provenance.get("safety_assertion") or {}
    lifetime = provenance.get("lifetime_counters") or {}
    session = provenance.get("session_counters") or {}
    required = ["runtime_session_id", "process_id", "started_at", "generated_at", "uptime_seconds", "mode", "symbol"]
    missing = [field for field in required if provenance.get(field) in {None, ""}]
    unsafe = [key for key in ["created_paper_trade", "created_order_request", "queued_mt5_command", "created_demo_oms_request", "created_broker_order", "modified_broker_order", "closed_broker_order"] if assertion.get(key)]

    print(f"runtime_session_id: {provenance.get('runtime_session_id')}")
    print(f"process_id: {provenance.get('process_id')}")
    print(f"started_at: {provenance.get('started_at')}")
    print(f"uptime_seconds: {provenance.get('uptime_seconds')}")
    print(f"lifetime_counters: {lifetime}")
    print(f"session_counters: {session}")
    print(f"safety_assertion: {assertion}")

    if missing:
        print(f"ERROR: missing provenance fields: {missing}", file=sys.stderr)
        return 1
    if unsafe or assertion.get("overall_safe") is not True:
        print(f"ERROR: current session is not safe: {unsafe}", file=sys.stderr)
        return 1
    print("OK: runtime provenance check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
