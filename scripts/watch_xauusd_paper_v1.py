from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from dotenv import load_dotenv


def post_json(url: str) -> dict:
    req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(url: str) -> list[dict]:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    interval = float(os.getenv("AURIX_XAUUSD_PAPER_V1_WATCH_SECONDS", "5"))
    base_url = f"http://{host}:{port}"
    print(f"Watching XAUUSD Paper V1 every {interval:g}s. Press Ctrl+C to stop.")

    try:
        while True:
            try:
                context = post_json(f"{base_url}/context/evaluate")
                paper_result = post_json(f"{base_url}/paper/evaluate-paper-v1")
                update = post_json(f"{base_url}/paper/update")
                open_trades = get_json(f"{base_url}/paper/open")
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                print(f"FAIL: {exc}")
                time.sleep(interval)
                continue

            signal = paper_result.get("signal") or {}
            reasons = signal.get("reasons") or [paper_result.get("reason", "")]
            print(
                " | ".join(
                    [
                        f"session={context.get('session_name')}",
                        f"regime={context.get('regime')}",
                        f"signal={signal.get('status')}",
                        f"direction={signal.get('direction')}",
                        f"open_paper={len(open_trades)}",
                        f"closed_now={len(update.get('updated') or [])}",
                        f"reasons={'; '.join(reason for reason in reasons if reason)}",
                    ]
                )
            )
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped XAUUSD Paper V1 watch.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
