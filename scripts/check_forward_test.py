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
    url = f"http://{host}:{port}/forward-test/status"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read forward test status at {url}: {exc}")
        return 1
    campaign = data.get("campaign") or {}
    progress = campaign.get("progress") or {}
    print("AURIX Forward Test")
    print(f"enabled: {data.get('enabled')}")
    print(f"status: {campaign.get('status')}")
    print(f"progress: {progress.get('percent')}")
    print(f"closed_paper_trades: {campaign.get('closed_paper_trades')}")
    print(f"blocking_reasons: {'; '.join(str(item) for item in campaign.get('blocking_reasons') or []) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
