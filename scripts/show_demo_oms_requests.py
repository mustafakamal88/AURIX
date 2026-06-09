from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    url = f"http://{host}:{port}/demo-oms/requests?limit={args.limit}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read Demo OMS requests at {url}: {exc}")
        return 1
    for item in data.get("items") or []:
        print(f"{item.get('created_at')} {item.get('id')} {item.get('intent_id')} {item.get('symbol')} {item.get('direction')} {item.get('status')} mt5={item.get('mt5_command_id')} broker={item.get('broker_order_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
