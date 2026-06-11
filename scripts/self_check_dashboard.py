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


def strategy_eval(strategy_name: str = "fast_rsi_first_reversal", status: str = "NO_SIGNAL", *, confidence: float = 0.0, direction: str | None = None, rejection_code: str = "no_fast_rsi_first_reversal_setup") -> dict[str, object]:
    return {
        "generated_at": iso_age(1),
        "agent_id": f"{strategy_name}_v1",
        "strategy_name": strategy_name,
        "strategy_version": "1.0.0",
        "symbol": "XAUUSDm",
        "status": status,
        "direction": direction,
        "confidence": confidence,
        "decision_trace": {"timeframe": "M1", "rsi_current": 42.0, "rsi_sma_current": 44.0, "evaluated_bar_time": iso_age(1), "rule_checks": {"enough_candles": True}},
        "rejection_reasons": [{"code": rejection_code, "message": rejection_code}],
    }


def seed_runtime(
    root: Path,
    *,
    snapshot_age: int = 1,
    broker_execution: bool = True,
    ea_execution: bool = True,
    spread_points: float = 20.0,
    evaluations: list[dict[str, object]] | None = None,
    registered_count: int = 1,
    enabled_count: int = 1,
) -> None:
    write_json(root, "latest_snapshot.json", snapshot(snapshot_age, broker_execution=ea_execution, spread_points=spread_points))
    write_json(root, "event_bus/status.json", {"updated_at": iso_age(1), "event_count": 1, "last_sequence": 1, "last_event_type": "AURIX_DECISION_EVENT"})
    write_json(root, "event_bus/state_snapshot.json", {"generated_at": iso_age(1)})
    write_jsonl(
        root,
        "event_bus/events.jsonl",
        [
            {"event_type": "AURIX_DECISION_EVENT", "event_id": "evt-1", "payload": {"action": "WAIT"}},
            {"event_type": "strategy_signal_rejected", "event_id": "evt-2", "payload": {"diagnostic_event": "strategy_signal_rejected"}},
        ],
    )
    write_json(root, "decision_engine/status.json", {"latest_action": "WAIT", "latest_status": "WAITING", "top_blocking_reason": "no actionable signal", "updated_at": iso_age(1)})
    write_json(root, "decision_engine/report.json", {"action": "WAIT", "generated_at": iso_age(1), "blocking_reasons": [{"message": "no actionable signal"}], "warnings": []})
    evaluations = evaluations if evaluations is not None else [{"strategy_name": "xauusd_paper_v2", "status": "NO_SIGNAL", "direction": None, "generated_at": iso_age(1), "confidence": 0.0}]
    write_json(root, "strategy_agents/status.json", {"registered_count": registered_count, "enabled_count": enabled_count, "latest_signal": next((item for item in evaluations if item.get("status") == "SIGNAL"), None)})
    write_json(root, "strategy_agents/latest_evaluations.json", evaluations)
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
    write_json(root, "trade_explanations/index.json", [])
    write_json(root, "durable_audit/status.json", {"durable_audit": "DISABLED", "database_connected": False})


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
    for section in ["Execution Control State", "AURIX Gates", "Validation / Readiness", "Quick Validation", "Latest Trade Explanation", "Durable Audit"]:
        require(section in index, f"missing cockpit section: {section}")
    require("No trade explanation recorded yet." in index and "No trade explanation recorded yet." in app_js, "dashboard missing empty trade explanation copy")
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
        "pipelineMarketFresh",
        "pipelineDecisionAlive",
        "pipelineRegistryLoaded",
        "pipelineRegistered",
        "pipelineEnabled",
        "pipelineEvaluations",
        "pipelineLastResult",
        "pipelineLastRejection",
        "strategyAgentsLatestResult",
        "strategyAgentsLatestRejection",
        "fastRsiLatestResult",
        "fastRsiLatestRejection",
        "runtimeHealthReason",
        "hdrRuntimeSafety",
        "hdrTradingSession",
        "runtimeTradingSession",
        "whySignalGate",
        "whyQueue",
        "tradeExplanationOrderId",
        "tradeExplanationStrategy",
        "tradeExplanationDirection",
        "tradeExplanationEntry",
        "tradeExplanationSl",
        "tradeExplanationTp",
        "tradeExplanationReason",
        "tradeExplanationConfidence",
        "tradeExplanationComponents",
        "tradeExplanationResult",
        "durableAuditState",
        "durableAuditConnected",
        "durableAuditLastWrite",
        "durableAuditLastError",
        "durableAuditExplanationId",
        "durableAuditCommandId",
        "durableAuditMt5OrderId",
        "durableAuditTradeResult",
    ]
    for field in required_fields:
        require(f'id="{field}"' in index or f"text(\"{field}\"" in app_js, f"missing dashboard field: {field}")

    require('id="hdrHealthReason"' not in index, "header must not render long health reason in topbar")
    require("Runtime Health Detail" in index, "dashboard should show health reason in a dedicated detail row")
    require(".runtime-health-detail" in styles and "overflow-wrap: anywhere" in styles, "health detail should wrap normally")

    sys.path.insert(0, str(ROOT))
    import aurix_bridge_server.main as main_module
    main_py = (ROOT / "aurix_bridge_server" / "main.py").read_text(encoding="utf-8")
    require("run_runtime_diagnostics_cycle(\"mt5_snapshot\")" in main_py, "MT5 snapshot path must run strategy diagnostics cycle")
    require("strategy_agent_evaluator.evaluate_all_agents()" in main_py, "runtime diagnostics cycle must evaluate strategy agents")
    require("decision_engine.evaluate()" in main_py, "runtime diagnostics cycle must evaluate advisory decision engine")

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
        seed_runtime(temp_root, snapshot_age=1, broker_execution=True, ea_execution=True, evaluations=[])
        true_summary = build_runtime_dashboard_summary(temp_root, runtime_environment=runtime_env, runtime_provenance=runtime_provenance).model_dump(mode="json")
        cockpit = true_summary["broker_execution_cockpit"]
        pipeline = true_summary["strategy_pipeline"]
        broker_recon = true_summary["broker_reconciliation"]
        require(pipeline["latest_result"] == "STRATEGY_EVALUATION_MISSING", f"expected missing strategy evaluation, got {pipeline}")
        require(pipeline["latest_rejection_reason"] == "STRATEGY_NOT_RUNNING", f"expected strategy not running, got {pipeline}")
        require(broker_recon["status"] == "DIRTY" and broker_recon["latest_exists"] is True, f"EA execution true should generate DIRTY broker reconciliation: {broker_recon}")
        require(cockpit["broker_execution_matched"] is True, "broker execution true + EA true should match")
        require(cockpit["latest_primary_block"] == "no actionable signal", f"expected no actionable signal, got {cockpit}")
        require(cockpit["signal_gate_state"] == "BLOCKED", f"signal gate should be blocked, got {cockpit}")
        require(cockpit["broker_order_permission"] == "BLOCKED", f"broker order permission should be blocked, got {cockpit}")
        require(cockpit["broker_order_permission_reason"] == "no actionable signal", f"broker order reason should identify no signal, got {cockpit}")
        require(cockpit["aurix_queue_state"] == "BLOCKED" and cockpit["aurix_queue_reason"] == "signal gate blocked: no actionable signal", f"queue reason wrong: {cockpit}")
        require(cockpit["legacy_gate_status"] == "IGNORED / RETIRED", f"legacy gate should be retired, got {cockpit}")
        require(cockpit["dashboard_order_capability"] == "READ_ONLY / CANNOT_CREATE_COMMANDS", f"dashboard order capability wrong: {cockpit}")
        require(true_summary["demo_command_queue"]["mt5_delivery_state"] == "NO_COMMAND", "dashboard summary should not create an MT5 command")
        require(true_summary["latest_trade_explanation"] == {}, "empty trade explanation ledger should render as empty summary data")
        require(true_summary["durable_audit"]["durable_audit"] == "DISABLED", f"missing durable audit dashboard state: {true_summary['durable_audit']}")
        require(true_summary["health"] == "HEALTHY", f"fresh snapshot should be healthy, got {true_summary['health']} {true_summary.get('health_reason')}")
        require(true_summary["session"]["trading_session"]["name"] in {"ASIA", "LONDON", "NEW_YORK", "OFF_SESSION"}, f"trading session missing: {true_summary['session']}")

        seed_runtime(temp_root, snapshot_age=1, broker_execution=True, ea_execution=False, evaluations=[])
        write_json(temp_root, "broker_reconciliation/report.json", {"generated_at": iso_age(1200), "status": "UNKNOWN", "mismatches": [], "warnings": [], "broker_positions": [], "broker_orders": []})
        write_json(temp_root, "broker_reconciliation/status.json", {"latest_exists": True, "status": "CLEAN", "mismatch_count": 0, "warning_count": 0, "broker_position_count": 0, "broker_order_count": 0, "updated_at": iso_age(1200)})
        stale_recon_summary = build_runtime_dashboard_summary(temp_root, runtime_environment=runtime_env, runtime_provenance=runtime_provenance).model_dump(mode="json")
        require(stale_recon_summary["broker_reconciliation"]["status"] == "CLEAN", f"stale broker reconciliation should refresh from fresh snapshot: {stale_recon_summary['broker_reconciliation']}")
        refreshed_report = json.loads((temp_root / "broker_reconciliation" / "report.json").read_text(encoding="utf-8"))
        require(refreshed_report["status"] == "CLEAN" and refreshed_report["positions_count"] == 0 and refreshed_report["orders_count"] == 0, f"refreshed broker report wrong: {refreshed_report}")

        seed_runtime(temp_root, snapshot_age=999, broker_execution=True, ea_execution=False, evaluations=[])
        stale_snapshot_summary = build_runtime_dashboard_summary(temp_root, runtime_environment=runtime_env, runtime_provenance=runtime_provenance).model_dump(mode="json")
        require(stale_snapshot_summary["broker_reconciliation"]["status"] == "UNKNOWN", f"stale snapshot should generate UNKNOWN broker reconciliation: {stale_snapshot_summary['broker_reconciliation']}")

        seed_runtime(temp_root, snapshot_age=1, broker_execution=True, ea_execution=False, evaluations=[])
        write_json(temp_root, "broker_reconciliation/report.json", {"generated_at": iso_age(1), "status": "BLOCKED", "mismatches": [], "warnings": [], "broker_positions": [], "broker_orders": []})
        write_json(temp_root, "broker_reconciliation/status.json", {"latest_exists": True, "status": "BLOCKED", "mismatch_count": 0, "warning_count": 0, "broker_position_count": 0, "broker_order_count": 0, "updated_at": iso_age(1)})
        no_evidence_recon_summary = build_runtime_dashboard_summary(temp_root, runtime_environment=runtime_env, runtime_provenance=runtime_provenance).model_dump(mode="json")
        require(no_evidence_recon_summary["broker_reconciliation"]["status"] == "UNKNOWN", f"non-clean broker reconciliation without dirty evidence should be UNKNOWN: {no_evidence_recon_summary['broker_reconciliation']}")

        write_json(temp_root, "broker_reconciliation/report.json", {"generated_at": iso_age(1), "status": "BLOCKED", "mismatches": [{"code": "unexpected_position"}], "warnings": [], "broker_positions": [], "broker_orders": []})
        write_json(temp_root, "broker_reconciliation/status.json", {"latest_exists": True, "status": "BLOCKED", "mismatch_count": 1, "warning_count": 0, "broker_position_count": 0, "broker_order_count": 0, "updated_at": iso_age(1)})
        dirty_recon_summary = build_runtime_dashboard_summary(temp_root, runtime_environment=runtime_env, runtime_provenance=runtime_provenance).model_dump(mode="json")
        require(dirty_recon_summary["broker_reconciliation"]["status"] == "DIRTY", f"dirty broker reconciliation evidence should preserve status: {dirty_recon_summary['broker_reconciliation']}")

        seed_runtime(temp_root, evaluations=[], registered_count=1, enabled_count=0)
        disabled_summary = build_runtime_dashboard_summary(temp_root, runtime_environment=runtime_env, runtime_provenance=runtime_provenance).model_dump(mode="json")
        require(disabled_summary["strategy_pipeline"]["latest_result"] == "STRATEGY_DISABLED", f"disabled strategy state wrong: {disabled_summary['strategy_pipeline']}")
        require(disabled_summary["decision"]["action"] == "WAIT", f"disabled strategy should keep decision WAIT: {disabled_summary['decision']}")

        seed_runtime(temp_root, evaluations=[strategy_eval(rejection_code="no_fast_rsi_first_reversal_setup")])
        rejected_summary = build_runtime_dashboard_summary(temp_root, runtime_environment=runtime_env, runtime_provenance=runtime_provenance).model_dump(mode="json")
        require(rejected_summary["strategy_pipeline"]["latest_result"] == "NO_SETUP", f"rejected setup should be NO_SETUP: {rejected_summary['strategy_pipeline']}")
        require(rejected_summary["strategy_pipeline"]["latest_rejection_reason"] == "NO_TRACE_PATTERN", f"rejection reason should be visible: {rejected_summary['strategy_pipeline']}")
        require(rejected_summary["event_bus"]["event_count"] == 1, f"diagnostic event should increment event count in fixture: {rejected_summary['event_bus']}")

        seed_runtime(temp_root, evaluations=[strategy_eval(status="SIGNAL", confidence=0.4, direction="BUY", rejection_code="")])
        low_summary = build_runtime_dashboard_summary(temp_root, runtime_environment=runtime_env, runtime_provenance=runtime_provenance).model_dump(mode="json")
        require(low_summary["strategy_pipeline"]["latest_result"] == "LOW_CONFIDENCE", f"low confidence should be visible: {low_summary['strategy_pipeline']}")
        require(low_summary["strategy_pipeline"]["latest_confidence"] == 0.4, f"low confidence value missing: {low_summary['strategy_pipeline']}")

        seed_runtime(temp_root, evaluations=[strategy_eval(status="SKIPPED", rejection_code="insufficient_m1_candles_for_rsi")], registered_count=3, enabled_count=3)
        waiting_summary = build_runtime_dashboard_summary(temp_root, runtime_environment=runtime_env, runtime_provenance=runtime_provenance).model_dump(mode="json")
        require(waiting_summary["strategy_pipeline"]["strategy_registry_loaded"] is True, f"registry should stay loaded with insufficient data: {waiting_summary['strategy_pipeline']}")
        require(waiting_summary["strategy_pipeline"]["latest_result"] == "WAITING_FOR_DATA", f"insufficient data should be waiting: {waiting_summary['strategy_pipeline']}")
        require(waiting_summary["fast_rsi"]["latest_result"] == "WAITING_FOR_DATA", f"Fast RSI should show waiting: {waiting_summary['fast_rsi']}")

        seed_runtime(temp_root, broker_execution=False, ea_execution=False, evaluations=[strategy_eval(status="SIGNAL", confidence=0.9, direction="BUY", rejection_code="")])
        actionable_false = build_runtime_dashboard_summary(temp_root, runtime_environment={"broker_execution_enabled": False, "data_dir": temp_dir}, runtime_provenance=runtime_provenance).model_dump(mode="json")
        require(actionable_false["strategy_pipeline"]["latest_result"] == "ACTIONABLE", f"actionable signal should be visible: {actionable_false['strategy_pipeline']}")
        require(actionable_false["demo_command_queue"]["mt5_delivery_state"] == "NO_COMMAND", "actionable signal with broker execution false should not queue MT5 command")

        seed_runtime(temp_root, broker_execution=True, ea_execution=True, evaluations=[strategy_eval(status="SIGNAL", confidence=0.9, direction="BUY", rejection_code="")])
        actionable_true = build_runtime_dashboard_summary(temp_root, runtime_environment=runtime_env, runtime_provenance=runtime_provenance).model_dump(mode="json")
        require(actionable_true["strategy_pipeline"]["latest_result"] == "ACTIONABLE", f"actionable signal should be visible read-only: {actionable_true['strategy_pipeline']}")
        require(actionable_true["runtime_provenance"]["safety_assertion"]["overall_safe"] is True, "dashboard summary must remain read-only safe")

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
    require("id=\"deploymentCommit\"" in index, "dashboard must show deployment commit provenance")
    require("setProvenanceValue(\"runtimeSessionId\"" in app_js, "runtime session provenance should render unknown/legacy as warning")
    require("setProvenanceValue(\"deploymentCommit\"" in app_js, "deployment commit provenance should render unknown as warning")

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
