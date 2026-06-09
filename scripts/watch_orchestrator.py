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
    interval = float(os.getenv("AURIX_ORCHESTRATOR_WATCH_SECONDS", "5"))
    url = f"http://{host}:{port}/orchestrator/status"
    print(f"Watching orchestrator every {interval:g}s. Press Ctrl+C to stop.")
    try:
        while True:
            try:
                status = get_json(url)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                print(f"FAIL: {exc}")
                time.sleep(interval)
                continue
            print(
                " | ".join(
                    [
                        f"time={time.strftime('%Y-%m-%dT%H:%M:%S%z')}",
                        f"running={status.get('running')}",
                        f"session={status.get('current_session')}",
                        f"allowed={status.get('session_allowed')}",
                        f"daemon={status.get('daemon_running')}",
                        f"forward={status.get('forward_test_progress')}",
                        f"evidence={status.get('evidence_status')}",
                        f"operator_ok={status.get('operator_ok')}",
                        f"warnings={'; '.join(str(item) for item in status.get('warnings') or []) or 'none'}",
                        f"errors={'; '.join(str(item) for item in status.get('errors') or []) or 'none'}",
                    ]
                )
            )
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped orchestrator watch.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
