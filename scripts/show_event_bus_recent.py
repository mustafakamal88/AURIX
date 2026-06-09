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
    url = f"http://{host}:{port}/event-bus/recent?{urllib.parse.urlencode({'limit': limit})}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read event bus recent at {url}: {exc}")
        return 1
    for event in data.get("items") or []:
        print(
            f"{event.get('sequence')} | {event.get('created_at')} | {event.get('event_type')} | "
            f"{event.get('source')} | {event.get('symbol')} | {event.get('correlation_id')} | {event.get('causation_id')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
