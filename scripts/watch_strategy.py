from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    interval = float(os.getenv("AURIX_STRATEGY_WATCH_SECONDS", "5"))
    url = f"http://{host}:{port}/strategy/evaluate"

    print(f"Watching shadow strategy every {interval:g}s. Press Ctrl+C to stop.")
    while True:
        req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                signal = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"FAIL: {exc}")
            time.sleep(interval)
            continue

        print(
            " | ".join(
                [
                    f"time={signal.get('created_at')}",
                    f"symbol={signal.get('symbol')}",
                    f"status={signal.get('status')}",
                    f"direction={signal.get('direction')}",
                    f"confidence={signal.get('confidence')}",
                    f"reasons={'; '.join(signal.get('reasons') or [])}",
                ]
            )
        )
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
