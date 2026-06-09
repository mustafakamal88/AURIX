from __future__ import annotations

import json
import os
import urllib.request
from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    url = f"http://{os.getenv('AURIX_HOST', '127.0.0.1')}:{os.getenv('AURIX_PORT', '8765')}/decision-engine/status"
    with urllib.request.urlopen(url, timeout=5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    for field in ["enabled", "symbol", "mode", "autonomy_level", "latest_exists", "latest_action", "latest_direction", "latest_status", "confidence", "score", "strategy", "blocking_reason_count", "warning_count", "demo_execution_allowed", "live_execution_allowed", "command_queueing_allowed", "mt5_commands_queued", "broker_order_created"]:
        print(f"{field}: {data.get(field)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
