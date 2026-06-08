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
    url = f"http://{host}:{port}/context/status"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read context status at {url}: {exc}")
        return 1

    latest = data.get("latest") or {}
    print("AURIX Context")
    print(f"enabled: {data.get('enabled')}")
    print(f"symbol: {data.get('symbol')}")
    print(f"contexts_count: {data.get('contexts_count')}")
    print(f"session: {latest.get('session_name')}")
    print(f"regime: {latest.get('regime')}")
    print(f"bias: {latest.get('directional_bias')}")
    print(f"spread_ok: {latest.get('spread_ok')}")
    reasons = latest.get("reasons") or []
    print(f"reasons: {', '.join(reasons) if reasons else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
