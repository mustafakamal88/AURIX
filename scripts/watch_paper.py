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
    interval = float(os.getenv("AURIX_PAPER_WATCH_SECONDS", "5"))
    base_url = f"http://{host}:{port}"
    print(f"Watching paper trades every {interval:g}s. Press Ctrl+C to stop.")

    try:
        while True:
            try:
                evaluation = post_json(f"{base_url}/paper/evaluate-signal")
                update = post_json(f"{base_url}/paper/update")
                open_trades = get_json(f"{base_url}/paper/open")
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                print(f"FAIL: {exc}")
                time.sleep(interval)
                continue

            print(
                " | ".join(
                    [
                        f"created={evaluation.get('created')}",
                        f"reason={evaluation.get('reason', 'paper trade evaluated')}",
                        f"open={len(open_trades)}",
                        f"closed_now={len(update.get('updated') or [])}",
                    ]
                )
            )
            for trade in open_trades:
                print(
                    f"OPEN id={trade.get('id')} {trade.get('direction')} entry={trade.get('entry_price')} "
                    f"sl={trade.get('stop_loss')} tp={trade.get('take_profit')}"
                )
            for trade in update.get("updated") or []:
                print(
                    f"CLOSED id={trade.get('id')} status={trade.get('status')} "
                    f"pnl_points={trade.get('pnl_points')} r={trade.get('r_multiple')}"
                )
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped paper watch.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
