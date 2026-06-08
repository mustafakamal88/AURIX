from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv


def post_json(url: str) -> dict:
    req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    url = f"http://{host}:{port}/journal/review-paper-trades"
    try:
        result = post_json(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not review paper trades at {url}: {exc}")
        return 1
    print(f"paper_trade_reviews: {result.get('paper_trade_reviews')}")
    latest = (result.get("entries") or [])[-1] if result.get("entries") else {}
    print(f"latest_classification: {latest.get('classification')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
