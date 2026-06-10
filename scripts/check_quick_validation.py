#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


def request_json(base_url: str, path: str, api_key: str | None = None) -> dict[str, Any]:
    headers = {}
    if api_key:
        headers["X-AURIX-API-Key"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(base_url.rstrip("/") + path, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    base_url = os.getenv("AURIX_BASE_URL", "http://127.0.0.1:8765")
    api_key = os.getenv("AURIX_API_KEY") or None
    try:
        status = request_json(base_url, "/quick-validation/status", api_key)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: quick validation status request failed: {exc}")
        return 1
    print(json.dumps(status, indent=2))
    return 1 if status.get("status") == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())

