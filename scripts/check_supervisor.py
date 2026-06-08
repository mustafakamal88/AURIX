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
    url = f"http://{host}:{port}/supervisor/status"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read supervisor status at {url}: {exc}")
        return 1

    print("AURIX Paper Supervisor")
    print(f"enabled: {data.get('enabled')}")
    print(f"mode: {data.get('mode')}")
    print(f"last_heartbeat_at: {data.get('last_heartbeat_at')}")
    print(f"market_quality_ok: {data.get('market_quality_ok')}")
    print(f"paper_open_count: {data.get('paper_open_count')}")
    print(f"loop_count: {data.get('loop_count')}")
    errors = data.get("errors") or []
    if errors:
        print(f"errors: {'; '.join(str(error) for error in errors)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
