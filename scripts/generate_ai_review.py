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
    url = f"http://{host}:{port}/ai-review/generate"
    try:
        report = post_json(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not generate AI review at {url}: {exc}")
        return 1
    print("AURIX AI Review Report")
    print(f"id: {report.get('id')}")
    print(f"mode: {report.get('mode')}")
    print(f"summary: {report.get('summary')}")
    print("performance:")
    for item in report.get("performance_observations") or []:
        print(f"- {item}")
    print("action_items:")
    for item in report.get("action_items") or []:
        print(f"- {item}")
    print(f"safety: {json.dumps(report.get('safety') or {}, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
