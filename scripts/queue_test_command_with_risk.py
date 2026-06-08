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
    terminal_id = os.getenv("AURIX_TERMINAL_ID", "AURIX-MAC-001")
    url = f"http://{host}:{port}/commands/open-market"

    payload = {
        "terminal_id": terminal_id,
        "symbol": "XAUUSDm",
        "direction": "BUY",
        "volume": 0.01,
        "sl": None,
        "tp": None,
        "comment": "AURIX-RISK-TEST-DRY-COMMAND",
        "live_confirm": "I_ACCEPT_LIVE_RISK",
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print("APPROVED: Risk Governor allowed the test command and it was queued.")
            print(json.dumps(data, indent=2))
            print()
            print("EA safety still blocks live execution unless AllowLiveTrading=true is manually enabled.")
            return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = {"raw": body}
        print("BLOCKED: Risk Governor rejected the test command.")
        print(json.dumps(data, indent=2))
        return 1
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"FAIL: could not queue test command at {url}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
