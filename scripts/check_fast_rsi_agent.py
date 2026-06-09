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
    base = f"http://{host}:{port}"
    try:
        with urllib.request.urlopen(f"{base}/strategy-agents/status", timeout=5) as resp:
            status = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read Fast RSI status: {exc}")
        return 1
    config = ((status.get("config") or {}).get("fast_rsi_first_reversal") or {})
    latest = status.get("latest_fast_rsi") or {}
    trace = latest.get("decision_trace") or {}
    print(f"enabled: {config.get('enabled')}")
    print(f"symbol: {config.get('symbol')}")
    print(f"timeframe: {config.get('timeframe')}")
    print(f"latest_status: {latest.get('status')}")
    print(f"direction: {latest.get('direction')}")
    print(f"confidence: {latest.get('confidence')}")
    print(f"rsi_current: {trace.get('rsi_current')}")
    print(f"rsi_sma_current: {trace.get('rsi_sma_current')}")
    print(
        "state_flags: "
        f"below={trace.get('rsi_was_below_buy_extreme_after')} "
        f"above={trace.get('rsi_was_above_sell_extreme_after')}"
    )
    print(f"rejection_reasons: {latest.get('rejection_reasons')}")
    print(f"event_id: {latest.get('event_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
