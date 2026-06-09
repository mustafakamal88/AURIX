from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from dotenv import load_dotenv


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    interval = float(os.getenv("AURIX_SIGNAL_PATH_WATCH_SECONDS", "10"))
    url = f"http://{host}:{port}/signal-certifier/status"
    print(f"Watching latest signal path report every {interval:g}s. Press Ctrl+C to stop.")
    try:
        while True:
            try:
                status_payload = get_json(url)
                report = status_payload.get("latest") or {}
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                print(f"FAIL: {exc}")
                time.sleep(interval)
                continue
            failed = [str(item) for item in report.get("failed_checks") or []]
            warnings = [str(item) for item in report.get("warnings") or []]
            print(" | ".join([
                f"time={time.strftime('%Y-%m-%dT%H:%M:%S%z')}",
                f"status={report.get('status')}",
                f"trade_id={report.get('certified_trade_id')}",
                f"signal_id={report.get('certified_signal_id')}",
                f"strategy={report.get('strategy')}",
                f"direction={report.get('direction')}",
                f"trade_status={report.get('trade_status')}",
                f"passed={len(report.get('passed_checks') or [])}",
                f"failed={len(failed)}",
                f"warnings={len(warnings)}",
                f"top_failed={'; '.join(failed[:2]) or 'none'}",
                f"top_warnings={'; '.join(warnings[:2]) or 'none'}",
            ]))
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped signal path watch.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
