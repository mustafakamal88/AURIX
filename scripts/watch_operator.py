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
    interval = float(os.getenv("AURIX_OPERATOR_WATCH_SECONDS", "5"))
    url = f"http://{host}:{port}/operator/summary"
    print(f"Watching operator summary every {interval:g}s. Press Ctrl+C to stop.")

    try:
        while True:
            try:
                summary = get_json(url)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                print(f"FAIL: {exc}")
                time.sleep(interval)
                continue

            warnings = summary.get("warnings") or []
            print(
                " | ".join(
                    [
                        f"time={time.strftime('%Y-%m-%dT%H:%M:%S%z')}",
                        f"ok={summary.get('ok')}",
                        f"mode={summary.get('mode')}",
                        f"symbol={summary.get('symbol')}",
                        f"session={summary.get('session')}",
                        f"regime={summary.get('regime')}",
                        f"spread={summary.get('spread_points')}",
                        f"paper_open={summary.get('paper_open_count')}",
                        f"paper_closed={summary.get('paper_closed_trades')}",
                        f"win_rate={summary.get('paper_win_rate')}",
                        f"total_r={summary.get('paper_total_r')}",
                        f"expectancy_r={summary.get('paper_expectancy_r')}",
                        f"journal_entries={summary.get('journal_entry_count')}",
                        f"journal_latest={summary.get('journal_latest_classification')}",
                        f"warnings={'; '.join(str(warning) for warning in warnings) if warnings else 'none'}",
                    ]
                )
            )
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped operator watch.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
