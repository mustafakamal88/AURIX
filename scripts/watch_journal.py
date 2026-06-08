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


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    interval = float(os.getenv("AURIX_JOURNAL_WATCH_SECONDS", "10"))
    base_url = f"http://{host}:{port}"
    print(f"Watching journal every {interval:g}s. Press Ctrl+C to stop.")
    try:
        while True:
            try:
                paper = post_json(f"{base_url}/journal/review-paper-trades")
                signals = post_json(f"{base_url}/journal/review-signals")
                post_json(f"{base_url}/journal/generate-daily-summary")
                status = get_json(f"{base_url}/journal/status")
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                print(f"FAIL: {exc}")
                time.sleep(interval)
                continue
            print(
                " | ".join(
                    [
                        f"entries={status.get('entries_count')}",
                        f"paper_reviews={paper.get('paper_trade_reviews')}",
                        f"signal_reviews={signals.get('signal_reviews')}",
                        f"latest={status.get('latest_classification')}",
                    ]
                )
            )
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped journal watch.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
