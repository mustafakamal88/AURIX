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
    url = f"http://{host}:{port}/evidence-monitor/status"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read evidence growth status at {url}: {exc}")
        return 1
    latest = data.get("latest") or {}
    checkpoints = latest.get("checkpoints") or {}
    print("AURIX Evidence Growth")
    print(f"enabled: {data.get('enabled')}")
    print(f"symbol: {data.get('symbol')}")
    print(f"mode: {data.get('mode')}")
    print(f"latest_exists: {data.get('latest_exists')}")
    print(f"status: {latest.get('status')}")
    print(f"overall_progress: {latest.get('overall_progress')}")
    print(f"closed_paper_trades_progress: {(checkpoints.get('closed_paper_trades') or {}).get('progress')}")
    print(f"recorded_candles_progress: {(checkpoints.get('recorded_candles') or {}).get('progress')}")
    print(f"forward_days_progress: {(checkpoints.get('forward_tested_days') or {}).get('progress')}")
    print(f"missing_requirements: {len(latest.get('missing_requirements') or [])}")
    print(f"blocking_reasons: {len(latest.get('blocking_reasons') or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
