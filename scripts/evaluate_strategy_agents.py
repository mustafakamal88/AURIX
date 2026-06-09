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
    url = f"http://{host}:{port}/strategy-agents/evaluate"
    request = urllib.request.Request(url, data=b"{}", method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not evaluate strategy agents at {url}: {exc}")
        return 1
    for item in data.get("items") or []:
        reasons = "; ".join(reason.get("message", "") for reason in item.get("rejection_reasons") or [])
        print(
            f"agent_id={item.get('agent_id')} strategy={item.get('strategy_name')} status={item.get('status')} "
            f"direction={item.get('direction')} confidence={item.get('confidence')} "
            f"setup_reason={item.get('setup_reason')} rejection_reasons={reasons} event_id={item.get('event_id')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
