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
    interval = float(os.getenv("AURIX_EVIDENCE_GROWTH_WATCH_SECONDS", "10"))
    url = f"http://{host}:{port}/evidence-monitor/evaluate"
    print(f"Watching evidence growth every {interval:g}s. Press Ctrl+C to stop.")
    try:
        while True:
            try:
                report = post_json(url)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                print(f"FAIL: {exc}")
                time.sleep(interval)
                continue
            current = report.get("current") or {}
            targets = report.get("targets") or {}
            missing = [str(item) for item in report.get("missing_requirements") or []]
            blocking = [str(item) for item in report.get("blocking_reasons") or []]
            print(
                " | ".join(
                    [
                        f"time={time.strftime('%Y-%m-%dT%H:%M:%S%z')}",
                        f"status={report.get('status')}",
                        f"progress={report.get('overall_progress')}",
                        f"closed={current.get('closed_paper_trades')}/{targets.get('closed_paper_trades')}",
                        f"candles={current.get('recorded_candles')}/{targets.get('recorded_candles')}",
                        f"days={current.get('forward_tested_days')}/{targets.get('forward_tested_days')}",
                        f"missing={len(missing)}",
                        f"top_missing={'; '.join(missing[:3]) or 'none'}",
                        f"top_blocks={'; '.join(blocking[:3]) or 'none'}",
                    ]
                )
            )
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped evidence growth watch.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
