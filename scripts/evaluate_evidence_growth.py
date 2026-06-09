from __future__ import annotations

import json
import os
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
    url = f"http://{host}:{port}/evidence-monitor/evaluate"
    try:
        report = post_json(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not evaluate evidence growth at {url}: {exc}")
        return 1
    current = report.get("current") or {}
    print("AURIX Evidence Growth Report")
    print(f"status: {report.get('status')}")
    print(f"overall_progress: {report.get('overall_progress')}")
    print(f"closed_paper_trades: {current.get('closed_paper_trades')}")
    print(f"recorded_candles: {current.get('recorded_candles')}")
    print(f"forward_tested_days: {current.get('forward_tested_days')}")
    print(f"missing_requirements: {'; '.join(str(item) for item in report.get('missing_requirements') or []) or 'none'}")
    print(f"blocking_reasons: {'; '.join(str(item) for item in report.get('blocking_reasons') or []) or 'none'}")
    print(f"recommendations: {'; '.join(str(item) for item in report.get('recommendations') or []) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
