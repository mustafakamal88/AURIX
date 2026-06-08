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
    url = f"http://{host}:{port}/market/status"

    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read market status at {url}: {exc}")
        return 1

    quality = data.get("quality") or {}
    print("AURIX Market Data")
    print(f"symbol: {data.get('symbol')}")
    print(f"tick_count: {data.get('tick_count')}")
    print(f"candle_count: {data.get('candle_count')}")
    print(f"spread_points: {quality.get('spread_points')}")
    print(f"quality_ok: {quality.get('ok')}")
    reasons = quality.get("reasons") or []
    print(f"reasons: {', '.join(reasons) if reasons else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
