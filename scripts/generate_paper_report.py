from __future__ import annotations

import json
import os
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
    url = f"http://{host}:{port}/analytics/paper/generate"
    try:
        report = post_json(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not generate paper analytics report at {url}: {exc}")
        return 1

    print("AURIX Paper Performance Report")
    print(f"generated_at: {report.get('generated_at')}")
    print(f"total_trades: {report.get('total_trades')}")
    print(f"open_trades: {report.get('open_trades')}")
    print(f"closed_trades: {report.get('closed_trades')}")
    print(f"wins: {report.get('wins')}")
    print(f"losses: {report.get('losses')}")
    print(f"win_rate: {report.get('win_rate')}")
    print(f"total_pnl_points: {report.get('total_pnl_points')}")
    print(f"average_pnl_points: {report.get('average_pnl_points')}")
    print(f"total_r: {report.get('total_r')}")
    print(f"expectancy_r: {report.get('expectancy_r')}")
    print(f"profit_factor: {report.get('profit_factor')}")
    print(f"max_consecutive_wins: {report.get('max_consecutive_wins')}")
    print(f"max_consecutive_losses: {report.get('max_consecutive_losses')}")
    warnings = report.get("warnings") or []
    print(f"warnings: {'; '.join(str(warning) for warning in warnings) if warnings else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
