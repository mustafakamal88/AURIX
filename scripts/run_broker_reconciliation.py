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
    url = f"http://{host}:{port}/broker-reconciliation/run"
    req = urllib.request.Request(url, data=b"{}", method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not run broker reconciliation at {url}: {exc}")
        return 1
    account = data.get("account") or {}
    print(f"status: {data.get('status')}")
    print(f"account currency: {account.get('currency')}")
    print(f"balance/equity: {account.get('balance')}/{account.get('equity')}")
    print(f"broker positions count: {len(data.get('broker_positions') or [])}")
    print(f"broker orders count: {len(data.get('broker_orders') or [])}")
    print(f"mismatches: {data.get('mismatches')}")
    print(f"warnings: {data.get('warnings')}")
    print(f"recommendations: {data.get('recommendations')}")
    print(f"event_id: {data.get('event_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
