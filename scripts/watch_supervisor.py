from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from dotenv import load_dotenv


def post_json(url: str) -> dict:
    req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(url: str):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    interval = float(os.getenv("AURIX_SUPERVISOR_WATCH_SECONDS", "5"))
    base_url = f"http://{host}:{port}"
    print(f"Watching paper supervisor every {interval:g}s. Press Ctrl+C to stop.")

    try:
        while True:
            try:
                status = post_json(f"{base_url}/supervisor/run-once")
                open_trades = get_json(f"{base_url}/paper/open")
                context = get_json(f"{base_url}/context/latest")
                signals = get_json(f"{base_url}/strategy/signals")
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                print(f"FAIL: {exc}")
                time.sleep(interval)
                continue

            signal_id = status.get("strategy_signal_id")
            latest_signal = next((signal for signal in signals if signal.get("id") == signal_id), {}) if signal_id else {}
            errors = status.get("errors") or []
            print(
                " | ".join(
                    [
                        f"time={status.get('last_heartbeat_at')}",
                        f"mode={status.get('mode')}",
                        f"market_quality_ok={status.get('market_quality_ok')}",
                        f"session={context.get('session_name') or 'n/a'}",
                        f"regime={context.get('regime') or 'n/a'}",
                        f"signal={latest_signal.get('status') or 'n/a'}",
                        f"paper_created={status.get('paper_created')}",
                        f"open_paper={status.get('paper_open_count')}",
                        f"errors={'; '.join(str(error) for error in errors) if errors else 'none'}",
                    ]
                )
            )
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped supervisor watch.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
