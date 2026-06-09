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
    url = f"http://{host}:{port}/daemon/status"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            status = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read daemon status at {url}: {exc}")
        return 1
    print("AURIX Paper Daemon")
    print(f"enabled: {status.get('enabled')}")
    print(f"mode: {status.get('mode')}")
    print(f"running: {status.get('running')}")
    print(f"loop_count: {status.get('loop_count')}")
    print(f"last_heartbeat_at: {status.get('last_heartbeat_at')}")
    print(f"errors: {'; '.join(str(error) for error in status.get('errors') or []) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
