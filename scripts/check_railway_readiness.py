#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
failures: list[str] = []


def ok(message: str) -> None:
    print(f"PASS: {message}")


def warn(message: str) -> None:
    print(f"WARN: {message}")


def fail(message: str) -> None:
    failures.append(message)
    print(f"FAIL: {message}")


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require_file(path: str) -> None:
    if (ROOT / path).exists():
        ok(f"{path} exists")
    else:
        fail(f"{path} missing")


def main() -> int:
    for path in [
        "railway.json",
        "Procfile",
        "runtime.txt",
        ".env.example",
        "docs/railway_cloud_bridge_setup.md",
        "docs/railway_mt5_hybrid_setup.md",
        "scripts/run_server.py",
        "scripts/check_railway_remote_health.py",
        "scripts/check_mt5_bridge_routes.py",
    ]:
        require_file(path)

    env_text = read(".env.example")
    for key in [
        "AURIX_RUNTIME_PROFILE",
        "AURIX_HOST",
        "AURIX_PORT",
        "AURIX_PUBLIC_BASE_URL",
        "AURIX_REQUIRE_API_KEY_FOR_REMOTE",
        "AURIX_API_KEY",
        "AURIX_DASHBOARD_PASSWORD",
        "AURIX_DASHBOARD_SESSION_SECRET",
        "AURIX_DASHBOARD_COOKIE_NAME",
        "AURIX_DASHBOARD_SESSION_TTL_SECONDS",
        "AURIX_DASHBOARD_READ_ONLY",
        "AURIX_BROKER_EXECUTION",
        "AURIX_DATA_DIR",
        "AURIX_LOG_DIR",
    ]:
        if key in env_text:
            ok(f".env.example includes {key}")
        else:
            fail(f".env.example missing {key}")

    run_server = read("scripts/run_server.py")
    if 'os.getenv("PORT")' in run_server and "RAILWAY_CLOUD_BRIDGE" in run_server:
        ok("server start reads Railway PORT")
    else:
        fail("server start does not read Railway PORT")

    main_py = read("aurix_bridge_server/main.py")
    main_lower = main_py.lower()
    if "AURIX_REQUIRE_API_KEY_FOR_REMOTE" in main_py and "x-aurix-api-key" in main_lower and "authorization" in main_lower:
        ok("API key requirement logic exists")
    else:
        fail("API key requirement logic missing")

    if '@app.get("/healthz")' in main_py:
        ok("/healthz endpoint exists")
    else:
        fail("/healthz endpoint missing")
    if '@app.get("/dashboard/login")' in main_py and '@app.post("/dashboard/logout")' in main_py and '@app.get("/dashboard/session")' in main_py:
        ok("dashboard session auth routes exist")
    else:
        fail("dashboard session auth routes missing")
    if '@app.post("/mt5/snapshot")' in main_py and '@app.get("/mt5/command")' in main_py:
        ok("EA-compatible MT5 bridge routes exist")
    else:
        fail("EA-compatible MT5 bridge routes missing")

    safety_expectations = {
        "AURIX_BROKER_EXECUTION=false": "broker execution false",
        "AURIX_DASHBOARD_READ_ONLY=true": "dashboard read-only true",
    }
    for needle, label in safety_expectations.items():
        if re.search(rf"^#?\s*{re.escape(needle)}\s*$", env_text, re.MULTILINE):
            ok(label)
        else:
            fail(f".env.example does not show {needle}")

    dashboard_js = read("aurix_dashboard/app.js")
    if "/dashboard/runtime-summary" in dashboard_js and not any(endpoint in dashboard_js for endpoint in ["/commands/open-market", "/decision-engine/evaluate", "/strategy-agents/evaluate", "/demo-command-queue/dry-run-latest"]):
        ok("dashboard remains read-only and polls runtime summary")
    else:
        fail("dashboard JavaScript contains unexpected execution/evaluation endpoint")

    railway = read("railway.json")
    if "python scripts/run_server.py" in railway:
        ok("Railway start command uses existing server runner")
    else:
        fail("Railway start command missing")

    if "/data" in env_text:
        ok("Railway /data volume variables documented")
    else:
        warn("Railway /data volume variables not found")

    print(f"SUMMARY: {len(failures)} fail")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
