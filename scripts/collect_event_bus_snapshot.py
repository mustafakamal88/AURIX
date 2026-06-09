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
    url = f"http://{host}:{port}/event-bus/collect"
    request = urllib.request.Request(url, data=b"{}", method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not collect event bus snapshot at {url}: {exc}")
        return 1
    print(f"published_count: {data.get('published_count')}")
    print(f"event_types_published: {', '.join([str(item) for item in data.get('event_types') or []])}")
    print(f"last_sequence: {data.get('last_sequence')}")
    print(f"state_snapshot_path: {data.get('state_snapshot_path')}")
    print(f"state_exists: {data.get('state_exists')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
