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
    "/strategy-agents/evaluate",
    "/decision-engine/evaluate",
    "/demo-oms/process-latest-signal",
    "/demo-command-queue/preview-latest",
    "/demo-command-queue/dry-run-latest",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    files = [
        DASHBOARD / "index.html",
        DASHBOARD / "styles.css",
        DASHBOARD / "app.js",
        ROOT / "scripts" / "stress_runtime_status_endpoints.py",
        ROOT / "scripts" / "check_runtime_provenance.py",
        ROOT / "scripts" / "check_evidence_integrity.py",
    ]
    for file in files:
        require(file.exists(), f"missing dashboard file: {file}")

    index = (DASHBOARD / "index.html").read_text(encoding="utf-8")
    styles = (DASHBOARD / "styles.css").read_text(encoding="utf-8")
    app_js = (DASHBOARD / "app.js").read_text(encoding="utf-8")
    combined = f"{index}\n{styles}\n{app_js}"

    for label in ["BROKER EXECUTION DISABLED", "EA EXECUTION DISABLED", "EXECUTION STATE", "READ-ONLY DASHBOARD", "NO COMMANDS FROM DASHBOARD"]:
        require(label in index, f"missing safety label: {label}")

    for forbidden in FORBIDDEN_JS_REFERENCES:
        require(forbidden not in app_js, f"dashboard JS references forbidden endpoint: {forbidden}")

    require("/dashboard/runtime-summary" in app_js, "dashboard JS must call runtime summary endpoint")
    require("/dashboard/session" in app_js, "dashboard JS must check dashboard session endpoint")
    require("/dashboard/logout" in app_js, "dashboard JS must support dashboard logout")
    require("fetch(" in app_js, "dashboard JS should fetch read-only API data")
    require("method: \"GET\"" in app_js, "dashboard fetch calls must use GET")
    require('method: "POST"' not in app_js.replace('method: "POST", credentials: "same-origin"', ""), "dashboard JS must not call POST endpoints except logout")
    require("dashboardLogout" in index, "dashboard must include logout control")
    require("api_key" not in app_js, "dashboard JS must not read api_key query parameters")
    require("X-AURIX-API-Key" not in app_js and "x-aurix-api-key" not in app_js.lower(), "dashboard JS must not handle API key headers")
    local_storage = "local" + "Storage"
    session_storage = "session" + "Storage"
    require(local_storage not in app_js, "dashboard must not store API keys in browser local storage")
    require(session_storage not in app_js, "dashboard must not store API keys in browser session storage")
    require("sk-" not in combined, "dashboard must not hardcode API keys")
    require("read-only" in combined.lower(), "dashboard should identify itself as read-only")
    for section in ["Execution Control State", "AURIX Gates", "Validation / Readiness", "Quick Validation"]:
        require(section in index, f"missing cockpit section: {section}")
    for css_class in [".state-ok", ".state-warn", ".state-danger", ".state-disabled", ".state-enabled", ".state-blocked"]:
        require(css_class in styles, f"missing state css class: {css_class}")
    require("Runtime summary failed" in app_js, "dashboard should handle missing data gracefully")
    stress = (ROOT / "scripts" / "stress_runtime_status_endpoints.py").read_text(encoding="utf-8")
    for endpoint in ["/event-bus/status", "/operator/status", "/operator/summary", "/dashboard/runtime-summary", "/evidence-integrity/status", "/demo-command-queue/status"]:
        require(endpoint in stress, f"stress script missing endpoint: {endpoint}")
    require("ThreadPoolExecutor" in stress, "stress script should call endpoints concurrently")

    required_fields = [
        "decisionAction",
        "decisionDirection",
        "decisionScore",
        "decisionConfidence",
        "decisionStrategy",
        "fastRsiStatus",
        "fastRsiRsi",
        "fastRsiSma",
        "brokerReconStatus",
        "brokerReconMismatches",
        "safetyLiveExecution",
        "safetyMt5Commands",
        "whyPrimary",
        "whyNext",
        "runtimeSessionId",
        "sessionPaperTrades",
        "sessionCommands",
        "runtimeSafetyAssertion",
        "evidenceIntegrityStatus",
        "evidenceCorruptJsonFiles",
        "cockpitRailwayExecution",
        "cockpitEaExecution",
        "cockpitExecutionMatch",
        "cockpitCommandState",
        "cockpitPrimaryBlock",
        "gateQueueState",
        "gateSpreadState",
        "gateRiskModel",
        "validationQuickStatus",
        "validationReadinessStatus",
    ]
    for field in required_fields:
        require(f'id="{field}"' in index or f"text(\"{field}\"" in app_js, f"missing dashboard field: {field}")

    sys.path.insert(0, str(ROOT))
    import aurix_bridge_server.main as main_module

    routes = {getattr(route, "path", "") for route in main_module.app.routes}
    require("/" in routes, "FastAPI root route missing")
    require("/api" in routes, "route index /api route missing")
    root_response = main_module.root()
    require(getattr(root_response, "status_code", None) in {302, 303}, "root route must redirect")
    require(root_response.headers.get("location") == "/dashboard", "root route must redirect to /dashboard")
    api_index = main_module.api_index()
    require(api_index.get("dashboard") == "/dashboard" and api_index.get("healthz") == "/healthz", "route index /api missing expected entries")
    require("/dashboard" in routes, "FastAPI /dashboard route missing")
    require("/dashboard/" in routes, "FastAPI /dashboard/ route missing")
    require("/dashboard/login" in routes, "dashboard login route missing")
    require("/dashboard/logout" in routes, "dashboard logout route missing")
    require("/dashboard/session" in routes, "dashboard session route missing")
    require("/dashboard/runtime-summary" in routes, "runtime summary endpoint missing")
    require("/evidence-integrity/status" in routes, "evidence integrity endpoint missing")

    from aurix_dashboard_runtime import build_runtime_dashboard_summary

    summary = build_runtime_dashboard_summary(ROOT / "data").model_dump(mode="json")
    safety = summary["safety"]
    require(safety["read_only_dashboard"] is True, "runtime summary is not marked read-only")
    require(safety["paper_trade_created"] is False, "paper trades must not be created")
    require(safety["order_request_creation_allowed"] is False, "order requests must not be created")
    require(safety["mt5_commands_queued"] is False, "MT5 commands must not be queued")
    require(safety["broker_order_created"] is False, "broker orders must not be created")
    require(safety["broker_order_modified"] is False, "broker orders must not be modified")
    require(safety["broker_order_closed"] is False, "broker orders must not be closed")
    require(summary.get("runtime_provenance"), "runtime summary missing runtime provenance")
    require(summary.get("evidence_integrity"), "runtime summary missing evidence integrity")
    require(summary.get("broker_execution_cockpit") is not None, "runtime summary missing broker execution cockpit")
    assertion = summary["runtime_provenance"].get("safety_assertion") or {}
    require(assertion.get("overall_safe") is True, "runtime provenance safety assertion is not safe")

    print("OK: dashboard self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
