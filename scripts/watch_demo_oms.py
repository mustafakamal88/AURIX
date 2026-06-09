from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    url = f"http://{host}:{port}/demo-oms/status"
    while True:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            print(
                f"time={datetime.now().isoformat(timespec='seconds')} "
                f"mode={data.get('mode')} "
                f"intent_count={data.get('order_intent_count')} "
                f"request_count={data.get('order_request_count')} "
                f"latest_intent_status={data.get('latest_intent_status')} "
                f"latest_request_status={data.get('latest_request_status')} "
                f"demo_execution_allowed={data.get('demo_execution_allowed')} "
                f"live_execution_allowed={data.get('live_execution_allowed')} "
                f"command_queueing_allowed={data.get('command_queueing_allowed')} "
                f"broker_order_created={data.get('broker_order_created')} "
                f"mt5_commands_queued={data.get('mt5_commands_queued')}"
            )
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"time={datetime.now().isoformat(timespec='seconds')} error={exc}")
        time.sleep(5)


if __name__ == "__main__":
    raise SystemExit(main())
