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
    url = f"http://{host}:{port}/paper-risk-audit/status"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read paper risk audit at {url}: {exc}")
        return 1
    latest = data.get("latest") or {}
    print("AURIX Paper Risk Audit")
    print(f"enabled: {data.get('enabled')}")
    print(f"symbol: {data.get('symbol')}")
    print(f"mode: {data.get('mode')}")
    print(f"latest_exists: {data.get('latest_exists')}")
    print(f"decision_count: {data.get('decision_count')}")
    print(f"latest_decision_id: {latest.get('id')}")
    print(f"latest_signal_id: {latest.get('signal_id')}")
    print(f"latest_trade_id: {latest.get('trade_id')}")
    print(f"latest_risk_status: {latest.get('risk_status')}")
    print(f"history_exists: {data.get('history_exists')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
