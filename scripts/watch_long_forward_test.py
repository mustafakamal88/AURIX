from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from dotenv import load_dotenv


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    load_dotenv()
    base = f"http://{os.getenv('AURIX_HOST', '127.0.0.1')}:{os.getenv('AURIX_PORT', '8765')}"
    interval = float(os.getenv("AURIX_LONG_FORWARD_WATCH_SECONDS", "5"))
    print(f"Watching long forward-test every {interval:g}s. Press Ctrl+C to stop.")
    try:
        while True:
            try:
                status = get_json(f"{base}/long-forward-test/status")
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                print(f"FAIL: {exc}")
                time.sleep(interval)
                continue
            warnings = "; ".join(str(item) for item in status.get("warnings") or [])
            errors = "; ".join(str(item) for item in status.get("errors") or [])
            print(
                " | ".join(
                    [
                        time.strftime("%H:%M:%S"),
                        f"running={status.get('running')}",
                        f"session={status.get('current_session')}",
                        f"session_allowed={status.get('session_allowed')}",
                        f"orchestrator_running={status.get('orchestrator_running')}",
                        f"progress={status.get('forward_test_progress')}%",
                        f"candles={status.get('recorded_candles')}",
                        f"closed={status.get('paper_closed_trades')}",
                        f"expectancy_r={status.get('latest_expectancy_r')}",
                        f"evidence={status.get('evidence_status')}",
                        f"live_ready={status.get('evidence_live_ready')}",
                        f"warnings={warnings or 'none'}",
                        f"errors={errors or 'none'}",
                    ]
                )
            )
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped long forward-test watch.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
