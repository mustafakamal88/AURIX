from __future__ import annotations

import json
import os
import urllib.request
from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    url = f"http://{os.getenv('AURIX_HOST', '127.0.0.1')}:{os.getenv('AURIX_PORT', '8765')}/demo-command-queue/dry-run-latest"
    req = urllib.request.Request(url, data=b"{}", method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    preview = data.get("preview") or {}
    payload = data.get("payload") or {}
    validation = data.get("validation") or {}
    print(f"status: {data.get('status')}")
    print(f"preview_id: {preview.get('id')}")
    print(f"payload_id: {payload.get('id')}")
    print(f"command_type: {payload.get('command_type')}")
    print(f"symbol: {payload.get('symbol')}")
    print(f"side: {payload.get('side')}")
    print(f"volume: {payload.get('volume')}")
    print(f"sl: {payload.get('sl')}")
    print(f"tp: {payload.get('tp')}")
    print(f"payload_status: {payload.get('status')}")
    print(f"mt5_command_id: {payload.get('mt5_command_id')}")
    print(f"broker_order_id: {payload.get('broker_order_id')}")
    print(f"rejection_reasons: {validation.get('rejection_reasons')}")
    print(f"warnings: {validation.get('warnings')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
