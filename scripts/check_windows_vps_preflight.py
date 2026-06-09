#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.getenv("AURIX_BASE_URL") or f"http://{os.getenv('AURIX_HOST', '127.0.0.1')}:{os.getenv('AURIX_PORT', '8765')}"


failures: list[str] = []
warnings: list[str] = []


def pass_line(message: str) -> None:
    print(f"PASS: {message}")


def warn_line(message: str) -> None:
    warnings.append(message)
    print(f"WARN: {message}")


def fail_line(message: str) -> None:
    failures.append(message)
    print(f"FAIL: {message}")


def require_path(path: Path, label: str) -> None:
    if path.exists():
        pass_line(f"{label} exists: {path}")
    else:
        fail_line(f"{label} missing: {path}")


def get_nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def endpoint_json(path: str) -> tuple[int | None, dict[str, Any] | None, str | None]:
    url = f"{BASE_URL}{path}"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            payload = response.read().decode("utf-8")
            return response.status, json.loads(payload), None
    except urllib.error.HTTPError as exc:
        return exc.code, None, str(exc)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return None, None, str(exc)


def main() -> int:
    version = sys.version_info
    if version >= (3, 9):
        pass_line(f"Python version acceptable: {sys.version.split()[0]}")
    else:
        fail_line(f"Python 3.9+ required, found {sys.version.split()[0]}")

    if PROJECT_ROOT.exists() and (PROJECT_ROOT / "scripts").exists():
        pass_line(f"project root detected: {PROJECT_ROOT}")
    else:
        fail_line(f"project root could not be detected from {__file__}")

    for folder in [
        "aurix_bridge_server",
        "aurix_dashboard",
        "aurix_dashboard_runtime",
        "aurix_common",
        "scripts",
    ]:
        require_path(PROJECT_ROOT / folder, f"folder {folder}")

    for file_name in [
        "aurix_dashboard/index.html",
        "aurix_dashboard/app.js",
        "aurix_dashboard/styles.css",
        "scripts/windows/start_aurix_server.ps1",
        "scripts/windows/stop_aurix_server.ps1",
        "scripts/windows/check_aurix_server.ps1",
        "scripts/windows/install_aurix_startup_task.ps1",
        "scripts/windows/uninstall_aurix_startup_task.ps1",
        ".env.example",
    ]:
        require_path(PROJECT_ROOT / file_name, f"file {file_name}")

    app_js = (PROJECT_ROOT / "aurix_dashboard/app.js").read_text(encoding="utf-8")
    forbidden_calls = [
        "fetch('/commands/open-market",
        'fetch("/commands/open-market',
        "fetch('/demo-command-queue/dry-run-latest",
        'fetch("/demo-command-queue/dry-run-latest',
        "fetch('/demo-command-queue/preview-latest",
        'fetch("/demo-command-queue/preview-latest',
        "fetch('/decision-engine/evaluate",
        'fetch("/decision-engine/evaluate',
        "fetch('/strategy-agents/evaluate",
        'fetch("/strategy-agents/evaluate',
    ]
    if any(call in app_js for call in forbidden_calls):
        fail_line("dashboard JavaScript contains forbidden execution/evaluation fetch calls")
    else:
        pass_line("dashboard JavaScript remains read-only")

    status, summary, error = endpoint_json("/dashboard/runtime-summary")
    if status is None:
        warn_line(f"server is not running or not reachable at {BASE_URL}: {error}")
        print("INFO: endpoint checks skipped because this is acceptable before manual server start.")
    elif status != 200 or summary is None:
        fail_line(f"/dashboard/runtime-summary returned {status}: {error}")
    else:
        pass_line("/dashboard/runtime-summary returned 200")
        if summary.get("runtime_provenance"):
            pass_line("runtime provenance present")
        else:
            fail_line("runtime provenance missing from runtime summary")
        if summary.get("evidence_integrity"):
            pass_line("evidence integrity present")
        else:
            fail_line("evidence integrity missing from runtime summary")
        safety = summary.get("safety") or {}
        if safety:
            pass_line("safety fields present")
        else:
            fail_line("safety fields missing from runtime summary")

        live_execution = bool(safety.get("live_execution_allowed"))
        demo_execution = bool(safety.get("demo_execution_allowed"))
        queueing = bool(safety.get("demo_command_queueing_allowed") or safety.get("mt5_command_queueing_allowed"))
        if live_execution:
            fail_line("live execution is enabled")
        else:
            pass_line("live execution is false")
        if demo_execution:
            fail_line("demo broker execution is enabled")
        else:
            pass_line("demo broker execution is false or absent/disabled")
        if queueing:
            fail_line("command queueing is enabled")
        else:
            pass_line("command queueing is false")

        assertion = get_nested(summary, "runtime_provenance", "safety_assertion") or {}
        unsafe_session = any(
            bool(assertion.get(key))
            for key in [
                "created_paper_trade",
                "created_order_request",
                "queued_mt5_command",
                "created_broker_order",
                "modified_broker_order",
                "closed_broker_order",
            ]
        )
        if unsafe_session:
            fail_line("current runtime session reports trade/order/command/broker action")
        else:
            pass_line("current runtime session reports no trade/order/command/broker action")

    print(f"SUMMARY: {len(failures)} fail, {len(warnings)} warn")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
