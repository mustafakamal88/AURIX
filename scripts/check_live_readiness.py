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
    url = f"http://{host}:{port}/live-readiness/status"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read live readiness status at {url}: {exc}")
        return 1
    latest = data.get("latest") or {}
    print("AURIX Live Readiness")
    print(f"enabled: {data.get('enabled')}")
    print(f"symbol: {data.get('symbol')}")
    print(f"mode: {data.get('mode')}")
    print(f"latest_exists: {data.get('latest_exists')}")
    print(f"status: {latest.get('status')}")
    print(f"score: {latest.get('score')}")
    print(f"arming_allowed: {latest.get('live_arming_allowed')}")
    print(f"execution_allowed: {latest.get('live_execution_allowed')}")
    print(f"blocking_reasons: {len(latest.get('blocking_reasons') or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
