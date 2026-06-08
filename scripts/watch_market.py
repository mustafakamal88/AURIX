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
    interval = float(os.getenv("AURIX_MARKET_WATCH_SECONDS", "5"))
    url = f"http://{host}:{port}/market/status"
    print(f"Watching market quality every {interval:g}s. Press Ctrl+C to stop.")

    try:
        while True:
            try:
                with urllib.request.urlopen(url, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                print(f"FAIL: {exc}")
                time.sleep(interval)
                continue

            quality = data.get("quality") or {}
            reasons = quality.get("reasons") or []
            print(
                " | ".join(
                    [
                        f"symbol={data.get('symbol')}",
                        f"ticks={data.get('tick_count')}",
                        f"candles={data.get('candle_count')}",
                        f"spread={quality.get('spread_points')}",
                        f"ok={quality.get('ok')}",
                        f"reasons={'; '.join(reasons) if reasons else 'none'}",
                    ]
                )
            )
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped market watch.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
