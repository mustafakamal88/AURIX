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
    interval = float(os.getenv("AURIX_DAEMON_WATCH_SECONDS", "5"))
    url = f"http://{host}:{port}/daemon/status"
    print(f"Watching paper daemon every {interval:g}s. Press Ctrl+C to stop.")
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
                        f"loops={status.get('loop_count')}",
                        f"heartbeat={status.get('last_heartbeat_at')}",
                        f"quality_ok={status.get('market_quality_ok')}",
                        f"open_paper={status.get('open_paper_trades')}",
                        f"evidence={status.get('last_evidence_status')}",
                        f"errors={'; '.join(str(error) for error in status.get('errors') or []) or 'none'}",
                    ]
                )
            )
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped daemon watch.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
