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
    url = f"http://{host}:{port}/analytics/paper/summary"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read paper analytics summary at {url}: {exc}")
        return 1

    print("AURIX Paper Analytics")
    print(f"generated_at: {data.get('generated_at')}")
    print(f"total_trades: {data.get('total_trades')}")
    print(f"closed_trades: {data.get('closed_trades')}")
    print(f"win_rate: {data.get('win_rate')}")
    print(f"total_r: {data.get('total_r')}")
    print(f"expectancy_r: {data.get('expectancy_r')}")
    warnings = data.get("warnings") or []
    print(f"warnings: {'; '.join(str(warning) for warning in warnings) if warnings else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
