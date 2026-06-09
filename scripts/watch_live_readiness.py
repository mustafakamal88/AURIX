from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from dotenv import load_dotenv


def post_json(url: str) -> dict:
    req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    interval = float(os.getenv("AURIX_LIVE_READINESS_WATCH_SECONDS", "10"))
    url = f"http://{host}:{port}/live-readiness/evaluate"
    print(f"Watching live readiness every {interval:g}s. Press Ctrl+C to stop.")
    try:
        while True:
            try:
                report = post_json(url)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                print(f"FAIL: {exc}")
                time.sleep(interval)
                continue
            reasons = [str(item) for item in report.get("blocking_reasons") or []]
            print(
                " | ".join(
                    [
                        f"time={time.strftime('%Y-%m-%dT%H:%M:%S%z')}",
                        f"status={report.get('status')}",
                        f"score={report.get('score')}",
                        f"arming_allowed={report.get('live_arming_allowed')}",
                        f"execution_allowed={report.get('live_execution_allowed')}",
                        f"blocks={len(reasons)}",
                        f"top_blocks={'; '.join(reasons[:3]) or 'none'}",
                    ]
                )
            )
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped live readiness watch.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
