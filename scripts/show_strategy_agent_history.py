from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    url = f"http://{host}:{port}/strategy-agents/history?{urllib.parse.urlencode({'limit': limit})}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read strategy agent history at {url}: {exc}")
        return 1
    for item in data.get("items") or []:
        print(
            f"{item.get('generated_at')} | {item.get('agent_id')} | {item.get('strategy_name')} | "
            f"{item.get('status')} | {item.get('direction')} | {item.get('confidence')} | {item.get('event_id')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
