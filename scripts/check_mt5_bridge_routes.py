#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def print_pass(message: str) -> None:
    print(f"PASS: {message}")


def print_fail(message: str) -> None:
    print(f"FAIL: {message}")


def app_has_route(path: str, method: str) -> bool:
    with tempfile.TemporaryDirectory(prefix="aurix-mt5-route-check-") as temp_dir:
        os.environ.setdefault("AURIX_RUNTIME_PROFILE", "LOCAL_DEV")
        os.environ["AURIX_DATA_DIR"] = temp_dir
        from aurix_bridge_server.main import app

        for route in app.routes:
            if getattr(route, "path", None) == path and method.upper() in getattr(route, "methods", set()):
                return True
    return False


def request_json(
    base_url: str,
    path: str,
    method: str = "GET",
    api_key: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
) -> tuple[int, dict[str, Any]]:
    data = None
    headers = {}
    if api_key:
        headers["X-AURIX-API-Key"] = api_key
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(base_url.rstrip("/") + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Check EA-compatible MT5 bridge routes.")
    parser.add_argument("--base-url", help="Optional running server base URL to probe")
    parser.add_argument("--api-key", help="Optional AURIX API key for remote/server probes")
    args = parser.parse_args()

    failures: list[str] = []
    required = [
        ("/healthz", "GET"),
        ("/mt5/snapshot", "POST"),
        ("/mt5/command", "GET"),
    ]
    for path, method in required:
        if app_has_route(path, method):
            print_pass(f"{method} {path} is registered")
        else:
            failures.append(f"{method} {path} is not registered")
            print_fail(f"{method} {path} is not registered")

    if args.base_url:
        snapshot = {
            "terminal_id": "AURIX-ROUTE-CHECK",
            "symbol": "XAUUSDm",
            "balance": 100.0,
            "equity": 100.0,
            "free_margin": 100.0,
            "bid": 2300.0,
            "ask": 2300.2,
            "spread_points": 20,
            "positions": [],
            "orders": [],
            "raw": {"route_check": True},
        }
        try:
            status, health = request_json(args.base_url, "/healthz", api_key=args.api_key)
            print_pass(f"GET /healthz returned {status}: {health.get('status')}")
            status, snapshot_response = request_json(args.base_url, "/mt5/snapshot", method="POST", api_key=args.api_key, payload=snapshot)
            print_pass(f"POST /mt5/snapshot returned {status}: {snapshot_response.get('status')}")
            status, command_response = request_json(args.base_url, "/mt5/command?terminal_id=AURIX-ROUTE-CHECK", api_key=args.api_key)
            print_pass(f"GET /mt5/command returned {status}: {command_response.get('status')}")
            if command_response.get("command") is not None or command_response.get("status") != "NO_COMMAND":
                failures.append("GET /mt5/command did not return safe NO_COMMAND response")
                print_fail("GET /mt5/command did not return safe NO_COMMAND response")
        except urllib.error.HTTPError as exc:
            failures.append(f"HTTP probe failed with {exc.code}")
            print_fail(f"HTTP probe failed with {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
        except Exception as exc:
            failures.append(f"HTTP probe failed: {exc}")
            print_fail(f"HTTP probe failed: {exc}")

    print(f"SUMMARY: {len(failures)} fail")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
