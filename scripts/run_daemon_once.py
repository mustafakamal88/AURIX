from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv


def post_json(url: str) -> dict:
    req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    url = f"http://{host}:{port}/daemon/run-once"
    try:
        status = post_json(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not run daemon once at {url}: {exc}")
        return 1
    print("AURIX Paper Daemon Run")
    print(f"running: {status.get('running')}")
    print(f"loop_count: {status.get('loop_count')}")
    print(f"market_quality_ok: {status.get('market_quality_ok')}")
    print(f"last_signal_id: {status.get('last_signal_id')}")
    print(f"open_paper_trades: {status.get('open_paper_trades')}")
    print(f"last_evidence_status: {status.get('last_evidence_status')}")
    print(f"errors: {'; '.join(str(error) for error in status.get('errors') or []) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
