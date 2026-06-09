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
    url = f"http://{host}:{port}/backtest/run"
    try:
        report = post_json(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not run backtest at {url}: {exc}")
        return 1
    print("AURIX Backtest Report")
    print(f"candles_used: {report.get('candles_used')}")
    print(f"trades: {report.get('trades')}")
    print(f"wins: {report.get('wins')}")
    print(f"losses: {report.get('losses')}")
    print(f"win_rate: {report.get('win_rate')}")
    print(f"total_r: {report.get('total_r')}")
    print(f"expectancy_r: {report.get('expectancy_r')}")
    warnings = report.get("warnings") or []
    print(f"warnings: {'; '.join(str(warning) for warning in warnings) if warnings else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
