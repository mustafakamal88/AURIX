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
                status = get_json(f"{base}/event-bus/status")
                state = get_json(f"{base}/event-bus/latest-state")
                tick = (state.get("market") or {}).get("latest_tick") or {}
                session = state.get("session") or {}
                signal = (state.get("strategy") or {}).get("latest_signal") or {}
                paper = state.get("paper") or {}
                safety = state.get("safety") or {}
                print(
                    f"time={time.strftime('%H:%M:%S')} event_count={status.get('event_count')} "
                    f"last_sequence={status.get('last_sequence')} last_event_type={status.get('last_event_type')} "
                    f"market_bid={tick.get('bid')} market_ask={tick.get('ask')} "
                    f"session={session.get('current_session') or session.get('session_name')} "
                    f"latest_signal={signal.get('status') or signal.get('direction') or signal.get('id')} "
                    f"paper_open={paper.get('open_count')} paper_closed={paper.get('closed_count')} "
                    f"live_execution_allowed={safety.get('live_execution_allowed')} "
                    f"command_queueing_allowed={safety.get('command_queueing_allowed')}"
                )
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                print(f"FAIL: {exc}")
            time.sleep(5)
    except KeyboardInterrupt:
        print("stopped")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
