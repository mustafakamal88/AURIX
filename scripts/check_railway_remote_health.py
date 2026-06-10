#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any
from typing import Optional


def request_json(base_url: str, path: str, api_key: Optional[str]) -> tuple[int, dict[str, Any]]:
    url = base_url.rstrip("/") + path
    headers = {}
    if api_key:
        headers["X-AURIX-API-Key"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{path} returned HTTP {exc.code}: {body}") from exc


def safety_false(value: Any) -> bool:
    return value is False or value is None


def main() -> int:
    parser = argparse.ArgumentParser(description="Check remote Railway AURIX bridge health.")
    parser.add_argument("--base-url", required=True, help="Railway public base URL, for example https://aurix-production.up.railway.app")
    parser.add_argument("--api-key", default=None, help="AURIX_API_KEY value")
    args = parser.parse_args()

    failures: list[str] = []

    try:
        _, healthz = request_json(args.base_url, "/healthz", args.api_key)
        _, summary = request_json(args.base_url, "/dashboard/runtime-summary", args.api_key)
        _, evidence = request_json(args.base_url, "/evidence-integrity/status", args.api_key)
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return 1

    runtime_env = summary.get("runtime_environment") or {}
    provenance = summary.get("runtime_provenance") or {}
    safety = summary.get("safety") or {}
    market = summary.get("market") or {}

    print(f"runtime_profile: {runtime_env.get('runtime_profile') or healthz.get('runtime_profile')}")
    print(f"health: {summary.get('health')}")
    print(f"symbol: {summary.get('symbol')}")
    print(f"runtime_session_id: {provenance.get('runtime_session_id') or healthz.get('runtime_session_id')}")
    print(f"mt5_snapshot_age_seconds: {market.get('snapshot_age_seconds')}")
    print(f"live_execution_enabled: {healthz.get('live_execution_enabled')}")
    print(f"demo_broker_execution_enabled: {healthz.get('demo_broker_execution_enabled')}")
    print(f"command_queue_enabled: {healthz.get('command_queue_enabled')}")
    print(f"live_execution_allowed: {safety.get('live_execution_allowed')}")
    print(f"demo_execution_allowed: {safety.get('demo_execution_allowed')}")
    print(f"command_queueing_allowed: {safety.get('demo_command_queueing_allowed') or safety.get('mt5_command_queueing_allowed')}")
    print(f"evidence_integrity_status: {evidence.get('status')}")

    if not args.api_key:
        failures.append("--api-key is required for remote Railway checks")
    if not safety_false(healthz.get("live_execution_enabled")) or not safety_false(safety.get("live_execution_allowed")):
        failures.append("live execution is not false")
    if not safety_false(healthz.get("demo_broker_execution_enabled")) or not safety_false(safety.get("demo_execution_allowed")):
        failures.append("demo broker execution is not false")
    if not safety_false(healthz.get("command_queue_enabled")):
        failures.append("command queue env flag is not false")
    if bool(safety.get("demo_command_queueing_allowed")) or bool(safety.get("mt5_command_queueing_allowed")):
        failures.append("runtime summary reports command queueing allowed")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("OK: Railway remote health check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
