from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    url = f"http://{host}:{port}/health"

    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: AURIX bridge server is not healthy at {url}: {exc}")
        return 1

    if data.get("ok") is True:
        print(f"OK: AURIX bridge server is healthy at {url}")
        print(f"Terminal ID: {data.get('terminal_id')}")
        return 0

    print(f"FAIL: Unexpected health response from {url}: {data}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
