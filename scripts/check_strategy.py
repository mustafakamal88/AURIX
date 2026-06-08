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
    url = f"http://{host}:{port}/strategy/status"

    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read strategy status at {url}: {exc}")
        return 1

    print("AURIX Shadow Strategy")
    print(f"enabled: {data.get('enabled')}")
    print(f"mode: {data.get('mode')}")
    print(f"strategy: {data.get('strategy_name')} {data.get('strategy_version')}")
    print(f"symbol: {data.get('symbol')}")
    print(f"snapshot_symbol: {data.get('snapshot_symbol')}")
    print(f"candles: {data.get('candles')}")
    print(f"spread_points: {data.get('spread_points')}")
    print(f"signals_count: {data.get('signals_count')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
