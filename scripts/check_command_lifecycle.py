from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from dotenv import load_dotenv


TERMINAL_STATUSES = {
    "EXECUTION_BLOCKED",
    "EXECUTION_FAILED",
    "EXECUTION_FILLED",
    "CANCELLED",
    "EXPIRED",
}


def request_json(url: str, payload: dict | None = None) -> dict:
    data = None
    method = "GET"
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        method = "POST"
        headers = {"Content-Type": "application/json"}

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    terminal_id = os.getenv("AURIX_TERMINAL_ID", "AURIX-MAC-001")
    base_url = f"http://{host}:{port}"

    payload = {
        "terminal_id": terminal_id,
        "symbol": "XAUUSDm",
        "direction": "BUY",
        "volume": 0.01,
        "sl": None,
        "tp": None,
        "comment": "AURIX-LIFECYCLE-TEST-DRY-COMMAND",
        "live_confirm": "I_ACCEPT_LIVE_RISK",
    }

    try:
        command = request_json(f"{base_url}/commands/open-market", payload)
    except urllib.error.HTTPError as exc:
        print("FAILED: command was blocked before queueing.")
        print(exc.read().decode("utf-8"))
        return 1
    except urllib.error.URLError as exc:
        print(f"FAILED: server not reachable: {exc}")
        return 1

    command_id = command["id"]
    print(f"command_id={command_id}")
    print(f"initial_status={command.get('status')}")

    last_status = None
    deadline = time.time() + 45
    while time.time() < deadline:
        current = request_json(f"{base_url}/commands/{command_id}")
        status = current.get("status")
        if status != last_status:
            print(
                "status="
                f"{status} dispatch_count={current.get('dispatch_count')} "
                f"risk_decision_id={current.get('risk_decision_id')} "
                f"execution_result_id={current.get('execution_result_id')}"
            )
            last_status = status

        if status in TERMINAL_STATUSES:
            print("final_command:")
            print(json.dumps(current, indent=2))
            return 0

        time.sleep(2)

    print("final_status=TIMEOUT")
    print("Command is not terminal yet. If MT5 EA is not polling, it may expire on the next command check.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
