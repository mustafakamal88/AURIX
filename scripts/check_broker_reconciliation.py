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
    url = f"http://{host}:{port}/broker-reconciliation/status"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read broker reconciliation at {url}: {exc}")
        return 1
    for field in [
        "enabled",
        "symbol",
        "mode",
        "latest_exists",
        "status",
        "broker_position_count",
        "broker_order_count",
        "mismatch_count",
        "warning_count",
        "live_execution_allowed",
        "command_queueing_allowed",
        "broker_order_created",
        "mt5_commands_queued",
    ]:
        print(f"{field}: {data.get(field)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
