#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


def request_json(base_url: str, path: str, *, method: str = "GET", api_key: str | None = None) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-AURIX-API-Key"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"
    data = b"{}" if method == "POST" else None
    request = urllib.request.Request(base_url.rstrip("/") + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    base_url = os.getenv("AURIX_BASE_URL", "http://127.0.0.1:8765")
    api_key = os.getenv("AURIX_API_KEY") or None
    try:
        report = request_json(base_url, "/quick-validation/run", method="POST", api_key=api_key)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: quick validation request failed: {exc}")
        return 1

    summary = report.get("summary") or {}
    safety = report.get("safety") or {}
    print(f"status: {report.get('status')}")
    print(f"pass_count: {summary.get('pass_count', 0)}")
    print(f"fail_count: {summary.get('fail_count', 0)}")
    print(f"warning_count: {summary.get('warning_count', 0)}")
    print(f"blocking_reasons: {report.get('blocking_reasons') or []}")
    print(f"safety: {safety}")
    print(f"recommendation: {(report.get('recommendations') or ['--'])[0]}")
    return 1 if report.get("status") == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())

