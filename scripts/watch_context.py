from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    interval = float(os.getenv("AURIX_CONTEXT_WATCH_SECONDS", "5"))
    url = f"http://{host}:{port}/context/evaluate"
    print(f"Watching context every {interval:g}s. Press Ctrl+C to stop.")

    try:
        while True:
            req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    context = json.loads(resp.read().decode("utf-8"))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                print(f"FAIL: {exc}")
                time.sleep(interval)
                continue

            print(
                " | ".join(
                    [
                        f"time={context.get('created_at')}",
                        f"symbol={context.get('symbol')}",
                        f"session={context.get('session_name')}",
                        f"regime={context.get('regime')}",
                        f"bias={context.get('directional_bias')}",
                        f"spread_ok={context.get('spread_ok')}",
                        f"reasons={'; '.join(context.get('reasons') or [])}",
                    ]
                )
            )
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped context watch.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
