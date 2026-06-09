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
    url = f"http://{host}:{port}/signal-certifier/certify"
    try:
        report = post_json(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not certify signal path at {url}: {exc}")
        return 1
    setup = "; ".join(str(item) for item in (report.get("strategy_trace") or {}).get("reasons") or [])
    print("AURIX Signal Path Certification Report")
    print(f"status: {report.get('status')}")
    print(f"trade_id: {report.get('certified_trade_id')}")
    print(f"signal_id: {report.get('certified_signal_id')}")
    print(f"strategy: {report.get('strategy')}")
    print(f"direction: {report.get('direction')}")
    print(f"trade_status: {report.get('trade_status')}")
    print(f"setup_reason: {setup or 'none'}")
    print(f"passed_checks: {'; '.join(report.get('passed_checks') or []) or 'none'}")
    print(f"skipped_checks: {'; '.join(report.get('skipped_checks') or []) or 'none'}")
    print(f"failed_checks: {'; '.join(report.get('failed_checks') or []) or 'none'}")
    print(f"warnings: {'; '.join(report.get('warnings') or []) or 'none'}")
    print(f"recommendations: {'; '.join(report.get('recommendations') or []) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
