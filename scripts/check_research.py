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
    url = f"http://{host}:{port}/research/status"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read research status at {url}: {exc}")
        return 1
    latest = data.get("latest") or {}
    best = latest.get("best_by_expectancy") or {}
    print("AURIX Research")
    print(f"enabled: {data.get('enabled')}")
    print(f"symbol: {data.get('symbol')}")
    print(f"latest_exists: {data.get('latest_exists')}")
    print(f"warning_count: {data.get('warning_count')}")
    print(f"best_expectancy_r: {best.get('expectancy_r')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
