from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from dotenv import load_dotenv


def post_json(url: str) -> dict:
    req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    interval = float(os.getenv("AURIX_ANALYTICS_WATCH_SECONDS", "10"))
    url = f"http://{host}:{port}/analytics/paper/generate"
    print(f"Watching paper analytics every {interval:g}s. Press Ctrl+C to stop.")

    try:
        while True:
            try:
                report = post_json(url)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                print(f"FAIL: {exc}")
                time.sleep(interval)
                continue

            warnings = report.get("warnings") or []
            print(
                " | ".join(
                    [
                        f"total={report.get('total_trades')}",
                        f"closed={report.get('closed_trades')}",
                        f"win_rate={report.get('win_rate')}",
                        f"total_r={report.get('total_r')}",
                        f"expectancy_r={report.get('expectancy_r')}",
                        f"warnings={'; '.join(str(warning) for warning in warnings) if warnings else 'none'}",
                    ]
                )
            )
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped analytics watch.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
