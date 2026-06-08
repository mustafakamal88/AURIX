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
    url = f"http://{host}:{port}/risk/status"

    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read Risk Governor status at {url}: {exc}")
        return 1

    snapshot = data.get("latest_snapshot", {})
    print("AURIX Risk Governor")
    print(f"enabled: {data.get('enabled')}")
    print(f"can_trade: {data.get('can_trade')}")
    print(f"symbol: {snapshot.get('symbol')}")
    print(f"equity: {snapshot.get('equity')}")
    print(f"balance: {snapshot.get('balance')}")
    print(f"spread_points: {data.get('spread_points')}")
    print(f"open_positions: {data.get('open_positions')}")

    reasons = data.get("reasons") or []
    if reasons:
        print("reasons:")
        for reason in reasons:
            print(f"- {reason}")
    else:
        print("reasons: none")

    return 0 if data.get("enabled") else 1


if __name__ == "__main__":
    raise SystemExit(main())
