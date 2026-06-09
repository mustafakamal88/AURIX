from __future__ import annotations

import json
import os
import urllib.request
from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    url = f"http://{os.getenv('AURIX_HOST', '127.0.0.1')}:{os.getenv('AURIX_PORT', '8765')}/demo-command-queue/status"
    with urllib.request.urlopen(url, timeout=5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    for field in ["enabled", "symbol", "mode", "preview_count", "payload_count", "latest_preview_status", "latest_payload_status", "manual_demo_arm", "demo_command_queueing_allowed", "mt5_command_queueing_allowed", "demo_execution_allowed", "live_execution_allowed", "broker_order_created", "mt5_commands_queued"]:
        print(f"{field}: {data.get(field)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
