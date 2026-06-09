from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "aurix_dashboard"


FORBIDDEN_JS_REFERENCES = [
    "/commands/open-market",
    "/commands/close-position",
    "/commands/kill-switch",
    "/commands/cancel",
    "/daemon/start",
    "/daemon/stop",
    "/daemon/reset",
    "/orchestrator/start",
    "/orchestrator/stop",
    "/orchestrator/reset",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    files = [
        DASHBOARD / "index.html",
        DASHBOARD / "styles.css",
        DASHBOARD / "app.js",
    ]
    for file in files:
        require(file.exists(), f"missing dashboard file: {file}")

    index = (DASHBOARD / "index.html").read_text(encoding="utf-8")
    styles = (DASHBOARD / "styles.css").read_text(encoding="utf-8")
    app_js = (DASHBOARD / "app.js").read_text(encoding="utf-8")
    combined = f"{index}\n{styles}\n{app_js}"

    for label in ["LIVE TRADING DISABLED", "PAPER MODE ONLY", "NO MT5 COMMAND QUEUEING FROM DASHBOARD"]:
        require(label in index, f"missing safety label: {label}")

    for forbidden in FORBIDDEN_JS_REFERENCES:
        require(forbidden not in app_js, f"dashboard JS references forbidden endpoint: {forbidden}")

    require("fetch(" in app_js, "dashboard JS should fetch read-only API data")
    require("method: \"GET\"" in app_js, "dashboard fetch calls must use GET")
    require("<button" not in index.lower(), "dashboard must not include action buttons")
    require("read-only" in combined.lower(), "dashboard should identify itself as read-only")

    sys.path.insert(0, str(ROOT))
    import aurix_bridge_server.main as main_module

    routes = {getattr(route, "path", "") for route in main_module.app.routes}
    require("/dashboard" in routes, "FastAPI /dashboard route missing")
    require("/dashboard/" in routes, "FastAPI /dashboard/ route missing")

    print("OK: dashboard self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
