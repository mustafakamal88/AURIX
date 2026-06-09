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
    url = f"http://{host}:{port}/forward-test/update"
    try:
        campaign = post_json(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not update forward test at {url}: {exc}")
        return 1
    progress = campaign.get("progress") or {}
    print("AURIX Forward Test Update")
    print(f"status: {campaign.get('status')}")
    print(f"days_observed: {campaign.get('days_observed')}")
    print(f"sessions_observed: {', '.join(campaign.get('sessions_observed') or []) or 'none'}")
    print(f"recorded_candles: {campaign.get('recorded_candles')}")
    print(f"closed_paper_trades: {campaign.get('closed_paper_trades')}")
    print(f"daemon_loops: {campaign.get('daemon_loops')}")
    print(f"progress: {progress.get('percent')}")
    print(f"blocking_reasons: {'; '.join(str(item) for item in campaign.get('blocking_reasons') or []) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
