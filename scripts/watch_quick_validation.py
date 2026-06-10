#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any


def request_json(base_url: str, api_key: str | None = None) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-AURIX-API-Key"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(base_url.rstrip("/") + "/quick-validation/run", data=b"{}", headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    base_url = os.getenv("AURIX_BASE_URL", "http://127.0.0.1:8765")
    api_key = os.getenv("AURIX_API_KEY") or None
    interval = float(os.getenv("AURIX_QUICK_VALIDATION_WATCH_SECONDS", "60"))
    try:
        while True:
            try:
                report = request_json(base_url, api_key)
                summary = report.get("summary") or {}
                print(
                    f"{datetime.now().isoformat(timespec='seconds')} "
                    f"quick_validation={report.get('status')} "
                    f"pass={summary.get('pass_count', 0)} "
                    f"fail={summary.get('fail_count', 0)} "
                    f"warn={summary.get('warning_count', 0)}"
                )
            except Exception as exc:
                print(f"{datetime.now().isoformat(timespec='seconds')} quick_validation=ERROR {exc}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("quick validation watch stopped")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

