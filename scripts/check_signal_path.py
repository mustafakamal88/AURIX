from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    url = f"http://{host}:{port}/signal-certifier/status"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read signal path status at {url}: {exc}")
        return 1
    latest = data.get("latest") or {}
    print("AURIX Signal Path Certification")
    print(f"enabled: {data.get('enabled')}")
    print(f"symbol: {data.get('symbol')}")
    print(f"mode: {data.get('mode')}")
    print(f"latest_exists: {data.get('latest_exists')}")
    print(f"status: {latest.get('status')}")
    print(f"certified_trade_id: {latest.get('certified_trade_id')}")
    print(f"certified_signal_id: {latest.get('certified_signal_id')}")
    print(f"strategy: {latest.get('strategy')}")
    print(f"direction: {latest.get('direction')}")
    print(f"trade_status: {latest.get('trade_status')}")
    print(f"passed_checks: {len(latest.get('passed_checks') or [])}")
    print(f"skipped_checks: {len(latest.get('skipped_checks') or [])}")
    print(f"failed_checks: {len(latest.get('failed_checks') or [])}")
    print(f"warnings: {len(latest.get('warnings') or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
