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
    url = f"http://{host}:{port}/ai-review/status"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read AI review status at {url}: {exc}")
        return 1
    print("AURIX AI Review")
    print(f"enabled: {data.get('enabled')}")
    print(f"mode: {data.get('mode')}")
    print(f"allow_external_llm: {data.get('allow_external_llm')}")
    print(f"reports_count: {data.get('reports_count')}")
    print(f"latest_summary: {data.get('latest_summary')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
