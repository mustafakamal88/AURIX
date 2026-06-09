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
    url = f"http://{host}:{port}/broker-reconciliation/status"
    try:
        while True:
            try:
                with urllib.request.urlopen(url, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                print(
                    f"time={datetime.now().isoformat(timespec='seconds')} "
                    f"status={data.get('status')} "
                    f"positions={data.get('broker_position_count')} "
                    f"orders={data.get('broker_order_count')} "
                    f"mismatches={data.get('mismatch_count')} "
                    f"warnings={data.get('warning_count')} "
                    f"live_execution_allowed={data.get('live_execution_allowed')} "
                    f"command_queueing_allowed={data.get('command_queueing_allowed')}"
                )
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                print(f"time={datetime.now().isoformat(timespec='seconds')} error={exc}")
            time.sleep(5)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
