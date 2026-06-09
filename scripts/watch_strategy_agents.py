from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from dotenv import load_dotenv


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    base = f"http://{host}:{port}"
    try:
        while True:
            try:
                status = get_json(f"{base}/strategy-agents/status")
                latest = get_json(f"{base}/strategy-agents/latest").get("items") or []
                event_bus = get_json(f"{base}/event-bus/status")
                latest_signal = next((item for item in reversed(latest) if item.get("status") == "SIGNAL"), {})
                agent_statuses = ",".join(f"{item.get('agent_id')}={item.get('status')}" for item in latest)
                print(
                    f"time={time.strftime('%H:%M:%S')} registered={status.get('registered_count')} enabled={status.get('enabled_count')} "
                    f"statuses={agent_statuses or status.get('latest_status_counts')} "
                    f"latest_signal={latest_signal.get('direction')} event_bus_sequence={event_bus.get('last_sequence')} "
                    f"paper_trade_creation_allowed={status.get('paper_trade_creation_allowed')} "
                    f"order_request_creation_allowed={status.get('order_request_creation_allowed')} "
                    f"live_execution_allowed={status.get('live_execution_allowed')} "
                    f"command_queueing_allowed={status.get('command_queueing_allowed')}"
                )
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                print(f"FAIL: {exc}")
            time.sleep(5)
    except KeyboardInterrupt:
        print("stopped")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
