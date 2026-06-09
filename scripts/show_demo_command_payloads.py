from __future__ import annotations

import argparse
import json
import os
import urllib.request
from dotenv import load_dotenv


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    load_dotenv()
    url = f"http://{os.getenv('AURIX_HOST', '127.0.0.1')}:{os.getenv('AURIX_PORT', '8765')}/demo-command-queue/payloads?limit={args.limit}"
    with urllib.request.urlopen(url, timeout=5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    for item in data.get("items") or []:
        print(f"{item.get('created_at')} {item.get('id')} {item.get('preview_id')} {item.get('symbol')} {item.get('side')} {item.get('status')} mt5={item.get('mt5_command_id')} broker={item.get('broker_order_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
