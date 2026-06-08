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
    url = f"http://{host}:{port}/paper/status"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read paper status at {url}: {exc}")
        return 1
    print("AURIX Paper Trading")
    print(f"enabled: {data.get('enabled')}")
    print(f"symbol: {data.get('symbol')}")
    print(f"open_trades: {data.get('open_trades')}")
    print(f"closed_trades: {data.get('closed_trades')}")
    print(f"bid: {data.get('bid')}")
    print(f"ask: {data.get('ask')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
