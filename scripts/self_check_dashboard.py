from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


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


def iso_age(seconds: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


def write_json(root: Path, relative_path: str, value: object) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def write_jsonl(root: Path, relative_path: str, rows: list[dict[str, object]]) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


def snapshot(age_seconds: int, *, broker_execution: bool = True, spread_points: float = 20.0) -> dict[str, object]:
    return {
        "terminal_id": "AURIX-VPS-001",
        "received_at": iso_age(age_seconds),
        "account": {"server": "Exness-MT5Trial15", "currency": "GBP", "balance": 1000.0, "equity": 1000.0, "is_demo": True},
        "tick": {"symbol": "XAUUSDm", "bid": 2300.0, "ask": 2300.2, "spread_points": spread_points, "time": iso_age(age_seconds)},
        "candles": [{"time": iso_age(age_seconds), "open": 1, "high": 2, "low": 1, "close": 2}],
        "positions": [],
        "orders": [],
        "raw": {"broker_execution_enabled": broker_execution},
    }


def seed_runtime(root: Path, *, snapshot_age: int = 1, broker_execution: bool = True, ea_execution: bool = True, spread_points: float = 20.0) -> None:
    write_json(root, "latest_snapshot.json", snapshot(snapshot_age, broker_execution=ea_execution, spread_points=spread_points))
    write_json(root, "event_bus/status.json", {"updated_at": iso_age(1), "event_count": 1, "last_sequence": 1, "last_event_type": "AURIX_DECISION_EVENT"})
    write_json(root, "event_bus/state_snapshot.json", {"generated_at": iso_age(1)})
    write_jsonl(root, "event_bus/events.jsonl", [{"event_type": "AURIX_DECISION_EVENT", "event_id": "evt-1", "payload": {"action": "WAIT"}}])
    write_json(root, "decision_engine/status.json", {"latest_action": "WAIT", "latest_status": "WAITING", "top_blocking_reason": "no actionable signal", "updated_at": iso_age(1)})
    write_json(root, "decision_engine/report.json", {"action": "WAIT", "generated_at": iso_age(1), "blocking_reasons": [{"message": "no actionable signal"}], "warnings": []})
    write_json(root, "strategy_agents/status.json", {"registered_count": 1, "enabled_count": 1, "latest_signal": {"status": "NO_SIGNAL", "direction": None}})
    write_json(root, "strategy_agents/latest_evaluations.json", [{"strategy_name": "xauusd_paper_v2", "status": "NO_SIGNAL", "direction": None}])
    write_json(root, "risk_status.json", {"config": {"max_spread_points": 270}})
    write_json(root, "demo_command_queue/status.json", {"mode": "READ_ONLY", "preview_count": 0, "payload_count": 0})
    write_json(root, "demo_oms/status.json", {"mode": "READ_ONLY", "order_intent_count": 0, "order_request_count": 0})
    write_json(root, "quick_validation_report.json", {"status": "NOT_RUN", "summary": {"pass_count": 0, "fail_count": 0, "warning_count": 0}, "safety": {"paper_only": True, "broker_execution_enabled": broker_execution, "mt5_commands_queued": False}})
    write_json(root, "paper_trades.json", [])
    write_json(root, "journal_entries.json", [])
    write_json(root, "commands.json", [])
    write_json(root, "execution_results.json", [])
    write_json(root, "demo_oms/order_requests.json", [])
    write_json(root, "demo_command_queue/payloads.json", [])


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
        "safetyBrokerOrderPermission",
        "safetyBrokerOrderReason",
        "safetyQueueReason",
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
        "hdrHealthReason",
        "hdrRuntimeSafety",
        "hdrTradingSession",
        "runtimeTradingSession",
        "whySignalGate",
        "whyQueue",
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
    from aurix_dashboard_runtime.summary import _dashboard_trading_session

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

    with tempfile.TemporaryDirectory(prefix="aurix-dashboard-self-check-") as temp_dir:
        temp_root = Path(temp_dir)
        runtime_env = {"broker_execution_enabled": True, "data_dir": temp_dir}
        runtime_provenance = {"generated_at": iso_age(1), "safety_assertion": {"overall_safe": True}, "runtime_session_id": "test"}
        seed_runtime(temp_root, snapshot_age=1, broker_execution=True, ea_execution=True)
        true_summary = build_runtime_dashboard_summary(temp_root, runtime_environment=runtime_env, runtime_provenance=runtime_provenance).model_dump(mode="json")
        cockpit = true_summary["broker_execution_cockpit"]
        require(cockpit["broker_execution_matched"] is True, "broker execution true + EA true should match")
        require(cockpit["latest_primary_block"] == "no actionable signal", f"expected no actionable signal, got {cockpit}")
        require(cockpit["signal_gate_state"] == "BLOCKED", f"signal gate should be blocked, got {cockpit}")
        require(cockpit["broker_order_permission"] == "BLOCKED", f"broker order permission should be blocked, got {cockpit}")
        require(cockpit["broker_order_permission_reason"] == "no actionable signal", f"broker order reason should identify no signal, got {cockpit}")
        require(cockpit["aurix_queue_state"] == "BLOCKED" and cockpit["aurix_queue_reason"] == "signal gate blocked: no actionable signal", f"queue reason wrong: {cockpit}")
        require(cockpit["legacy_gate_status"] == "IGNORED / RETIRED", f"legacy gate should be retired, got {cockpit}")
        require(cockpit["dashboard_order_capability"] == "READ_ONLY / CANNOT_CREATE_COMMANDS", f"dashboard order capability wrong: {cockpit}")
        require(true_summary["demo_command_queue"]["mt5_delivery_state"] == "NO_COMMAND", "dashboard summary should not create an MT5 command")
        require(true_summary["health"] == "HEALTHY", f"fresh snapshot should be healthy, got {true_summary['health']} {true_summary.get('health_reason')}")
        require(true_summary["session"]["trading_session"]["name"] in {"ASIA", "LONDON", "NEW_YORK", "OFF_SESSION"}, f"trading session missing: {true_summary['session']}")

        seed_runtime(temp_root, snapshot_age=1, broker_execution=True, ea_execution=True, spread_points=999.0)
        spread_summary = build_runtime_dashboard_summary(temp_root, runtime_environment=runtime_env, runtime_provenance=runtime_provenance).model_dump(mode="json")
        require(spread_summary["top_blocks"][0] == "no actionable signal", f"no signal should remain primary, got {spread_summary['top_blocks']}")
        require(
            spread_summary["top_blocks"][1] == "spread gate blocked: current spread 999.0 points > max spread 270 points",
            f"spread block should be secondary with current/max spread, got {spread_summary['top_blocks']}",
        )

        false_summary = build_runtime_dashboard_summary(temp_root, runtime_environment={"broker_execution_enabled": False, "data_dir": temp_dir}, runtime_provenance=runtime_provenance).model_dump(mode="json")
        require(false_summary["health"] == "HEALTHY", "broker execution false must not make readiness collection unhealthy")
        require(false_summary["quick_validation"]["safety"]["paper_only"] is True, "paper/backtest readiness should remain available when broker execution is false")
        require(false_summary["demo_command_queue"]["mt5_delivery_state"] == "NO_COMMAND", "broker execution false should not create MT5 command")

        seed_runtime(temp_root, snapshot_age=999, broker_execution=True, ea_execution=True)
        stale_summary = build_runtime_dashboard_summary(temp_root, runtime_environment=runtime_env, runtime_provenance=runtime_provenance).model_dump(mode="json")
        require(stale_summary["health"] == "STALE", f"stale snapshot should be stale, got {stale_summary['health']}")
        require("MT5 snapshot stale" in stale_summary["health_reason"], f"stale health reason missing snapshot detail: {stale_summary['health_reason']}")

        london = ZoneInfo("Europe/London")
        expected_sessions = [
            (datetime(2026, 1, 5, 1, 0, tzinfo=london), "ASIA"),
            (datetime(2026, 1, 5, 8, 0, tzinfo=london), "LONDON"),
            (datetime(2026, 1, 5, 15, 0, tzinfo=london), "NEW_YORK"),
            (datetime(2026, 1, 5, 22, 0, tzinfo=london), "OFF_SESSION"),
        ]
        for dt, expected in expected_sessions:
            actual = _dashboard_trading_session(dt)["name"]
            require(actual == expected, f"trading session for {dt.isoformat()} should be {expected}, got {actual}")

    require("Broker Execution</span><span class=\"rt-value\" id=\"safetyLiveExecution\"" not in index, "safety locks must not show contradictory Broker Execution row")
    require("Safety State" not in index, "decision strip should use Runtime Safety wording")
    require("Overall Session Safe" not in index, "runtime safety wording should not say Overall Session Safe")

    import aurix_demo_broker_execution.store as broker_store_module

    original_create_command = broker_store_module.DemoBrokerExecutionStore.create_command
    try:
        def fail_create_command(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("dashboard read-only path must not create commands")

        broker_store_module.DemoBrokerExecutionStore.create_command = fail_create_command  # type: ignore[method-assign]
        _ = build_runtime_dashboard_summary(ROOT / "data")
    finally:
        broker_store_module.DemoBrokerExecutionStore.create_command = original_create_command  # type: ignore[method-assign]

    print("OK: dashboard self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
