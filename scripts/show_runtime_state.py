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
    url = f"http://{host}:{port}/event-bus/latest-state"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            state = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read runtime state at {url}: {exc}")
        return 1
    tick = (state.get("market") or {}).get("latest_tick") or {}
    account = state.get("account") or {}
    session = state.get("session") or {}
    context = state.get("context") or {}
    signal = (state.get("strategy") or {}).get("latest_signal") or {}
    risk = (state.get("risk") or {}).get("latest_decision") or {}
    paper = state.get("paper") or {}
    safety = state.get("safety") or {}
    print(f"generated_at: {state.get('generated_at')}")
    print(f"symbol: {state.get('symbol')}")
    print(f"last_sequence: {state.get('last_sequence')}")
    print(f"market: bid={tick.get('bid')} ask={tick.get('ask')} spread={tick.get('spread_points')}")
    print(f"account: balance={account.get('balance')} equity={account.get('equity')} currency={account.get('currency')}")
    print(f"session: current={session.get('current_session') or session.get('session_name')} allowed={session.get('allowed') if 'allowed' in session else session.get('session_allowed')}")
    print(f"context: regime={context.get('regime')} bias={context.get('directional_bias') or context.get('context_bias')}")
    print(f"latest_signal: {signal.get('status') or signal.get('direction') or signal.get('id')}")
    print(f"risk_latest_decision: {risk.get('status') or risk.get('risk_status') or risk.get('id')}")
    print(f"paper: open={paper.get('open_count')} closed={paper.get('closed_count')}")
    print(f"safety.live_execution_allowed: {safety.get('live_execution_allowed')}")
    print(f"safety.command_queueing_allowed: {safety.get('command_queueing_allowed')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
