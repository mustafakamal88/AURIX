from __future__ import annotations

import asyncio
import os
import json
import logging
from urllib.parse import parse_qs
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Optional
from uuid import NAMESPACE_URL, uuid4, uuid5

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from aurix_common import RuntimeSession
from aurix_ai_review import AIReviewStore, AIReviewTemplateReviewer, load_ai_review_config
from aurix_analytics import PaperPerformanceStore, generate_paper_performance_report
from aurix_analytics.performance import summary_from_report
from aurix_backtest import BacktestReplayEngine, BacktestStore, XauusdPaperV2BacktestReplayEngine, load_backtest_config
from aurix_broker_reconciliation import BrokerReconciler, load_broker_reconciliation_config
from aurix_context_engine import ContextEngine, load_context_config
from aurix_daemon import DaemonConfig, PaperDaemonRunner, load_daemon_config
from aurix_demo_command_queue import DemoCommandQueueAdapter, load_demo_command_queue_config
from aurix_demo_broker_execution import DemoBrokerExecutionGate, DemoBrokerExecutionStore, load_demo_broker_execution_config
from aurix_demo_broker_execution.account import verify_demo_account
from aurix_demo_oms import DemoOms, load_demo_oms_config
from aurix_decision_engine import AurixDecisionEngine, load_decision_engine_config
from aurix_dashboard_runtime import build_runtime_dashboard_summary
from aurix_dashboard_runtime.evidence_integrity import build_evidence_integrity_status
from aurix_evidence_monitor import EvidenceMonitorStore, load_evidence_monitor_config
from aurix_evidence_gate import EvidenceGateStore, load_evidence_gate_config
from aurix_event_bus import AurixEventBus, EVENT_TYPES, collect_observation_events, load_event_bus_config
from aurix_event_bus.models import AurixEvent, AurixEventType, EventSafety
from aurix_forward_test import ForwardTestStore, load_forward_test_config
from aurix_journal import JournalReviewer, JournalStore, load_journal_config
from aurix_long_run import LongForwardTestManager, load_long_forward_test_config
from aurix_live_readiness import LiveReadinessStore, load_live_readiness_config
from aurix_market_data import MarketDataRecorder, load_market_data_config
from aurix_operator import build_operator_summary, build_operator_status
from aurix_orchestrator import SessionOrchestrator, load_orchestrator_config
from aurix_paper_trading import PaperLedger, PaperTradingEngine, load_paper_trading_config
from aurix_paper_risk_audit import PaperRiskAuditStore, load_paper_risk_audit_config
from aurix_persistence import DurableAuditError, DurableAuditStore
from aurix_quick_validation import QuickValidationRunner, QuickValidationStore
from aurix_research import ResearchStore, load_research_config
from aurix_risk_governor import RiskGovernor, load_risk_config
from aurix_risk_governor.checks import as_dict, as_float, as_list
from aurix_signal_certifier import SignalCertifierStore, load_signal_certifier_config
from aurix_strategy_agents import StrategyAgentEvaluator, StrategyAgentRegistry, load_strategy_agent_config
from aurix_supervisor import PaperSupervisor, load_supervisor_config
from aurix_strategy_engine import StrategyEngine, load_strategy_config
from aurix_strategy_engine.xauusd_paper_v1 import evaluate_xauusd_paper_v1, load_xauusd_paper_v1_config
from aurix_strategy_engine.xauusd_paper_v2 import evaluate_xauusd_paper_v2, load_xauusd_paper_v2_config
from aurix_trade_explanations import TradeExplanationStore, build_trade_explanation

from .command_codec import encode_command_for_mql5
from .dashboard_auth import (
    DashboardAuthConfig,
    build_clear_cookie_header,
    build_cookie_header,
    create_session_token,
    verify_dashboard_password,
    verify_session_token,
)
from .models import Command, ExecutionResult, utc_now_iso
from .store import JsonStore

load_dotenv()

RUNTIME_PROFILE = os.getenv("AURIX_RUNTIME_PROFILE", "LOCAL_DEV").upper()
DATA_DIR = os.getenv("AURIX_DATA_DIR", "data")
LOG_DIR = os.getenv("AURIX_LOG_DIR", "logs")
PUBLIC_BASE_URL = os.getenv("AURIX_PUBLIC_BASE_URL", "")
DEFAULT_TERMINAL_ID = os.getenv("AURIX_TERMINAL_ID", "AURIX-MAC-001")
REQUIRE_API_KEY_FOR_REMOTE = os.getenv("AURIX_REQUIRE_API_KEY_FOR_REMOTE", "false").lower() in {"1", "true", "yes"}
API_KEY = os.getenv("AURIX_API_KEY", "")
DASHBOARD_READ_ONLY = os.getenv("AURIX_DASHBOARD_READ_ONLY", "true").lower() in {"1", "true", "yes"}
DASHBOARD_DIR = Path(__file__).resolve().parents[1] / "aurix_dashboard"
dashboard_auth_config = DashboardAuthConfig.from_env()
RAILWAY_VOLUME_DETECTED = Path(DATA_DIR).is_mount() if Path(DATA_DIR).exists() else False

store = JsonStore(DATA_DIR)
logger = logging.getLogger("aurix.runtime")
risk_config = load_risk_config()
risk_governor = RiskGovernor(risk_config)
strategy_config = load_strategy_config()
strategy_engine = StrategyEngine(strategy_config)
xauusd_paper_v1_config = load_xauusd_paper_v1_config()
xauusd_paper_v2_config = load_xauusd_paper_v2_config()
paper_config = load_paper_trading_config()
paper_ledger = PaperLedger(DATA_DIR)
paper_engine = PaperTradingEngine(paper_config, risk_config)
paper_risk_audit_config = load_paper_risk_audit_config()
paper_risk_audit_store = PaperRiskAuditStore(DATA_DIR, paper_risk_audit_config)
market_config = load_market_data_config()
market_recorder = MarketDataRecorder(DATA_DIR, market_config)
context_config = load_context_config()
context_engine = ContextEngine(DATA_DIR, context_config)
supervisor_config = load_supervisor_config()
paper_supervisor = PaperSupervisor(
    data_dir=DATA_DIR,
    config=supervisor_config,
    store=store,
    market_recorder=market_recorder,
    context_engine=context_engine,
    xauusd_paper_v1_config=xauusd_paper_v1_config,
    paper_engine=paper_engine,
    paper_ledger=paper_ledger,
    market_config=market_config,
    paper_risk_audit_store=paper_risk_audit_store,
)
performance_store = PaperPerformanceStore(DATA_DIR)
journal_config = load_journal_config()
journal_store = JournalStore(DATA_DIR, journal_config)
journal_reviewer = JournalReviewer(journal_config)
ai_review_config = load_ai_review_config()
ai_review_store = AIReviewStore(DATA_DIR, ai_review_config)
ai_review_reviewer = AIReviewTemplateReviewer(ai_review_config)
backtest_config = load_backtest_config()
backtest_store = BacktestStore(DATA_DIR, backtest_config)
backtest_engine = BacktestReplayEngine(backtest_config)
backtest_v2_store = BacktestStore(DATA_DIR, backtest_config, suffix="_v2")
backtest_v2_engine = XauusdPaperV2BacktestReplayEngine(xauusd_paper_v2_config)
research_config = load_research_config()
research_store = ResearchStore(DATA_DIR, research_config)
evidence_gate_config = load_evidence_gate_config()
evidence_gate_store = EvidenceGateStore(DATA_DIR, evidence_gate_config)
daemon_config = load_daemon_config()
daemon_runner: PaperDaemonRunner
daemon_task: asyncio.Task[Any] | None = None
forward_test_config = load_forward_test_config()
forward_test_store = ForwardTestStore(DATA_DIR, forward_test_config)
orchestrator_config = load_orchestrator_config()
orchestrator: SessionOrchestrator
orchestrator_task: asyncio.Task[Any] | None = None
long_forward_config = load_long_forward_test_config()
long_forward_manager: LongForwardTestManager
long_forward_task: asyncio.Task[Any] | None = None
live_readiness_config = load_live_readiness_config()
live_readiness_store = LiveReadinessStore(DATA_DIR, live_readiness_config)
evidence_monitor_config = load_evidence_monitor_config()
evidence_monitor_store = EvidenceMonitorStore(DATA_DIR, evidence_monitor_config)
signal_certifier_config = load_signal_certifier_config()
signal_certifier_store = SignalCertifierStore(DATA_DIR, signal_certifier_config)
decision_engine_config = load_decision_engine_config()
runtime_session = RuntimeSession(
    data_dir=DATA_DIR,
    mode=decision_engine_config.mode,
    symbol=decision_engine_config.symbol,
)
event_bus_config = load_event_bus_config()
event_bus = AurixEventBus(DATA_DIR, event_bus_config, runtime_session_id=runtime_session.runtime_session_id)
strategy_agents_config = load_strategy_agent_config()
strategy_agent_registry = StrategyAgentRegistry(strategy_agents_config, DATA_DIR)
strategy_agent_evaluator = StrategyAgentEvaluator(
    data_dir=DATA_DIR,
    config=strategy_agents_config,
    registry=strategy_agent_registry,
    event_bus=event_bus,
    latest_signals=store.list_strategy_signals,
    candles=market_recorder.list_candles,
    context=context_engine.latest,
)
demo_oms_config = load_demo_oms_config()
demo_oms = DemoOms(DATA_DIR, demo_oms_config, event_bus=event_bus, snapshot_provider=store.latest_snapshot)
broker_reconciliation_config = load_broker_reconciliation_config()
broker_reconciler = BrokerReconciler(
    DATA_DIR,
    broker_reconciliation_config,
    event_bus=event_bus,
    snapshot_provider=store.latest_snapshot,
    demo_oms_store=demo_oms.store,
)
demo_command_queue_config = load_demo_command_queue_config()
demo_command_queue = DemoCommandQueueAdapter(
    DATA_DIR,
    demo_command_queue_config,
    event_bus=event_bus,
    snapshot_provider=store.latest_snapshot,
    demo_oms_store=demo_oms.store,
    broker_reconciliation_store=broker_reconciler.store,
)
demo_broker_execution_config = load_demo_broker_execution_config()
demo_broker_execution_store = DemoBrokerExecutionStore(DATA_DIR)
demo_broker_execution_gate = DemoBrokerExecutionGate(demo_broker_execution_config, demo_broker_execution_store)
quick_validation_store = QuickValidationStore(DATA_DIR)
decision_engine = AurixDecisionEngine(
    DATA_DIR,
    decision_engine_config,
    event_bus=event_bus,
    snapshot_provider=store.latest_snapshot,
    strategy_agent_store=strategy_agent_evaluator.store,
    demo_oms_store=demo_oms.store,
    broker_reconciliation_store=broker_reconciler.store,
    demo_command_queue_store=demo_command_queue.store,
    risk_status_provider=lambda: risk_status(),
)


def build_durable_audit_store() -> DurableAuditStore:
    database_url = os.getenv("DATABASE_URL")
    sqlite_path = os.getenv("AURIX_DURABLE_AUDIT_SQLITE_PATH")
    if not database_url and RUNTIME_PROFILE == "LOCAL_DEV":
        return DurableAuditStore.sqlite_local(
            DATA_DIR,
            path=sqlite_path or Path(DATA_DIR) / "aurix_durable_audit.sqlite",
            runtime_session_id=runtime_session.runtime_session_id,
        )
    return DurableAuditStore(DATA_DIR, runtime_session_id=runtime_session.runtime_session_id)


durable_audit_store = build_durable_audit_store()
trade_explanation_store = TradeExplanationStore(DATA_DIR)


def runtime_provenance_metadata(component: str, source: str) -> dict[str, Any]:
    return {
        "runtime_session_id": runtime_session.runtime_session_id,
        "component": component,
        "created_at": utc_now_iso(),
        "source_module": source,
        "safety_mode": runtime_session.mode,
        "live_enabled": False,
        "command_queue_enabled": False,
    }


def mirror_historical_trade_explanation_to_db() -> None:
    if not durable_audit_store.database_url:
        return
    path = Path(DATA_DIR) / "trade_explanations" / "1765078137.json"
    if not path.exists():
        return
    try:
        explanation = json.loads(path.read_text(encoding="utf-8"))
        durable_audit_store.write_trade_explanation(explanation, explanation_id=str(uuid5(NAMESPACE_URL, "aurix-historical-trade-1765078137")))
    except Exception as exc:
        logger.warning("durable audit historical mirror failed: %s", exc)


demo_oms.provenance_provider = runtime_provenance_metadata
demo_command_queue.provenance_provider = runtime_provenance_metadata
mirror_historical_trade_explanation_to_db()

app = FastAPI(
    title="AURIX Mac/Wine MT5 Bridge",
    version="0.1.0",
    description="Mac/Wine-safe MT5 bridge using an MQL5 EA + Python API.",
)
app.mount("/dashboard/static", StaticFiles(directory=DASHBOARD_DIR), name="dashboard-static")


def _remote_auth_required() -> bool:
    if RUNTIME_PROFILE == "LOCAL_DEV":
        return False
    return REQUIRE_API_KEY_FOR_REMOTE or RUNTIME_PROFILE == "RAILWAY_CLOUD_BRIDGE"


def _extract_api_key(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return request.headers.get("x-aurix-api-key", "")


def _request_is_https(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    return request.url.scheme == "https" or forwarded_proto.split(",", 1)[0].strip().lower() == "https"


def _has_valid_api_key(request: Request) -> bool:
    return bool(API_KEY) and hmac_compare(_extract_api_key(request), API_KEY)


def hmac_compare(left: str, right: str) -> bool:
    import hmac

    return hmac.compare_digest(left or "", right or "")


def _has_valid_dashboard_session(request: Request) -> bool:
    token = request.cookies.get(dashboard_auth_config.cookie_name)
    return verify_session_token(token, dashboard_auth_config)


def _dashboard_auth_configured() -> bool:
    return dashboard_auth_config.configured


def _dashboard_auth_required() -> bool:
    return _remote_auth_required() or _dashboard_auth_configured()


def _is_dashboard_path(path: str) -> bool:
    return path in {"/dashboard", "/dashboard/"} or path.startswith("/dashboard/static") or path in {"/dashboard/runtime-summary", "/dashboard/session"}


def _login_redirect() -> RedirectResponse:
    return RedirectResponse("/dashboard/login", status_code=303)


def _dashboard_auth_ok(request: Request) -> bool:
    return _has_valid_api_key(request) or _has_valid_dashboard_session(request)


def _auth_error_detail() -> str:
    if not API_KEY:
        return "AURIX_API_KEY is required for remote profile; remote access is closed."
    return "Missing or invalid AURIX API key."


def runtime_environment_payload() -> dict[str, Any]:
    return {
        "runtime_profile": RUNTIME_PROFILE,
        "public_base_url": PUBLIC_BASE_URL,
        "remote_auth_required": _remote_auth_required(),
        "api_key_configured": bool(API_KEY),
        "dashboard_auth_configured": _dashboard_auth_configured(),
        "data_dir": DATA_DIR,
        "log_dir": LOG_DIR,
        "railway_volume_detected": RAILWAY_VOLUME_DETECTED if RUNTIME_PROFILE == "RAILWAY_CLOUD_BRIDGE" else "unknown",
        "mt5_terminal_id": DEFAULT_TERMINAL_ID,
        "dashboard_read_only": DASHBOARD_READ_ONLY,
        "broker_execution_enabled": demo_broker_execution_config.broker_execution_enabled,
    }


@app.middleware("http")
async def require_remote_api_key(request: Request, call_next: Any) -> Any:
    path = request.url.path
    if path in {"/healthz", "/dashboard/login", "/dashboard/logout"}:
        return await call_next(request)
    if path == "/" and request.method == "GET":
        return await call_next(request)
    if _is_dashboard_path(path):
        if not _dashboard_auth_required():
            return await call_next(request)
        if _dashboard_auth_ok(request):
            return await call_next(request)
        if path in {"/dashboard", "/dashboard/"} or path.startswith("/dashboard/static"):
            return _login_redirect()
        return JSONResponse(status_code=401, content={"ok": False, "error": "Dashboard session required."})
    if not _remote_auth_required():
        return await call_next(request)
    if _has_valid_dashboard_session(request):
        return await call_next(request)
    if not API_KEY:
        return JSONResponse(status_code=503, content={"ok": False, "error": _auth_error_detail()})
    if not _has_valid_api_key(request):
        return JSONResponse(status_code=401, content={"ok": False, "error": _auth_error_detail()})
    return await call_next(request)


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse("/dashboard", status_code=303)


@app.get("/api")
def api_index() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "aurix-mac-wine-bridge",
        "name": "AURIX",
        "docs": "/docs",
        "api": "/api",
        "dashboard": "/dashboard",
        "dashboard_login": "/dashboard/login",
        "health": "/health",
        "healthz": "/healthz",
        "latest_state": "/state/latest",
        "risk_status": "/risk/status",
        "results": "/results",
        "execution_results": "/execution/results",
        "strategy_status": "/strategy/status",
        "xauusd_paper_v1": "/strategy/evaluate-paper-v1",
        "xauusd_paper_v2": "/strategy/evaluate-paper-v2",
        "paper_status": "/paper/status",
        "paper_risk_audit_status": "/paper-risk-audit/status",
        "market_status": "/market/status",
        "context_status": "/context/status",
        "supervisor_status": "/supervisor/status",
        "operator_status": "/operator/status",
        "paper_analytics": "/analytics/paper",
        "journal_status": "/journal/status",
        "ai_review_status": "/ai-review/status",
        "backtest_status": "/backtest/status",
        "backtest_v2": "/backtest/run-v2",
        "backtest_compare_v1_v2": "/backtest/compare-v1-v2",
        "research_status": "/research/status",
        "evidence_status": "/evidence/status",
        "daemon_status": "/daemon/status",
        "forward_test_status": "/forward-test/status",
        "orchestrator_status": "/orchestrator/status",
        "long_forward_test_status": "/long-forward-test/status",
        "live_readiness_status": "/live-readiness/status",
        "evidence_monitor_status": "/evidence-monitor/status",
        "signal_certifier_status": "/signal-certifier/status",
        "event_bus_status": "/event-bus/status",
        "strategy_agents_status": "/strategy-agents/status",
        "demo_oms_status": "/demo-oms/status",
        "broker_reconciliation_status": "/broker-reconciliation/status",
        "demo_command_queue_status": "/demo-command-queue/status",
        "demo_broker_execution_status": "/demo-broker-execution/status",
        "quick_validation_status": "/quick-validation/status",
        "quick_validation_run": "/quick-validation/run",
        "decision_engine_status": "/decision-engine/status",
        "evidence_integrity_status": "/evidence-integrity/status",
    }


def _dashboard_login_html(error: bool = False) -> str:
    error_html = "<p class=\"error\">Login failed. Check the dashboard password.</p>" if error else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AURIX Dashboard Login</title>
  <style>
    body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0f172a; color: #e5e7eb; }}
    main {{ width: min(420px, calc(100vw - 32px)); border: 1px solid #334155; background: #111827; padding: 28px; border-radius: 8px; }}
    h1 {{ margin: 0 0 16px; font-size: 22px; }}
    label {{ display: block; margin-bottom: 8px; color: #cbd5e1; }}
    input {{ width: 100%; box-sizing: border-box; padding: 12px; border-radius: 6px; border: 1px solid #475569; background: #020617; color: #f8fafc; }}
    button {{ width: 100%; margin-top: 16px; padding: 12px; border: 0; border-radius: 6px; background: #38bdf8; color: #082f49; font-weight: 700; cursor: pointer; }}
    .error {{ color: #fecaca; background: #7f1d1d; border: 1px solid #ef4444; padding: 10px; border-radius: 6px; }}
    .note {{ color: #94a3b8; font-size: 13px; line-height: 1.4; }}
  </style>
</head>
<body>
  <main>
    <h1>AURIX Dashboard</h1>
    {error_html}
    <form method="post" action="/dashboard/login">
      <label for="password">Dashboard password</label>
      <input id="password" name="password" type="password" autocomplete="current-password" required autofocus>
      <button type="submit">Log in</button>
    </form>
    <p class="note">The dashboard uses a server-side HttpOnly session cookie. API keys are not placed in the browser URL.</p>
  </main>
</body>
</html>"""


@app.get("/dashboard/login")
def dashboard_login_page() -> HTMLResponse:
    return HTMLResponse(_dashboard_login_html())


@app.post("/dashboard/login")
async def dashboard_login(request: Request) -> Any:
    body = (await request.body()).decode("utf-8")
    fields = parse_qs(body, keep_blank_values=True)
    password = fields.get("password", [""])[0]
    if not _dashboard_auth_configured() or not verify_dashboard_password(password, dashboard_auth_config):
        return HTMLResponse(_dashboard_login_html(error=True), status_code=401)
    token = create_session_token(dashboard_auth_config)
    response = RedirectResponse("/dashboard", status_code=303)
    response.headers.append(
        "set-cookie",
        build_cookie_header(config=dashboard_auth_config, token=token, secure=_request_is_https(request)),
    )
    return response


@app.post("/dashboard/logout")
def dashboard_logout(request: Request) -> RedirectResponse:
    response = RedirectResponse("/dashboard/login", status_code=303)
    response.headers.append(
        "set-cookie",
        build_clear_cookie_header(config=dashboard_auth_config, secure=_request_is_https(request)),
    )
    return response


@app.get("/dashboard/session")
def dashboard_session(request: Request) -> dict[str, Any]:
    authenticated = _dashboard_auth_ok(request) if _dashboard_auth_required() else True
    return {
        "authenticated": authenticated,
        "dashboard_auth_configured": _dashboard_auth_configured(),
        "read_only_dashboard": DASHBOARD_READ_ONLY,
    }


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {
        "status": "ok",
        "runtime_profile": RUNTIME_PROFILE,
        "dashboard_read_only": DASHBOARD_READ_ONLY,
        "broker_execution_enabled": demo_broker_execution_config.broker_execution_enabled,
        "runtime_session_id": runtime_session.runtime_session_id,
    }


@app.get("/dashboard")
@app.get("/dashboard/")
def dashboard() -> FileResponse:
    return FileResponse(DASHBOARD_DIR / "index.html")


@app.get("/dashboard/runtime-summary")
def dashboard_runtime_summary() -> dict[str, Any]:
    try:
        build_demo_broker_execution_status()
        return build_runtime_dashboard_summary(
            DATA_DIR,
            runtime_provenance=runtime_session.payload(),
            evidence_integrity=evidence_integrity_payload(),
            runtime_environment=runtime_environment_payload(),
        ).model_dump(mode="json")
    except Exception as exc:
        logger.exception("dashboard runtime summary degraded after unexpected runtime read failure")
        return {
            "generated_at": utc_now_iso(),
            "symbol": None,
            "account": {},
            "market": {},
            "session": {},
            "decision": {},
            "strategy_agents": {},
            "fast_rsi": {},
            "event_bus": {},
            "demo_oms": {},
            "demo_command_queue": {},
            "demo_broker_execution": {},
            "broker_reconciliation": {},
            "live_readiness": {},
            "evidence_growth": {},
            "signal_certification": {},
            "paper_risk_audit": {},
            "strategy_pipeline": {},
            "runtime_provenance": runtime_session.payload(),
            "evidence_integrity": {"status": "ERROR", "notes": [str(exc)]},
            "runtime_environment": runtime_environment_payload(),
            "safety": {
                "read_only_dashboard": True,
                "paper_trade_creation_allowed": False,
                "order_request_creation_allowed": False,
                "demo_command_queueing_allowed": False,
                "mt5_command_queueing_allowed": False,
                "demo_execution_allowed": False,
                "live_execution_allowed": False,
                "live_arming_allowed": False,
                "real_account_execution_allowed": False,
                "mt5_commands_queued": False,
                "broker_order_created": False,
                "broker_order_modified": False,
                "broker_order_closed": False,
                "paper_trade_created": False,
                "ea_settings_modified": False,
                "external_llm_used": False,
                "strategy_config_mutated": False,
            },
            "health": "ERROR",
            "health_reason": "runtime summary degraded after unexpected runtime read failure",
            "top_blocks": [str(exc)],
            "top_warnings": [],
            "next_expected_action": "Runtime summary degraded; inspect server logs.",
            "degraded": True,
        }


class OpenMarketRequest(BaseModel):
    terminal_id: str = DEFAULT_TERMINAL_ID
    symbol: str = "XAUUSDm"
    direction: str
    volume: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    comment: str = "AURIX"
    live_confirm: Optional[str] = None


class ClosePositionRequest(BaseModel):
    terminal_id: str = DEFAULT_TERMINAL_ID
    ticket: int
    volume: Optional[float] = None
    comment: str = "AURIX-CLOSE"
    live_confirm: Optional[str] = None


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


async def read_lenient_json_object(request: Request) -> dict[str, Any]:
    body = await request.body()
    text = body.decode("utf-8", errors="replace").strip().strip("\x00")

    try:
        payload, _ = json.JSONDecoder().raw_decode(text)
    except JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON snapshot payload: {exc}") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Snapshot payload must be a JSON object.")

    return payload


def normalize_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    account = _dict_or_empty(payload.get("account"))
    tick = _dict_or_empty(payload.get("tick"))
    raw = _dict_or_empty(payload.get("raw"))
    account_raw = _dict_or_empty(account.get("raw"))
    raw_account = _dict_or_empty(raw.get("account"))
    symbol = payload.get("symbol") or tick.get("symbol") or os.getenv("AURIX_SYMBOL", "XAUUSDm")
    if not account:
        account = {
            "currency": payload.get("currency") or payload.get("account_currency"),
            "balance": payload.get("balance") or payload.get("account_balance"),
            "equity": payload.get("equity") or payload.get("account_equity"),
            "free_margin": payload.get("free_margin") or payload.get("margin_free"),
            "margin_level": payload.get("margin_level"),
            "trade_mode": payload.get("trade_mode") or payload.get("account_type"),
            "server": payload.get("server"),
            "login": payload.get("login") or payload.get("account_login"),
        }
        account = {key: value for key, value in account.items() if value is not None}
    for target, aliases in {
        "login": ["account_login"],
        "name": ["account_name"],
        "server": ["account_server"],
        "company": ["account_company"],
        "currency": ["account_currency"],
        "trade_mode": ["account_trade_mode"],
        "is_demo": ["is_demo"],
    }.items():
        if account.get(target) is None:
            for alias in aliases:
                if payload.get(alias) is not None:
                    account[target] = payload.get(alias)
                    break
    for target in ["balance", "equity"]:
        if account.get(target) is None:
            if account_raw.get(target) is not None:
                account[target] = account_raw.get(target)
            elif raw_account.get(target) is not None:
                account[target] = raw_account.get(target)
    if not tick:
        tick = {
            "symbol": symbol,
            "bid": payload.get("bid"),
            "ask": payload.get("ask"),
            "spread_points": payload.get("spread_points") or payload.get("spread"),
            "time": payload.get("tick_time") or payload.get("time") or payload.get("timestamp"),
        }
        tick = {key: value for key, value in tick.items() if value is not None}
    if tick and not tick.get("symbol"):
        tick["symbol"] = symbol
    return {
        "terminal_id": str(payload.get("terminal_id") or DEFAULT_TERMINAL_ID),
        "received_at": str(payload.get("received_at") or utc_now_iso()),
        "account": account,
        "tick": tick,
        "candles": _list_or_empty(payload.get("candles")),
        "positions": _list_or_empty(payload.get("positions")),
        "orders": _list_or_empty(payload.get("orders")),
        "deals": _list_or_empty(payload.get("deals")),
        "raw": raw,
    }


def normalize_execution_result(payload: dict[str, Any]) -> ExecutionResult:
    ok = payload.get("ok")
    status = str(payload.get("status") or "").upper()
    if ok is None and status:
        ok = status in {"FILLED", "DONE", "SUCCESS"}
    return ExecutionResult(
        terminal_id=str(payload.get("terminal_id") or DEFAULT_TERMINAL_ID),
        command_id=str(payload.get("command_id") or ""),
        ok=bool(ok),
        retcode=payload.get("retcode") or payload.get("error_code"),
        message=str(payload.get("message") or payload.get("error_message") or status),
        order=payload.get("order") or payload.get("ticket"),
        deal=payload.get("deal"),
        symbol=payload.get("symbol"),
        direction=payload.get("direction") or payload.get("side"),
        volume=payload.get("volume"),
        price=payload.get("price"),
        received_at=str(payload.get("received_at") or utc_now_iso()),
        raw=_dict_or_empty(payload.get("raw")),
    )


def log_snapshot(snapshot: dict[str, Any]) -> None:
    account = _dict_or_empty(snapshot.get("account"))
    tick = _dict_or_empty(snapshot.get("tick"))
    positions = _list_or_empty(snapshot.get("positions"))
    print(
        "AURIX snapshot received "
        f"terminal_id={snapshot.get('terminal_id')} "
        f"symbol={tick.get('symbol', 'n/a')} "
        f"balance={account.get('balance', 'n/a')} "
        f"equity={account.get('equity', 'n/a')} "
        f"positions={len(positions)}",
        flush=True,
    )


def run_runtime_diagnostics_cycle(source: str = "runtime_snapshot") -> dict[str, Any]:
    paper_before = len(paper_ledger.list_trades())
    commands_before = len(store.list_commands())
    oms_before = len(demo_oms.load_order_requests())
    queue_payloads_before = len(demo_command_queue.load_payloads())
    result: dict[str, Any] = {
        "ok": True,
        "source": source,
        "observation_events": 0,
        "strategy_evaluations": 0,
        "decision_action": None,
        "errors": [],
    }
    try:
        observation = _event_bus_collect_payload()
        result["observation_events"] = observation.get("published_count", 0)
    except Exception as exc:
        logger.exception("runtime observation collection failed")
        result["errors"].append(f"observation collection failed: {exc}")

    try:
        report = broker_reconciler.run()
        result["broker_reconciliation_status"] = report.get("status")
    except Exception as exc:
        logger.exception("broker reconciliation refresh failed")
        result["ok"] = False
        result["errors"].append(f"broker reconciliation failed: {exc}")

    try:
        strategy_results = strategy_agent_evaluator.evaluate_all_agents()
        result["strategy_evaluations"] = len(strategy_results)
    except Exception as exc:
        logger.exception("strategy diagnostics cycle failed")
        event_bus.publish_event(
            AurixEvent(
                event_type=AurixEventType.STRATEGY_PIPELINE_ERROR,
                source="runtime_strategy_diagnostics",
                symbol=strategy_agents_config.symbol,
                payload={"diagnostic_event": "strategy_pipeline_error", "error": str(exc), "reason": "exception in strategy loop"},
                safety=EventSafety(),
            )
        )
        result["ok"] = False
        result["errors"].append(f"strategy diagnostics failed: {exc}")

    try:
        decision = decision_engine.evaluate()
        result["decision_action"] = decision.get("action")
    except Exception as exc:
        logger.exception("decision diagnostics cycle failed")
        result["ok"] = False
        result["errors"].append(f"decision evaluation failed: {exc}")

    try:
        build_demo_broker_execution_status()
    except Exception as exc:
        logger.exception("demo broker execution status refresh failed")
        result["errors"].append(f"broker execution status failed: {exc}")

    result["paper_trades_created"] = len(paper_ledger.list_trades()) - paper_before
    result["commands_queued"] = len(store.list_commands()) - commands_before
    result["order_requests_created"] = len(demo_oms.load_order_requests()) - oms_before
    result["mt5_payloads_queued"] = len(demo_command_queue.load_payloads()) - queue_payloads_before
    result["safety"] = {
        "paper_trade_creation_allowed": False,
        "order_request_creation_allowed": False,
        "live_execution_allowed": False,
        "command_queueing_allowed": False,
        "mt5_commands_queued": False,
    }
    return result


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "aurix-mac-wine-bridge",
        "terminal_id": DEFAULT_TERMINAL_ID,
    }


@app.post("/mt5/snapshot")
@app.post("/mt5/snapshot/")
async def receive_snapshot(request: Request) -> dict[str, Any]:
    payload = await read_lenient_json_object(request)
    snapshot = normalize_snapshot(payload)
    store.save_snapshot(snapshot)
    market_recorder.record_snapshot(snapshot)
    diagnostics = run_runtime_diagnostics_cycle("mt5_snapshot")
    log_snapshot(snapshot)
    tick = _dict_or_empty(snapshot.get("tick"))
    return {
        "ok": True,
        "status": "snapshot_received",
        "terminal_id": snapshot.get("terminal_id"),
        "symbol": tick.get("symbol") or payload.get("symbol") or os.getenv("AURIX_SYMBOL", "XAUUSDm"),
        "strategy_diagnostics": diagnostics,
    }


@app.post("/mt5/snapshot-debug")
async def receive_snapshot_debug(request: Request) -> dict[str, Any]:
    payload = await read_lenient_json_object(request)
    store.save_snapshot_debug(payload)
    return {"ok": True}


@app.post("/mt5/execution-result")
async def receive_execution_result(request: Request) -> dict[str, Any]:
    payload = await read_lenient_json_object(request)
    result = normalize_execution_result(payload)
    if not result.command_id:
        raise HTTPException(status_code=400, detail="Execution result command_id is required.")
    result.provenance = runtime_provenance_metadata("mt5_execution_result", "aurix_bridge_server.main.receive_execution_result")
    store.mark_result(result)
    demo_result = {
        **payload,
        "ok": result.ok,
        "command_id": result.command_id,
        "terminal_id": result.terminal_id,
        "status": str(payload.get("status") or ("FILLED" if result.ok else "ERROR")),
        "received_at": result.received_at,
        "provenance": result.provenance,
    }
    demo_broker_execution_store.append_execution_result(demo_result)
    if durable_audit_store.database_url:
        try:
            durable_audit_store.write_broker_execution_result(demo_result)
        except DurableAuditError as exc:
            logger.warning("durable audit broker result write failed: %s", exc)
    return {"ok": True, "status": "execution_result_received", "command_id": result.command_id}


@app.get("/mt5/command")
@app.get("/mt5/command/")
def mt5_next_command(terminal_id: str = Query(default=DEFAULT_TERMINAL_ID)) -> dict[str, Any]:
    if terminal_id not in demo_broker_execution_config.terminal_id_allowlist:
        return {
            "ok": True,
            "command": None,
            "status": "NO_COMMAND",
            "terminal_id": terminal_id,
            "reason": "execution gate blocked",
            "primary_block": "terminal id is not allowlisted",
        }
    if not demo_broker_execution_config.broker_execution_enabled:
        build_demo_broker_execution_status(
            latest_gate_decision={
                "allowed": False,
                "action": "BROKER_EXECUTION_DISABLED",
                "reason": "broker execution disabled",
                "primary_block": "broker execution disabled",
                "queue_state": "BLOCKED",
                "spread_gate": "BLOCKED",
                "checks": [],
            }
        )
        return {
            "ok": True,
            "command": None,
            "status": "NO_COMMAND",
            "terminal_id": terminal_id,
            "reason": "broker execution disabled",
        }
    pending = demo_broker_execution_store.pending_for_terminal(terminal_id)
    if pending is None:
        gate = evaluate_demo_broker_execution_gate()
        if gate.get("allowed"):
            try:
                audited = prepare_durable_audit_for_broker_command(gate, terminal_id)
            except DurableAuditError as exc:
                reason = str(exc) if str(exc) in {"DURABLE_AUDIT_DISABLED", "DURABLE_AUDIT_DUPLICATE_COMMAND"} else "DURABLE_AUDIT_WRITE_FAILED"
                blocked_gate = _durable_audit_block(reason, str(exc))
                demo_broker_execution_store.write_status(build_demo_broker_execution_status(latest_gate_decision=blocked_gate))
                return {
                    "ok": True,
                    "command": None,
                    "status": "NO_COMMAND",
                    "terminal_id": terminal_id,
                    "reason": reason,
                    "primary_block": reason,
                }
            try:
                pending = demo_broker_execution_store.create_command(
                    terminal_id=terminal_id,
                    side=str(gate["side"]),
                    symbol=str(gate["symbol"]),
                    volume=float(gate["volume"]),
                    stop_loss=float(gate["stop_loss"]),
                    take_profit=float(gate["take_profit"]),
                    strategy_id=str(gate.get("strategy_id") or ""),
                    signal_id=str(gate.get("signal_id") or ""),
                    signal_confidence=gate.get("signal_confidence"),
                    signal_reasons=gate.get("signal_reasons") or [],
                    decision_cycle_id=gate.get("decision_cycle_id"),
                    final_gate_result=gate.get("final_gate_result"),
                    runtime_session_id=runtime_session.runtime_session_id,
                    provenance=audited.get("provenance") or runtime_provenance_metadata("demo_broker_mt5_command", "aurix_bridge_server.main.mt5_next_command"),
                    safety_checks_snapshot=gate,
                    ttl_seconds=demo_broker_execution_config.command_ttl_seconds,
                    magic_number=demo_broker_execution_config.magic_number,
                    command_id=str(audited["command_id"]),
                    comment=str(audited["comment"]),
                )
                durable_audit_store.mark_command_queued(str(pending.get("command_id")), pending)
            except Exception as exc:
                if audited.get("command_id"):
                    demo_broker_execution_store.mark_blocked(str(audited["command_id"]), "DURABLE_AUDIT_WRITE_FAILED")
                blocked_gate = _durable_audit_block("DURABLE_AUDIT_WRITE_FAILED", str(exc))
                demo_broker_execution_store.write_status(build_demo_broker_execution_status(latest_gate_decision=blocked_gate))
                return {
                    "ok": True,
                    "command": None,
                    "status": "NO_COMMAND",
                    "terminal_id": terminal_id,
                    "reason": "DURABLE_AUDIT_WRITE_FAILED",
                    "primary_block": "DURABLE_AUDIT_WRITE_FAILED",
                }
        else:
            demo_broker_execution_store.write_status(build_demo_broker_execution_status(latest_gate_decision=gate))
            return {
                "ok": True,
                "command": None,
                "status": "NO_COMMAND",
                "terminal_id": terminal_id,
                "reason": "execution gate blocked",
                "primary_block": gate.get("primary_block") or gate.get("reason"),
            }
    delivered = demo_broker_execution_store.mark_delivered(str(pending.get("command_id"))) or pending
    return {
        "ok": True,
        "command": command_for_ea(delivered),
        "status": "COMMAND_AVAILABLE",
        "terminal_id": terminal_id,
    }


def command_for_ea(command: dict[str, Any]) -> dict[str, Any]:
    return {
        "command_id": command.get("command_id"),
        "mode": "BROKER",
        "action": "OPEN_MARKET",
        "symbol": command.get("symbol"),
        "side": command.get("side"),
        "volume": command.get("volume"),
        "stop_loss": command.get("stop_loss"),
        "take_profit": command.get("take_profit"),
        "magic_number": command.get("magic_number"),
        "comment": command.get("comment") or "AURIX-DEMO",
        "expires_at": command.get("expires_at"),
    }


def latest_broker_execution_signal() -> dict[str, Any] | None:
    items = strategy_agent_evaluator.latest()
    for item in reversed(items):
        if not isinstance(item, dict):
            continue
        if item.get("symbol") != "XAUUSDm":
            continue
        if item.get("status") in {"SIGNAL", "VALID", "ACTIONABLE"}:
            return item
    return None


def evaluate_demo_broker_execution_gate() -> dict[str, Any]:
    summary_health = "UNKNOWN"
    try:
        summary_health = build_runtime_dashboard_summary(DATA_DIR).health
    except Exception:
        summary_health = "UNKNOWN"
    return demo_broker_execution_gate.evaluate(
        snapshot=store.latest_snapshot(),
        signal=latest_broker_execution_signal(),
        runtime_session_id=runtime_session.runtime_session_id,
        runtime_health=summary_health,
    )


def _latest_decision_payload() -> dict[str, Any]:
    try:
        events = event_bus.load_events_by_type(AurixEventType.AURIX_DECISION_EVENT.value, limit=20)
    except Exception:
        events = []
    if events:
        payload = events[-1].get("payload")
        if isinstance(payload, dict):
            return payload
    report = decision_engine.store.latest()
    return report if isinstance(report, dict) else {}


def _broker_command_id(signal_id: str | None) -> str:
    if signal_id:
        cleaned = "".join(ch for ch in str(signal_id) if ch.isalnum())[:24]
        if cleaned:
            return f"cmd{cleaned}"
    return uuid4().hex


def _broker_command_comment(command_id: str) -> str:
    return f"AURIX-DEMO:{command_id[:8]}"[:31]


def _durable_audit_block(reason: str, detail: str | None = None) -> dict[str, Any]:
    return {
        "allowed": False,
        "action": "BLOCKED",
        "reason": reason,
        "primary_block": reason,
        "detail": detail,
        "queue_state": "BLOCKED",
        "spread_gate": "BLOCKED",
        "checks": [{"name": "durable_audit_write", "passed": False, "reason": reason, "detail": detail}],
    }


def prepare_durable_audit_for_broker_command(gate: dict[str, Any], terminal_id: str) -> dict[str, Any]:
    if not durable_audit_store.database_url:
        raise DurableAuditError("DURABLE_AUDIT_DISABLED")
    signal = latest_broker_execution_signal() or {}
    decision = _latest_decision_payload()
    command_id = _broker_command_id(str(gate.get("signal_id") or signal.get("id") or ""))
    comment = _broker_command_comment(command_id)
    if durable_audit_store.command_already_queued(command_id):
        durable_audit_store.mark_duplicate_command_blocked(command_id)
        raise DurableAuditError("DURABLE_AUDIT_DUPLICATE_COMMAND")
    command = {
        "command_id": command_id,
        "terminal_id": terminal_id,
        "mode": "BROKER",
        "action": "OPEN_MARKET",
        "symbol": gate.get("symbol"),
        "side": gate.get("side"),
        "volume": gate.get("volume"),
        "entry": signal.get("entry_reference"),
        "stop_loss": gate.get("stop_loss"),
        "take_profit": gate.get("take_profit"),
        "magic_number": demo_broker_execution_config.magic_number,
        "comment": comment,
        "strategy_id": gate.get("strategy_id"),
        "signal_id": gate.get("signal_id"),
        "signal_confidence": gate.get("signal_confidence"),
        "signal_reasons": gate.get("signal_reasons") or [],
        "decision_cycle_id": gate.get("decision_cycle_id"),
        "final_gate_result": gate.get("final_gate_result"),
        "runtime_session_id": runtime_session.runtime_session_id,
        "provenance": runtime_provenance_metadata("demo_broker_mt5_command", "aurix_bridge_server.main.mt5_next_command"),
        "safety_checks_snapshot": gate,
    }
    if signal:
        durable_audit_store.write_strategy_evaluation(signal, market_snapshot=store.latest_snapshot() or {})
    decision_id = durable_audit_store.write_decision_record(decision or {"action": gate.get("action"), "reason": gate.get("reason")}, gates=gate, strategy_snapshot=signal)
    explanation = build_trade_explanation(
        oms_request={},
        oms_intent={
            "id": signal.get("id"),
            "strategy_name": signal.get("strategy_name"),
            "direction": signal.get("direction"),
            "confidence": signal.get("confidence"),
            "setup_reason": signal.get("setup_reason"),
            "decision_trace": signal.get("decision_trace") if isinstance(signal.get("decision_trace"), dict) else {},
        },
        preview={
            "id": command_id,
            "symbol": gate.get("symbol"),
            "direction": gate.get("side"),
            "volume": gate.get("volume"),
            "entry_reference": signal.get("entry_reference"),
            "stop_loss": gate.get("stop_loss"),
            "take_profit": gate.get("take_profit"),
            "strategy_name": signal.get("strategy_name") or gate.get("strategy_id"),
        },
        validation=gate,
        payload={"id": command_id, "side": gate.get("side"), "volume": gate.get("volume"), "sl": gate.get("stop_loss"), "tp": gate.get("take_profit")},
        snapshot=store.latest_snapshot() or {},
        decision=decision,
        strategy_diagnostics=signal,
    )
    explanation["trade_id"] = command_id
    local_explanation = trade_explanation_store.write(explanation)
    explanation_id = durable_audit_store.write_trade_explanation(local_explanation, explanation_id=str(local_explanation.get("id") or command_id), command_id=command_id, decision_id=decision_id)
    durable_audit_store.write_command_audit(command, explanation_id=explanation_id, decision_id=decision_id, queued=False, status="WRITE_BEFORE_SEND")
    command["durable_audit"] = {"explanation_id": explanation_id, "decision_id": decision_id}
    return command


def build_demo_broker_execution_status(latest_gate_decision: dict[str, Any] | None = None) -> dict[str, Any]:
    latest_gate_decision = latest_gate_decision or evaluate_demo_broker_execution_gate()
    snapshot = store.latest_snapshot()
    account_verification = verify_demo_account(snapshot)
    account = (snapshot or {}).get("account") or {}
    balance = account.get("balance")
    try:
        balance_value = float(balance)
    except (TypeError, ValueError):
        balance_value = None
    risk_per_trade = float(demo_broker_execution_config.risk_per_trade_percent)
    daily_risk_limit = float(demo_broker_execution_config.daily_risk_limit_percent)
    return demo_broker_execution_store.write_status(
        {
            "generated_at": utc_now_iso(),
            "execution_mode": demo_broker_execution_config.execution_mode,
            "config": demo_broker_execution_config.safety_flags(),
            "broker_execution": "ENABLED" if demo_broker_execution_config.broker_execution_enabled else "DISABLED",
            "queue_state": latest_gate_decision.get("queue_state") or ("READY" if latest_gate_decision.get("allowed") else "BLOCKED"),
            "spread_gate": latest_gate_decision.get("spread_gate") or "BLOCKED",
            "engine_max_spread_points": demo_broker_execution_config.max_spread_points,
            "risk_model": {
                "risk_per_trade_percent": risk_per_trade,
                "daily_risk_limit_percent": daily_risk_limit,
                "risk_amount": round(balance_value * (risk_per_trade / 100.0), 4) if balance_value is not None else None,
                "daily_loss_limit": round(balance_value * (daily_risk_limit / 100.0), 4) if balance_value is not None else None,
                "source": "account_balance",
            },
            "strategy_engine": "v1 / v2 / Fast RSI / BlackCat Cloud",
            "selected_strategy": latest_gate_decision.get("strategy_id"),
            "selected_signal": latest_gate_decision.get("signal_id"),
            "latest_gate_block": latest_gate_decision.get("primary_block") or latest_gate_decision.get("reason"),
            "demo_account_verification": account_verification,
            "latest_gate_decision": latest_gate_decision,
            "daily_risk_guard": latest_gate_decision.get("daily_risk_guard"),
            "latest_command": demo_broker_execution_store.latest_command(),
            "latest_execution_result": demo_broker_execution_store.latest_execution_result(),
            "durable_audit": durable_audit_store.status(),
            "safety": {
                "broker_execution_enabled": demo_broker_execution_config.broker_execution_enabled,
                "internal_queue_controlled_by_broker_execution": True,
                "real_money_live_path_added": False,
            },
        }
    )


@app.get("/demo-broker-execution/status")
def demo_broker_execution_status() -> dict[str, Any]:
    return build_demo_broker_execution_status()


def quick_validation_providers() -> dict[str, Any]:
    def context_for_validation() -> dict[str, Any]:
        latest = context_engine.latest()
        if latest is not None:
            return latest
        context = context_engine.evaluate(
            snapshot=store.latest_snapshot(),
            recorded_candles=market_recorder.list_candles(),
            market_quality=market_recorder.quality(),
        )
        return context.model_dump()

    def strategy_v1_for_validation() -> dict[str, Any]:
        signal = evaluate_xauusd_paper_v1(
            snapshot=store.latest_snapshot(),
            context=context_for_validation(),
            candles=market_recorder.list_candles(),
            previous_signals=store.list_strategy_signals(),
            config=xauusd_paper_v1_config,
        )
        return signal.model_dump()

    def strategy_v2_for_validation() -> dict[str, Any]:
        signal = evaluate_xauusd_paper_v2(
            snapshot=store.latest_snapshot(),
            context=context_for_validation(),
            candles=market_recorder.list_candles(),
            market_quality=market_recorder.quality(),
            previous_signals=store.list_strategy_signals(),
            config=xauusd_paper_v2_config,
        )
        data = signal.model_dump()
        data["command_id"] = None
        return data

    def analytics_for_validation() -> dict[str, Any]:
        trades, signals, contexts, quality = performance_store.read_inputs()
        return generate_paper_performance_report(trades, signals, contexts, quality).model_dump()

    def journal_for_validation() -> dict[str, Any]:
        trades, signals, contexts, quality, _ = journal_store.read_inputs()
        return {
            "paper_trade_reviews": len(journal_reviewer.review_paper_trades(trades, signals, contexts, quality)),
            "signal_reviews": len(journal_reviewer.review_signals(signals, trades, contexts, quality)),
        }

    def ai_review_for_validation() -> dict[str, Any]:
        report = ai_review_reviewer.generate(ai_review_store.read_inputs())
        return {**report.model_dump(), "external_llm_used": False, "allow_external_llm": ai_review_config.allow_external_llm}

    def evidence_for_validation() -> dict[str, Any]:
        status = _build_operator_status(include_evidence=False)
        summary = build_operator_summary(status).model_dump()
        report = evidence_gate_store.evaluate(evidence_gate_store.read_inputs(status.model_dump(), summary))
        return report.model_dump()

    def readiness_for_validation() -> dict[str, Any]:
        status = _build_operator_status(include_evidence=True, include_live_readiness=False)
        summary = build_operator_summary(status).model_dump()
        report = live_readiness_store.evaluate(live_readiness_store.read_inputs(status.model_dump(), summary))
        return report.model_dump()

    return {
        "latest_snapshot": store.latest_snapshot,
        "market_quality": market_recorder.quality,
        "market_candles": market_recorder.list_candles,
        "context": context_for_validation,
        "strategy_v1": strategy_v1_for_validation,
        "strategy_v2": strategy_v2_for_validation,
        "paper_status": paper_status,
        "paper_analytics": analytics_for_validation,
        "journal_review": journal_for_validation,
        "ai_review": ai_review_for_validation,
        "evidence_gate": evidence_for_validation,
        "live_readiness": readiness_for_validation,
        "runtime_summary": lambda: build_runtime_dashboard_summary(
            DATA_DIR,
            runtime_provenance=runtime_session.payload(),
            evidence_integrity=evidence_integrity_payload(),
            runtime_environment=runtime_environment_payload(),
        ).model_dump(mode="json"),
        "mt5_command": lambda: mt5_next_command(DEFAULT_TERMINAL_ID),
        "operator_summary": operator_summary,
        "dashboard_self_check": lambda: {"ok": True, "source": "runtime-summary-read-only"},
    }


def build_quick_validation_runner() -> QuickValidationRunner:
    return QuickValidationRunner(DATA_DIR, providers=quick_validation_providers())


@app.get("/quick-validation/status")
def quick_validation_status() -> dict[str, Any]:
    latest = quick_validation_store.latest()
    if latest is None:
        return {"ok": True, "status": "NOT_RUN", "report": None}
    return {
        "ok": True,
        "status": latest.get("status"),
        "generated_at": latest.get("generated_at"),
        "summary": latest.get("summary") or {},
        "safety": latest.get("safety") or {},
        "blocking_reasons": latest.get("blocking_reasons") or [],
        "warnings": latest.get("warnings") or [],
        "recommendations": latest.get("recommendations") or [],
    }


@app.get("/quick-validation/latest")
def quick_validation_latest() -> dict[str, Any]:
    latest = quick_validation_store.latest()
    if latest is None:
        raise HTTPException(status_code=404, detail="No quick validation report yet.")
    return latest


@app.post("/quick-validation/run")
def quick_validation_run() -> dict[str, Any]:
    return build_quick_validation_runner().run().model_dump(mode="json")


@app.post("/quick-validation/reset")
def quick_validation_reset() -> dict[str, Any]:
    quick_validation_store.reset()
    return {"ok": True, "status": "RESET"}


@app.get("/state/latest")
def latest_state() -> dict[str, Any]:
    snapshot = store.latest_snapshot()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No snapshot received yet.")
    return snapshot


@app.get("/state/account")
def account_state() -> dict[str, Any]:
    snapshot = store.latest_snapshot()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No snapshot received yet.")
    return snapshot.get("account", {})


@app.get("/state/positions")
def positions() -> list[dict[str, Any]]:
    snapshot = store.latest_snapshot()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No snapshot received yet.")
    return snapshot.get("positions", [])


@app.get("/state/orders")
def orders() -> list[dict[str, Any]]:
    snapshot = store.latest_snapshot()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No snapshot received yet.")
    return snapshot.get("orders", [])


@app.get("/state/deals")
def deals() -> list[dict[str, Any]]:
    snapshot = store.latest_snapshot()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No snapshot received yet.")
    return snapshot.get("deals", [])


def _current_context_observation() -> dict[str, Any] | None:
    return context_engine.latest()


def _event_bus_collect_payload() -> dict[str, Any]:
    paper_before = len(paper_ledger.list_trades())
    commands_before = len(store.list_commands())
    published = collect_observation_events(
        event_bus=event_bus,
        snapshot=store.latest_snapshot(),
        market_quality=market_recorder.quality(),
        context=_current_context_observation(),
        signals=store.list_strategy_signals(),
        paper_trades=paper_ledger.list_trades(),
        latest_paper_risk_decision=paper_risk_audit_store.latest(),
    )
    event_items = [item for item in published if not item.get("collector_summary")]
    summary = next((item for item in published if item.get("collector_summary")), {})
    paper_after = len(paper_ledger.list_trades())
    commands_after = len(store.list_commands())
    status = event_bus.get_latest_status()
    return {
        "ok": True,
        "published_count": len(event_items),
        "event_types": [item.get("event_type") for item in event_items],
        "last_sequence": status.get("last_sequence"),
        "state_snapshot_path": status.get("state_snapshot_path"),
        "state_exists": status.get("state_exists"),
        "correlation_id": summary.get("correlation_id"),
        "paper_trades_before": paper_before,
        "paper_trades_after": paper_after,
        "paper_trades_created": paper_after - paper_before,
        "commands_before": commands_before,
        "commands_after": commands_after,
        "commands_queued": commands_after - commands_before,
        "safety": {
            "paper_trade_creation_attempted": False,
            "mt5_execution_attempted": False,
            "live_execution_allowed": False,
            "command_queueing_allowed": False,
        },
    }


@app.get("/event-bus/status")
def event_bus_status() -> dict[str, Any]:
    try:
        return event_bus.get_latest_status()
    except Exception as exc:
        logger.exception("event bus status degraded after unexpected status write/read failure")
        cached = store._read_json(Path(DATA_DIR) / "event_bus" / "status.json", {}) if hasattr(store, "_read_json") else {}
        return {
            **(cached if isinstance(cached, dict) else {}),
            "degraded": True,
            "error": str(exc),
            "live_execution_allowed": False,
            "command_queueing_allowed": False,
            "safety": {
                "live_execution_allowed": False,
                "command_queueing_allowed": False,
                "paper_trade_creation_allowed": False,
                "mt5_execution_attempted": False,
            },
        }


@app.get("/event-bus/latest-state")
def event_bus_latest_state() -> dict[str, Any]:
    return event_bus.get_latest_state()


@app.get("/event-bus/recent")
def event_bus_recent(limit: int = Query(20, ge=1, le=500)) -> dict[str, Any]:
    return {"items": event_bus.load_recent_events(limit), "limit": limit}


@app.get("/event-bus/recent/{event_type}")
def event_bus_recent_by_type(event_type: str, limit: int = Query(20, ge=1, le=500)) -> dict[str, Any]:
    if event_type not in EVENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported event_type: {event_type}")
    return {"items": event_bus.load_events_by_type(event_type, limit), "limit": limit, "event_type": event_type}


@app.get("/event-bus/correlation/{correlation_id}")
def event_bus_correlation(correlation_id: str) -> dict[str, Any]:
    return {"items": event_bus.load_events_by_correlation_id(correlation_id), "correlation_id": correlation_id}


@app.post("/event-bus/collect")
def event_bus_collect() -> dict[str, Any]:
    return _event_bus_collect_payload()


@app.post("/event-bus/reset")
def event_bus_reset() -> dict[str, Any]:
    return event_bus.reset_event_bus()


@app.get("/strategy-agents/status")
def strategy_agents_status() -> dict[str, Any]:
    return strategy_agent_evaluator.status()


@app.get("/strategy-agents/registry")
def strategy_agents_registry() -> dict[str, Any]:
    return strategy_agent_evaluator.registry_payload()


@app.get("/strategy-agents/latest")
def strategy_agents_latest() -> dict[str, Any]:
    return {"items": strategy_agent_evaluator.latest()}


@app.post("/strategy-agents/evaluate")
def strategy_agents_evaluate() -> dict[str, Any]:
    paper_before = len(paper_ledger.list_trades())
    commands_before = len(store.list_commands())
    results = strategy_agent_evaluator.evaluate_all_agents()
    paper_after = len(paper_ledger.list_trades())
    commands_after = len(store.list_commands())
    return {
        "ok": True,
        "items": [result.model_dump() for result in results],
        "paper_trades_created": paper_after - paper_before,
        "commands_queued": commands_after - commands_before,
        "order_requests_created": 0,
        "safety": {
            "paper_trade_creation_allowed": False,
            "order_request_creation_allowed": False,
            "live_execution_allowed": False,
            "command_queueing_allowed": False,
        },
    }


@app.get("/strategy-agents/history")
def strategy_agents_history(limit: int = Query(20, ge=1, le=500)) -> dict[str, Any]:
    return {"items": strategy_agent_evaluator.history(limit), "limit": limit}


@app.get("/strategy-agents/trace/recent")
def strategy_agents_trace_recent(limit: int = Query(20, ge=1, le=500)) -> dict[str, Any]:
    return {"items": strategy_agent_evaluator.recent_traces(limit), "limit": limit}


@app.post("/strategy-agents/reset")
def strategy_agents_reset() -> dict[str, Any]:
    return strategy_agent_evaluator.reset()


@app.get("/demo-oms/status")
def demo_oms_status() -> dict[str, Any]:
    return demo_oms.get_demo_oms_status()


@app.get("/demo-oms/intents")
def demo_oms_intents(limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    items = demo_oms.load_order_intents()
    return {"items": items[-limit:], "limit": limit, "count": len(items), "safety": demo_oms_status().get("safety")}


@app.get("/demo-oms/requests")
def demo_oms_requests(limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    items = demo_oms.load_order_requests()
    return {"items": items[-limit:], "limit": limit, "count": len(items), "safety": demo_oms_status().get("safety")}


@app.get("/demo-oms/history")
def demo_oms_history(limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    return {"items": demo_oms.history(limit), "limit": limit, "safety": demo_oms_status().get("safety")}


@app.post("/demo-oms/process-latest-signal")
def demo_oms_process_latest_signal() -> dict[str, Any]:
    paper_before = len(paper_ledger.list_trades())
    commands_before = len(store.list_commands())
    results_before = len(store.list_results())
    result = demo_oms.process_latest_signal_event()
    paper_after = len(paper_ledger.list_trades())
    commands_after = len(store.list_commands())
    results_after = len(store.list_results())
    result["paper_trades_created"] = paper_after - paper_before
    result["commands_queued"] = commands_after - commands_before
    result["broker_orders_created"] = results_after - results_before
    result["safety"] = {
        **(result.get("safety") or {}),
        "paper_trade_created": False,
        "mt5_commands_queued": False,
        "broker_order_created": False,
        "ea_settings_modified": False,
    }
    return result


@app.post("/demo-oms/reset")
def demo_oms_reset() -> dict[str, Any]:
    return demo_oms.reset_demo_oms()


@app.get("/broker-reconciliation/status")
def broker_reconciliation_status() -> dict[str, Any]:
    return broker_reconciler.status()


@app.get("/broker-reconciliation/latest")
def broker_reconciliation_latest() -> dict[str, Any]:
    latest = broker_reconciler.latest()
    if latest is None:
        raise HTTPException(status_code=404, detail="No broker reconciliation report yet.")
    return latest


@app.get("/broker-reconciliation/history")
def broker_reconciliation_history(limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    return {"items": broker_reconciler.history(limit), "limit": limit, "safety": broker_reconciliation_status().get("safety")}


@app.post("/broker-reconciliation/run")
def broker_reconciliation_run() -> dict[str, Any]:
    paper_before = len(paper_ledger.list_trades())
    commands_before = len(store.list_commands())
    results_before = len(store.list_results())
    report = broker_reconciler.run()
    paper_after = len(paper_ledger.list_trades())
    commands_after = len(store.list_commands())
    results_after = len(store.list_results())
    report["paper_trades_created"] = paper_after - paper_before
    report["commands_queued"] = commands_after - commands_before
    report["broker_orders_created"] = results_after - results_before
    report["broker_orders_modified"] = 0
    report["broker_orders_closed"] = 0
    return report


@app.post("/broker-reconciliation/reset")
def broker_reconciliation_reset() -> dict[str, Any]:
    return broker_reconciler.reset()


@app.get("/demo-command-queue/status")
def demo_command_queue_status() -> dict[str, Any]:
    return demo_command_queue.get_demo_command_queue_status()


@app.get("/demo-command-queue/previews")
def demo_command_queue_previews(limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    items = demo_command_queue.load_previews()
    return {"items": items[-limit:], "limit": limit, "count": len(items), "safety": demo_command_queue_status().get("safety")}


@app.get("/demo-command-queue/payloads")
def demo_command_queue_payloads(limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    items = demo_command_queue.load_payloads()
    return {"items": items[-limit:], "limit": limit, "count": len(items), "safety": demo_command_queue_status().get("safety")}


@app.get("/demo-command-queue/history")
def demo_command_queue_history(limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    return {"items": demo_command_queue.history(limit), "limit": limit, "safety": demo_command_queue_status().get("safety")}


@app.post("/demo-command-queue/preview-latest")
def demo_command_queue_preview_latest() -> dict[str, Any]:
    paper_before = len(paper_ledger.list_trades())
    commands_before = len(store.list_commands())
    results_before = len(store.list_results())
    result = demo_command_queue.preview_latest_oms_request()
    result["paper_trades_created"] = len(paper_ledger.list_trades()) - paper_before
    result["commands_queued"] = len(store.list_commands()) - commands_before
    result["broker_orders_created"] = len(store.list_results()) - results_before
    return result


@app.post("/demo-command-queue/dry-run-latest")
def demo_command_queue_dry_run_latest() -> dict[str, Any]:
    paper_before = len(paper_ledger.list_trades())
    commands_before = len(store.list_commands())
    results_before = len(store.list_results())
    result = demo_command_queue.dry_run_latest_oms_request()
    result["paper_trades_created"] = len(paper_ledger.list_trades()) - paper_before
    result["commands_queued"] = len(store.list_commands()) - commands_before
    result["broker_orders_created"] = len(store.list_results()) - results_before
    result["broker_orders_modified"] = 0
    result["broker_orders_closed"] = 0
    return result


@app.post("/demo-command-queue/reset")
def demo_command_queue_reset() -> dict[str, Any]:
    return demo_command_queue.reset_demo_command_queue()


@app.get("/decision-engine/status")
def decision_engine_status() -> dict[str, Any]:
    return decision_engine.status()


@app.get("/decision-engine/latest")
def decision_engine_latest() -> dict[str, Any]:
    latest = decision_engine.latest()
    if latest is None:
        raise HTTPException(status_code=404, detail="No decision report yet.")
    return latest


@app.get("/decision-engine/history")
def decision_engine_history(limit: int = Query(50, ge=1, le=1000)) -> dict[str, Any]:
    return {"items": decision_engine.history(limit), "limit": limit, "safety": decision_engine_status().get("safety")}


@app.post("/decision-engine/evaluate")
def decision_engine_evaluate() -> dict[str, Any]:
    paper_before = len(paper_ledger.list_trades())
    commands_before = len(store.list_commands())
    results_before = len(store.list_results())
    oms_before = len(demo_oms.load_order_requests())
    report = decision_engine.evaluate()
    report["paper_trades_created"] = len(paper_ledger.list_trades()) - paper_before
    report["commands_queued"] = len(store.list_commands()) - commands_before
    report["broker_orders_created"] = len(store.list_results()) - results_before
    report["order_requests_created"] = len(demo_oms.load_order_requests()) - oms_before
    report["broker_orders_modified"] = 0
    report["broker_orders_closed"] = 0
    return report


@app.post("/decision-engine/reset")
def decision_engine_reset() -> dict[str, Any]:
    return decision_engine.reset()


@app.get("/commands")
def list_commands() -> list[dict[str, Any]]:
    return store.list_commands()


@app.get("/commands/open")
def list_open_commands() -> list[dict[str, Any]]:
    return store.list_open_commands()


@app.get("/commands/{command_id}")
def get_command(command_id: str) -> dict[str, Any]:
    command = store.get_command(command_id)
    if command is None:
        raise HTTPException(status_code=404, detail="Command not found.")
    return command


@app.post("/commands/{command_id}/cancel")
def cancel_command(command_id: str) -> dict[str, Any]:
    ok = store.cancel_command(command_id)
    if not ok:
        command = store.get_command(command_id)
        if command is None:
            raise HTTPException(status_code=404, detail="Command not found.")
        raise HTTPException(status_code=400, detail="Only QUEUED commands can be cancelled.")
    return {"ok": True, "command_id": command_id, "status": "CANCELLED"}


@app.get("/execution/results")
def execution_results() -> list[dict[str, Any]]:
    return store.list_results()


@app.get("/results")
def list_results() -> list[dict[str, Any]]:
    return execution_results()


@app.get("/risk/status")
def risk_status() -> dict[str, Any]:
    snapshot = store.latest_snapshot()
    reasons: list[str] = []
    account: dict[str, Any] = {}
    tick: dict[str, Any] = {}
    positions: list[Any] = []
    spread_points: Optional[float] = None
    equity: Optional[float] = None
    balance: Optional[float] = None

    if snapshot is None:
        reasons.append("account snapshot missing")
        reasons.append("tick missing")
        reasons.append("spread missing")
    else:
        account = as_dict(snapshot.get("account"))
        tick = as_dict(snapshot.get("tick"))
        positions = as_list(snapshot.get("positions"))
        spread_points = as_float(tick.get("spread_points"))
        equity = as_float(account.get("equity"))
        balance = as_float(account.get("balance"))

        if not account:
            reasons.append("account snapshot missing")
        if not tick:
            reasons.append("tick missing")
        if spread_points is None:
            reasons.append("spread missing")
        elif spread_points > risk_config.max_spread_points:
            reasons.append(f"spread {spread_points} exceeds max_spread_points {risk_config.max_spread_points}")
        if len(positions) >= risk_config.max_open_positions:
            reasons.append(f"open positions {len(positions)} reached max_open_positions {risk_config.max_open_positions}")

    if not risk_config.enabled:
        reasons = []

    return {
        "enabled": risk_config.enabled,
        "latest_snapshot": {
            "terminal_id": snapshot.get("terminal_id") if snapshot else None,
            "received_at": snapshot.get("received_at") if snapshot else None,
            "symbol": tick.get("symbol") if tick else None,
            "equity": equity,
            "balance": balance,
        },
        "spread_points": spread_points,
        "open_positions": len(positions),
        "can_trade": len(reasons) == 0,
        "reasons": reasons,
        "config": risk_config.model_dump(),
    }


@app.get("/risk/decisions")
def risk_decisions() -> list[dict[str, Any]]:
    return store.list_risk_decisions()


@app.get("/strategy/status")
def strategy_status() -> dict[str, Any]:
    return strategy_engine.status(store.latest_snapshot(), store.list_strategy_signals())


@app.get("/strategy/signals")
def strategy_signals() -> list[dict[str, Any]]:
    return store.list_strategy_signals()


@app.post("/strategy/evaluate")
def evaluate_strategy() -> dict[str, Any]:
    signal = strategy_engine.evaluate(
        snapshot=store.latest_snapshot(),
        previous_signals=store.list_strategy_signals(),
    )
    store.add_strategy_signal(signal.model_dump())
    return signal.model_dump()


@app.post("/strategy/reset-signals")
def reset_strategy_signals() -> dict[str, Any]:
    store.reset_strategy_signals()
    return {"ok": True, "signals": 0}


def current_context() -> dict[str, Any]:
    latest = context_engine.latest()
    if latest is not None:
        return latest
    context = context_engine.evaluate(
        snapshot=store.latest_snapshot(),
        recorded_candles=market_recorder.list_candles(),
        market_quality=market_recorder.quality(),
    )
    context_engine.store(context)
    return context.model_dump()


def evaluate_xauusd_paper_v1_signal() -> dict[str, Any]:
    signal = evaluate_xauusd_paper_v1(
        snapshot=store.latest_snapshot(),
        context=current_context(),
        candles=market_recorder.list_candles(),
        previous_signals=store.list_strategy_signals(),
        config=xauusd_paper_v1_config,
    )
    store.add_strategy_signal(signal.model_dump())
    return signal.model_dump()


def evaluate_xauusd_paper_v2_signal() -> dict[str, Any]:
    signal = evaluate_xauusd_paper_v2(
        snapshot=store.latest_snapshot(),
        context=current_context(),
        candles=market_recorder.list_candles(),
        market_quality=market_recorder.quality(),
        previous_signals=store.list_strategy_signals(),
        config=xauusd_paper_v2_config,
    )
    data = signal.model_dump()
    data["command_id"] = None
    store.add_strategy_signal(data)
    return data


@app.post("/strategy/evaluate-paper-v1")
def strategy_evaluate_paper_v1() -> dict[str, Any]:
    return evaluate_xauusd_paper_v1_signal()


@app.post("/strategy/evaluate-paper-v2")
def strategy_evaluate_paper_v2() -> dict[str, Any]:
    return evaluate_xauusd_paper_v2_signal()


@app.get("/paper/status")
def paper_status() -> dict[str, Any]:
    return paper_engine.status(store.latest_snapshot(), paper_ledger.list_trades())


@app.get("/paper/trades")
def paper_trades() -> list[dict[str, Any]]:
    return paper_ledger.list_trades()


@app.get("/paper/open")
def paper_open_trades() -> list[dict[str, Any]]:
    return paper_ledger.list_open_trades()


@app.get("/paper-risk-audit/status")
def paper_risk_audit_status() -> dict[str, Any]:
    return paper_risk_audit_store.status()


@app.get("/paper-risk-audit/latest")
def paper_risk_audit_latest() -> dict[str, Any]:
    latest = paper_risk_audit_store.latest()
    if latest is None:
        raise HTTPException(status_code=404, detail="No paper risk decision yet.")
    return latest


@app.get("/paper-risk-audit/history")
def paper_risk_audit_history(limit: int = Query(20, ge=1, le=500)) -> dict[str, Any]:
    return {"items": paper_risk_audit_store.history(limit), "limit": limit, "safety": paper_risk_audit_store.status().get("safety")}


@app.post("/paper-risk-audit/reset")
def paper_risk_audit_reset() -> dict[str, Any]:
    paper_risk_audit_store.reset()
    return {"ok": True, "decision_count": 0, "history_count": 0}


def persist_paper_risk_result(signal: Any, trade: Any, result: dict[str, Any]) -> None:
    decision = result.get("paper_risk_decision")
    if not isinstance(decision, dict):
        return
    paper_risk_audit_store.add_decision(decision)
    updates = {
        "paper_risk_checked": True,
        "paper_risk_decision_id": decision.get("id"),
        "paper_risk_status": decision.get("risk_status"),
        "paper_risk_checked_at": decision.get("created_at"),
        "risk_check_source": "PAPER_ENGINE_SIMULATION",
    }
    signal_id = getattr(signal, "id", None)
    if signal_id:
        store.update_strategy_signal(signal_id, updates)
    for key, value in updates.items():
        try:
            setattr(signal, key, value)
        except Exception:
            pass
    if trade is not None:
        trade.risk_decision_id = decision.get("id")


@app.post("/paper/evaluate-signal")
def paper_evaluate_signal() -> dict[str, Any]:
    signal = strategy_engine.evaluate(
        snapshot=store.latest_snapshot(),
        previous_signals=store.list_strategy_signals(),
    )
    store.add_strategy_signal(signal.model_dump())
    trade, result = paper_engine.create_from_signal(
        signal=signal,
        snapshot=store.latest_snapshot(),
        open_trades=paper_ledger.list_open_trades(),
        previous_risk_decisions=store.list_risk_decisions(),
    )
    persist_paper_risk_result(signal, trade, result)
    if trade is not None:
        trade.provenance = runtime_provenance_metadata("paper_trading", "aurix_bridge_server.main.paper_evaluate_signal")
        paper_ledger.add_trade(trade)
    return result


@app.post("/paper/evaluate-paper-v1")
def paper_evaluate_paper_v1() -> dict[str, Any]:
    signal_data = evaluate_xauusd_paper_v1_signal()
    from aurix_strategy_engine.models import StrategySignal

    signal = StrategySignal(**signal_data)
    trade, result = paper_engine.create_from_signal(
        signal=signal,
        snapshot=store.latest_snapshot(),
        open_trades=paper_ledger.list_open_trades(),
        previous_risk_decisions=store.list_risk_decisions(),
    )
    persist_paper_risk_result(signal, trade, result)
    if trade is not None:
        trade.provenance = runtime_provenance_metadata("paper_trading", "aurix_bridge_server.main.paper_evaluate_paper_v1")
        paper_ledger.add_trade(trade)
    return result


@app.post("/paper/evaluate-paper-v2")
def paper_evaluate_paper_v2() -> dict[str, Any]:
    signal_data = evaluate_xauusd_paper_v2_signal()
    from aurix_strategy_engine.models import StrategySignal

    signal = StrategySignal(**signal_data)
    trade, result = paper_engine.create_from_signal(
        signal=signal,
        snapshot=store.latest_snapshot(),
        open_trades=paper_ledger.list_open_trades(),
        previous_risk_decisions=store.list_risk_decisions(),
    )
    persist_paper_risk_result(signal, trade, result)
    if trade is not None:
        trade.provenance = runtime_provenance_metadata("paper_trading", "aurix_bridge_server.main.paper_evaluate_paper_v2")
        paper_ledger.add_trade(trade)
    return result


@app.post("/paper/update")
def paper_update() -> dict[str, Any]:
    trades, updated = paper_engine.update_open_trades(store.latest_snapshot(), paper_ledger.list_trades())
    paper_ledger.save_trades(trades)
    return {"ok": True, "updated": updated, "open": paper_ledger.list_open_trades()}


@app.post("/paper/close/{paper_trade_id}")
def paper_close(paper_trade_id: str) -> dict[str, Any]:
    trades = paper_ledger.list_trades()
    for trade in trades:
        if trade.get("id") == paper_trade_id:
            if trade.get("status") != "OPEN":
                raise HTTPException(status_code=400, detail="Only OPEN paper trades can be closed manually.")
            closed = paper_engine.close_manual(trade, store.latest_snapshot())
            paper_ledger.save_trades(trades)
            return {"ok": True, "paper_trade": closed}
    raise HTTPException(status_code=404, detail="Paper trade not found.")


@app.post("/paper/reset")
def paper_reset() -> dict[str, Any]:
    paper_ledger.reset()
    return {"ok": True, "trades": 0}


@app.get("/market/status")
def market_status() -> dict[str, Any]:
    return market_recorder.status()


@app.get("/market/ticks")
def market_ticks() -> list[dict[str, Any]]:
    return market_recorder.list_ticks()


@app.get("/market/candles")
def market_candles() -> list[dict[str, Any]]:
    return market_recorder.list_candles()


@app.get("/market/quality")
def market_quality() -> dict[str, Any]:
    return market_recorder.quality()


@app.post("/market/reset")
def market_reset() -> dict[str, Any]:
    market_recorder.reset()
    return {"ok": True, "ticks": 0, "candles": 0}


@app.get("/context/status")
def context_status() -> dict[str, Any]:
    return context_engine.status()


@app.get("/context/latest")
def context_latest() -> dict[str, Any]:
    latest = context_engine.latest()
    if latest is None:
        raise HTTPException(status_code=404, detail="No context snapshots yet.")
    return latest


@app.get("/context/history")
def context_history() -> list[dict[str, Any]]:
    return context_engine.history()


@app.post("/context/evaluate")
def context_evaluate() -> dict[str, Any]:
    context = context_engine.evaluate(
        snapshot=store.latest_snapshot(),
        recorded_candles=market_recorder.list_candles(),
        market_quality=market_recorder.quality(),
    )
    context_engine.store(context)
    return context.model_dump()


@app.post("/context/reset")
def context_reset() -> dict[str, Any]:
    context_engine.reset()
    return {"ok": True, "contexts": 0}


@app.get("/supervisor/status")
def supervisor_status() -> dict[str, Any]:
    return paper_supervisor.status().model_dump()


@app.post("/supervisor/run-once")
def supervisor_run_once() -> dict[str, Any]:
    return paper_supervisor.run_once().model_dump()


@app.post("/supervisor/reset")
def supervisor_reset() -> dict[str, Any]:
    return paper_supervisor.reset().model_dump()


def paper_analytics_summary() -> dict[str, Any]:
    return summary_from_report(performance_store.latest())


def _metric_subset(report: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if report is None:
        return None
    return {
        "candles_used": report.get("candles_used", 0),
        "trades": report.get("trades", 0),
        "wins": report.get("wins", 0),
        "losses": report.get("losses", 0),
        "win_rate": report.get("win_rate", 0.0),
        "total_r": report.get("total_r", 0.0),
        "expectancy_r": report.get("expectancy_r", 0.0),
        "profit_factor": report.get("profit_factor"),
        "max_consecutive_losses": report.get("max_consecutive_losses", 0),
        "warnings": report.get("warnings") or [],
    }


def build_backtest_compare(v1_report: Optional[dict[str, Any]], v2_report: Optional[dict[str, Any]]) -> dict[str, Any]:
    warnings = ["comparison is paper/research only", "low sample sizes must not be treated as profitability evidence"]
    if v1_report is None:
        warnings.append("v1 backtest report missing; run POST /backtest/run")
    if v2_report is None:
        warnings.append("v2 backtest report missing; run POST /backtest/run-v2")
    v1 = _metric_subset(v1_report)
    v2 = _metric_subset(v2_report)
    return {
        "v1": v1,
        "v2": v2,
        "delta": {
            "trades": (v2["trades"] - v1["trades"]) if v1 and v2 else None,
            "win_rate": round(v2["win_rate"] - v1["win_rate"], 6) if v1 and v2 else None,
            "total_r": round(v2["total_r"] - v1["total_r"], 6) if v1 and v2 else None,
            "expectancy_r": round(v2["expectancy_r"] - v1["expectancy_r"], 6) if v1 and v2 else None,
        },
        "warnings": warnings,
        "safety": {
            "paper_research_only": True,
            "no_mt5_execution": True,
            "commands_queued": False,
            "external_llm_used": False,
        },
    }


@app.get("/analytics/paper")
def analytics_paper() -> dict[str, Any]:
    return performance_store.latest().model_dump()


@app.post("/analytics/paper/generate")
def analytics_paper_generate() -> dict[str, Any]:
    trades, signals, contexts, quality = performance_store.read_inputs()
    report = generate_paper_performance_report(trades, signals, contexts, quality)
    performance_store.save(report)
    return report.model_dump()


@app.get("/analytics/paper/summary")
def analytics_paper_summary() -> dict[str, Any]:
    return paper_analytics_summary()


@app.get("/journal/status")
def journal_status() -> dict[str, Any]:
    return journal_store.status()


@app.get("/journal/entries")
def journal_entries() -> list[dict[str, Any]]:
    return journal_store.list_entries()


@app.post("/journal/review-paper-trades")
def journal_review_paper_trades() -> dict[str, Any]:
    trades, signals, contexts, quality, _ = journal_store.read_inputs()
    entries = journal_reviewer.review_paper_trades(trades, signals, contexts, quality)
    saved = journal_store.upsert_entries(entries)
    return {"ok": True, "paper_trade_reviews": len(saved), "entries": saved}


@app.post("/journal/review-signals")
def journal_review_signals() -> dict[str, Any]:
    trades, signals, contexts, quality, _ = journal_store.read_inputs()
    entries = journal_reviewer.review_signals(signals, trades, contexts, quality)
    saved = journal_store.upsert_entries(entries)
    return {"ok": True, "signal_reviews": len(saved), "entries": saved}


@app.post("/journal/generate-daily-summary")
def journal_generate_daily_summary() -> dict[str, Any]:
    trades, signals, _, quality, analytics_report = journal_store.read_inputs()
    entry = journal_reviewer.daily_summary(trades, signals, analytics_report, quality)
    saved = journal_store.upsert_entries([entry])
    return {"ok": True, "entry": saved[0] if saved else entry.model_dump()}


@app.post("/journal/reset")
def journal_reset() -> dict[str, Any]:
    journal_store.reset()
    return {"ok": True, "entries": 0}


@app.get("/ai-review/status")
def ai_review_status() -> dict[str, Any]:
    return ai_review_store.status()


@app.get("/ai-review/reports")
def ai_review_reports() -> list[dict[str, Any]]:
    return ai_review_store.list_reports()


@app.get("/ai-review/latest")
def ai_review_latest() -> dict[str, Any]:
    latest = ai_review_store.latest()
    if latest is None:
        raise HTTPException(status_code=404, detail="No AI review reports yet.")
    return latest


@app.post("/ai-review/generate")
def ai_review_generate() -> dict[str, Any]:
    report = ai_review_reviewer.generate(ai_review_store.read_inputs())
    ai_review_store.save(report)
    return report.model_dump()


@app.post("/ai-review/reset")
def ai_review_reset() -> dict[str, Any]:
    ai_review_store.reset()
    return {"ok": True, "reports": 0}


@app.get("/backtest/status")
def backtest_status() -> dict[str, Any]:
    return backtest_store.status()


@app.get("/backtest/report")
def backtest_report() -> dict[str, Any]:
    report = backtest_store.latest_report()
    if report is None:
        raise HTTPException(status_code=404, detail="No backtest report yet.")
    return report.model_dump()


@app.get("/backtest/trades")
def backtest_trades() -> list[dict[str, Any]]:
    return backtest_store.list_trades()


@app.post("/backtest/run")
def backtest_run() -> dict[str, Any]:
    report, trades = backtest_engine.run(backtest_store.load_candles())
    backtest_store.save(report, trades)
    return report.model_dump()


@app.post("/backtest/run-v2")
def backtest_run_v2() -> dict[str, Any]:
    report, trades = backtest_v2_engine.run(backtest_store.load_candles())
    backtest_v2_store.save(report, trades)
    return report.model_dump()


@app.get("/backtest/compare-v1-v2")
def backtest_compare_v1_v2() -> dict[str, Any]:
    v1 = backtest_store.latest_report()
    v2 = backtest_v2_store.latest_report()
    return build_backtest_compare(v1.model_dump() if v1 else None, v2.model_dump() if v2 else None)


@app.post("/backtest/reset")
def backtest_reset() -> dict[str, Any]:
    backtest_store.reset()
    backtest_v2_store.reset()
    return {"ok": True, "trades": 0}


@app.get("/research/status")
def research_status() -> dict[str, Any]:
    return research_store.status()


@app.get("/research/latest")
def research_latest() -> dict[str, Any]:
    latest = research_store.latest()
    if latest is None:
        raise HTTPException(status_code=404, detail="No research run yet.")
    return latest.model_dump()


@app.post("/research/run-sweep")
def research_run_sweep() -> dict[str, Any]:
    return research_store.run_sweep().model_dump()


@app.post("/research/reset")
def research_reset() -> dict[str, Any]:
    research_store.reset()
    return {"ok": True, "results": 0}


@app.get("/evidence/status")
def evidence_status() -> dict[str, Any]:
    return evidence_gate_store.status()


@app.get("/evidence/latest")
def evidence_latest() -> dict[str, Any]:
    latest = evidence_gate_store.latest()
    if latest is None:
        raise HTTPException(status_code=404, detail="No evidence gate report yet.")
    return latest.model_dump()


def evidence_latest_or_empty() -> dict[str, Any]:
    latest = evidence_gate_store.latest()
    return latest.model_dump() if latest else {}


@app.post("/evidence/evaluate")
def evidence_evaluate() -> dict[str, Any]:
    status = _build_operator_status(include_evidence=False)
    summary = build_operator_summary(status).model_dump()
    report = evidence_gate_store.evaluate(evidence_gate_store.read_inputs(status.model_dump(), summary))
    return report.model_dump()


@app.post("/evidence/reset")
def evidence_reset() -> dict[str, Any]:
    evidence_gate_store.reset()
    return {"ok": True, "report": None}


def _daemon_supervisor_run_once() -> dict[str, Any]:
    old_config = paper_supervisor.config
    paper_supervisor.config = old_config.model_copy(
        update={
            "run_context": daemon_config.run_context,
            "run_strategy": daemon_config.run_paper_strategy,
            "run_paper_trading": daemon_config.run_paper_update,
            "allow_command_queueing": daemon_config.allow_command_queueing,
            "mode": daemon_config.mode,
        }
    )
    try:
        return paper_supervisor.run_once().model_dump()
    finally:
        paper_supervisor.config = old_config


def _daemon_generate_analytics() -> dict[str, Any]:
    trades, signals, contexts, quality = performance_store.read_inputs()
    report = generate_paper_performance_report(trades, signals, contexts, quality)
    performance_store.save(report)
    return report.model_dump()


def _daemon_update_journal() -> dict[str, Any]:
    trades, signals, contexts, quality, analytics_report = journal_store.read_inputs()
    paper_entries = journal_reviewer.review_paper_trades(trades, signals, contexts, quality)
    signal_entries = journal_reviewer.review_signals(signals, trades, contexts, quality)
    daily_entry = journal_reviewer.daily_summary(trades, signals, analytics_report, quality)
    saved = journal_store.upsert_entries([*paper_entries, *signal_entries, daily_entry])
    return {"entries": len(saved), "updated_at": utc_now_iso()}


def _daemon_generate_ai_review() -> dict[str, Any]:
    if daemon_config.allow_external_llm or ai_review_config.allow_external_llm:
        return {"errors": ["external LLM use is disabled for daemon"]}
    report = ai_review_reviewer.generate(ai_review_store.read_inputs())
    ai_review_store.save(report)
    return report.model_dump()


def _daemon_evaluate_evidence() -> dict[str, Any]:
    status = _build_operator_status(include_evidence=False)
    summary = build_operator_summary(status).model_dump()
    report = evidence_gate_store.evaluate(evidence_gate_store.read_inputs(status.model_dump(), summary))
    return report.model_dump()


def _daemon_command_count() -> int:
    return len(store.list_commands())


daemon_runner = PaperDaemonRunner(
    DATA_DIR,
    daemon_config,
    supervisor_run_once=_daemon_supervisor_run_once,
    generate_analytics=_daemon_generate_analytics,
    update_journal=_daemon_update_journal,
    generate_ai_review=_daemon_generate_ai_review,
    evaluate_evidence=_daemon_evaluate_evidence,
    command_count=_daemon_command_count,
)


async def _daemon_loop() -> None:
    try:
        while daemon_runner.is_running():
            daemon_runner.run_once()
            await asyncio.sleep(max(float(daemon_config.interval_seconds), 0.1))
    finally:
        if daemon_runner.is_running():
            daemon_runner.mark_stopped()


@app.get("/daemon/status")
def daemon_status() -> dict[str, Any]:
    return daemon_runner.status().model_dump()


@app.post("/daemon/run-once")
def daemon_run_once() -> dict[str, Any]:
    return daemon_runner.run_once().model_dump()


@app.post("/daemon/start")
async def daemon_start() -> dict[str, Any]:
    global daemon_task
    if daemon_task is not None and not daemon_task.done():
        return daemon_runner.status().model_dump()
    status = daemon_runner.mark_started()
    daemon_task = asyncio.create_task(_daemon_loop())
    return status.model_dump()


@app.post("/daemon/stop")
async def daemon_stop() -> dict[str, Any]:
    global daemon_task
    status = daemon_runner.mark_stopped()
    if daemon_task is not None and not daemon_task.done():
        daemon_task.cancel()
        try:
            await daemon_task
        except asyncio.CancelledError:
            pass
    daemon_task = None
    return status.model_dump()


@app.post("/daemon/reset")
def daemon_reset() -> dict[str, Any]:
    return daemon_runner.reset().model_dump()


@app.get("/forward-test/status")
def forward_test_status() -> dict[str, Any]:
    return forward_test_store.status()


@app.post("/forward-test/start")
def forward_test_start() -> dict[str, Any]:
    return forward_test_store.start().model_dump()


@app.post("/forward-test/update")
def forward_test_update() -> dict[str, Any]:
    status = _build_operator_status(include_evidence=True, include_forward_test=False)
    summary = build_operator_summary(status).model_dump()
    return forward_test_store.update(forward_test_store.read_inputs(summary)).model_dump()


@app.post("/forward-test/pause")
def forward_test_pause() -> dict[str, Any]:
    return forward_test_store.pause().model_dump()


@app.post("/forward-test/reset")
def forward_test_reset() -> dict[str, Any]:
    forward_test_store.reset()
    return {"ok": True, "campaign": None}


def _orchestrator_evaluate_context() -> dict[str, Any]:
    context = context_engine.evaluate(
        snapshot=store.latest_snapshot(),
        recorded_candles=market_recorder.list_candles(),
        market_quality=market_recorder.quality(),
    )
    context_engine.store(context)
    return context.model_dump()


def _orchestrator_operator_summary() -> dict[str, Any]:
    status = _build_operator_status(include_evidence=True, include_forward_test=True, include_orchestrator=False)
    return build_operator_summary(status).model_dump()


def _orchestrator_forward_update() -> dict[str, Any]:
    summary = _orchestrator_operator_summary()
    return forward_test_store.update(forward_test_store.read_inputs(summary)).model_dump()


def _orchestrator_daemon_stop() -> dict[str, Any]:
    daemon_runner.mark_stopped()
    return daemon_runner.status().model_dump()


def _long_forward_operator_status() -> dict[str, Any]:
    return _build_operator_status(include_evidence=True, include_long_forward_test=False).model_dump()


def _long_forward_operator_summary() -> dict[str, Any]:
    status = _build_operator_status(include_evidence=True, include_long_forward_test=False)
    return build_operator_summary(status).model_dump()


def _long_forward_orchestrator_start() -> dict[str, Any]:
    return orchestrator.mark_started().model_dump()


def _long_forward_orchestrator_stop() -> dict[str, Any]:
    return orchestrator.mark_stopped().model_dump()


def _long_forward_daemon_start() -> dict[str, Any]:
    return daemon_runner.mark_started().model_dump()


orchestrator = SessionOrchestrator(
    DATA_DIR,
    orchestrator_config,
    evaluate_context=_orchestrator_evaluate_context,
    daemon_run_once=lambda: daemon_runner.run_once().model_dump(),
    daemon_stop=_orchestrator_daemon_stop,
    daemon_status=lambda: daemon_runner.status().model_dump(),
    update_forward_test=_orchestrator_forward_update,
    evaluate_evidence=_daemon_evaluate_evidence,
    generate_analytics=_daemon_generate_analytics,
    generate_journal=_daemon_update_journal,
    generate_ai_review=_daemon_generate_ai_review,
    operator_summary=_orchestrator_operator_summary,
    command_count=_daemon_command_count,
)

long_forward_manager = LongForwardTestManager(
    DATA_DIR,
    long_forward_config,
    operator_status=_long_forward_operator_status,
    operator_summary=_long_forward_operator_summary,
    orchestrator_status=lambda: orchestrator.status().model_dump(),
    orchestrator_start=_long_forward_orchestrator_start,
    orchestrator_stop=_long_forward_orchestrator_stop,
    orchestrator_run_once=lambda: orchestrator.run_once().model_dump(),
    daemon_status=lambda: daemon_runner.status().model_dump(),
    daemon_start=_long_forward_daemon_start,
    forward_test_status=lambda: forward_test_store.status(),
    update_forward_test=_orchestrator_forward_update,
    generate_analytics=_daemon_generate_analytics,
    analytics_summary=paper_analytics_summary,
    generate_journal=_daemon_update_journal,
    journal_status=journal_status,
    generate_ai_review=_daemon_generate_ai_review,
    ai_review_latest=lambda: ai_review_store.latest() or {},
    evaluate_evidence=_daemon_evaluate_evidence,
    evidence_latest=evidence_latest_or_empty,
    market_quality=market_quality,
    paper_status=paper_status,
    paper_trades=paper_trades,
    command_count=_daemon_command_count,
)


async def _orchestrator_loop() -> None:
    try:
        while orchestrator.is_running():
            orchestrator.run_once()
            await asyncio.sleep(max(float(orchestrator_config.interval_seconds), 0.1))
    finally:
        if orchestrator.is_running():
            orchestrator.mark_stopped()


async def _long_forward_loop() -> None:
    try:
        while long_forward_manager.is_running():
            long_forward_manager.run_once()
            await asyncio.sleep(max(float(long_forward_config.orchestrator_interval_seconds), 0.1))
    finally:
        if long_forward_manager.is_running():
            long_forward_manager.mark_stopped()


@app.get("/orchestrator/status")
def orchestrator_status() -> dict[str, Any]:
    return orchestrator.status().model_dump()


@app.post("/orchestrator/run-once")
def orchestrator_run_once() -> dict[str, Any]:
    return orchestrator.run_once().model_dump()


@app.post("/orchestrator/start")
async def orchestrator_start() -> dict[str, Any]:
    global orchestrator_task
    if orchestrator_task is not None and not orchestrator_task.done():
        return orchestrator.status().model_dump()
    status = orchestrator.mark_started()
    orchestrator_task = asyncio.create_task(_orchestrator_loop())
    return status.model_dump()


@app.post("/orchestrator/stop")
async def orchestrator_stop() -> dict[str, Any]:
    global orchestrator_task
    status = orchestrator.mark_stopped()
    if orchestrator_task is not None and not orchestrator_task.done():
        orchestrator_task.cancel()
        try:
            await orchestrator_task
        except asyncio.CancelledError:
            pass
    orchestrator_task = None
    return status.model_dump()


@app.post("/orchestrator/reset")
def orchestrator_reset() -> dict[str, Any]:
    return orchestrator.reset().model_dump()


@app.get("/long-forward-test/status")
def long_forward_test_status() -> dict[str, Any]:
    return long_forward_manager.status().model_dump()


@app.post("/long-forward-test/run-once")
def long_forward_test_run_once() -> dict[str, Any]:
    return long_forward_manager.run_once().model_dump()


@app.post("/long-forward-test/start")
async def long_forward_test_start() -> dict[str, Any]:
    global long_forward_task
    status = long_forward_manager.mark_started()
    if long_forward_task is None or long_forward_task.done():
        long_forward_task = asyncio.create_task(_long_forward_loop())
    return status.model_dump()


@app.post("/long-forward-test/stop")
async def long_forward_test_stop() -> dict[str, Any]:
    global long_forward_task
    status = long_forward_manager.mark_stopped()
    if long_forward_task is not None and not long_forward_task.done():
        long_forward_task.cancel()
        try:
            await long_forward_task
        except asyncio.CancelledError:
            pass
    long_forward_task = None
    return status.model_dump()


@app.post("/long-forward-test/daily-report")
def long_forward_test_daily_report() -> dict[str, Any]:
    return long_forward_manager.generate_daily_report().model_dump()


@app.post("/long-forward-test/reset")
def long_forward_test_reset() -> dict[str, Any]:
    return long_forward_manager.reset().model_dump()


def _build_operator_status(
    *,
    include_evidence: bool,
    include_forward_test: bool = True,
    include_orchestrator: bool = True,
    include_long_forward_test: bool = True,
    include_live_readiness: bool = True,
    include_evidence_growth: bool = True,
    include_signal_certification: bool = True,
) -> Any:
    return build_operator_status(
        service="aurix-mac-wine-bridge",
        terminal_id=DEFAULT_TERMINAL_ID,
        store=store,
        market_recorder=market_recorder,
        market_config=market_config,
        context_engine=context_engine,
        risk_status=risk_status(),
        strategy_status=strategy_status(),
        paper_status=paper_status(),
        paper_risk_audit_status=paper_risk_audit_status(),
        supervisor_status=supervisor_status(),
        analytics_summary=paper_analytics_summary(),
        journal_status=journal_status(),
        ai_review_status=ai_review_status(),
        backtest_status=backtest_status(),
        research_status=research_status(),
        evidence_status=evidence_status() if include_evidence else {},
        daemon_status=daemon_status(),
        forward_test_status=forward_test_status() if include_forward_test else {},
        orchestrator_status=orchestrator_status() if include_orchestrator else {},
        long_forward_test_status=long_forward_test_status() if include_long_forward_test else {},
        live_readiness_status=live_readiness_status() if include_live_readiness else {},
        evidence_growth_status=evidence_monitor_status() if include_evidence_growth else {},
        signal_certification_status=signal_certifier_status() if include_signal_certification else {},
        event_bus_status=event_bus_operator_status(),
        strategy_agents_status=strategy_agents_operator_status(),
        demo_oms_status=demo_oms_status(),
        broker_reconciliation_status=broker_reconciliation_status(),
        demo_command_queue_status=demo_command_queue_status(),
        demo_broker_execution_status=demo_broker_execution_status(),
        decision_engine_status=decision_engine_status(),
        runtime_environment=runtime_environment_payload(),
        quick_validation_status=quick_validation_status(),
        runtime_provenance=runtime_session.payload(),
        evidence_integrity_status=evidence_integrity_payload(),
        backtest_compare_v1_v2=build_backtest_compare(
            backtest_store.latest_report().model_dump() if backtest_store.latest_report() else None,
            backtest_v2_store.latest_report().model_dump() if backtest_v2_store.latest_report() else None,
        ),
    )


def event_bus_operator_status() -> dict[str, Any]:
    status = event_bus.get_latest_status()
    state = event_bus.get_latest_state()
    return {
        **status,
        "runtime_state_generated_at": state.get("generated_at"),
        "runtime_state": {
            "generated_at": state.get("generated_at"),
            "last_sequence": state.get("last_sequence"),
            "last_event_id": state.get("last_event_id"),
            "safety": state.get("safety") or {},
        },
    }


def strategy_agents_operator_status() -> dict[str, Any]:
    status = strategy_agent_evaluator.status()
    latest = strategy_agent_evaluator.latest()
    latest_signal = next((item for item in reversed(latest) if item.get("status") == "SIGNAL"), None)
    latest_fast_rsi = next((item for item in reversed(latest) if item.get("agent_id") == "fast_rsi_first_reversal_v1"), None)
    latest_blackcat = next((item for item in reversed(latest) if item.get("agent_id") == "blackcat_cloud_v1" or item.get("strategy_name") == "blackcat_cloud_v1"), None)
    return {**status, "latest": latest, "latest_signal": latest_signal, "latest_fast_rsi": latest_fast_rsi, "latest_blackcat_cloud_v1": latest_blackcat}


def operator_status_payload() -> dict[str, Any]:
    return _build_operator_status(include_evidence=True).model_dump()


def evidence_integrity_payload() -> dict[str, Any]:
    try:
        return build_evidence_integrity_status(DATA_DIR)
    except Exception as exc:
        logger.exception("evidence integrity status degraded after unexpected read failure")
        return {
            "generated_at": utc_now_iso(),
            "status": "ERROR",
            "paper_ledger": {"status": "ERROR", "note": str(exc)},
            "journal_ledger": {"status": "ERROR", "note": str(exc)},
            "evidence_monitor": {"status": "ERROR", "note": str(exc)},
            "live_readiness": {"status": "ERROR", "note": str(exc)},
            "signal_certification": {"status": "ERROR", "note": str(exc)},
            "stale_temp_files": [],
            "stale_temp_file_count": 0,
            "corrupt_json_files": [],
            "corrupt_json_file_count": 0,
            "counts_consistent": False,
            "notes": [str(exc)],
            "safety": {
                "read_only_check": True,
                "paper_trade_created": False,
                "order_request_created": False,
                "mt5_command_queued": False,
                "broker_order_created": False,
            },
        }


@app.get("/operator/status")
def operator_status() -> dict[str, Any]:
    try:
        return operator_status_payload()
    except Exception as exc:
        logger.exception("operator status degraded after unexpected runtime status failure")
        summary = build_runtime_dashboard_summary(
            DATA_DIR,
            runtime_provenance=runtime_session.payload(),
            evidence_integrity=evidence_integrity_payload(),
            runtime_environment=runtime_environment_payload(),
        ).model_dump(mode="json")
        return {"degraded": True, "error": str(exc), "runtime_summary": summary, "safety": summary.get("safety", {})}


@app.get("/operator/summary")
def operator_summary() -> dict[str, Any]:
    try:
        status = _build_operator_status(include_evidence=True)
        return build_operator_summary(status).model_dump()
    except Exception as exc:
        logger.exception("operator summary degraded after unexpected runtime status failure")
        summary = build_runtime_dashboard_summary(
            DATA_DIR,
            runtime_provenance=runtime_session.payload(),
            evidence_integrity=evidence_integrity_payload(),
            runtime_environment=runtime_environment_payload(),
        ).model_dump(mode="json")
        return {
            "degraded": True,
            "error": str(exc),
            "symbol": summary.get("symbol"),
            "mode": (summary.get("decision") or {}).get("mode"),
            "health": summary.get("health"),
            "warnings": summary.get("top_warnings", []),
            "blocking_reasons": summary.get("top_blocks", []),
            "safety": summary.get("safety", {}),
        }


@app.get("/evidence-integrity/status")
def evidence_integrity_status() -> dict[str, Any]:
    return evidence_integrity_payload()


@app.get("/live-readiness/status")
def live_readiness_status() -> dict[str, Any]:
    return live_readiness_store.status()


@app.get("/live-readiness/latest")
def live_readiness_latest() -> dict[str, Any]:
    latest = live_readiness_store.latest()
    if latest is None:
        raise HTTPException(status_code=404, detail="No live readiness report yet.")
    return latest.model_dump()


def live_readiness_latest_or_empty() -> dict[str, Any]:
    latest = live_readiness_store.latest()
    return latest.model_dump() if latest else {}


@app.post("/live-readiness/evaluate")
def live_readiness_evaluate() -> dict[str, Any]:
    status = _build_operator_status(include_evidence=True, include_live_readiness=False)
    summary = build_operator_summary(status).model_dump()
    report = live_readiness_store.evaluate(live_readiness_store.read_inputs(status.model_dump(), summary))
    return report.model_dump()


@app.get("/live-readiness/manual-checklist")
def live_readiness_manual_checklist() -> dict[str, Any]:
    return live_readiness_store.manual_checklist()


@app.post("/live-readiness/reset")
def live_readiness_reset() -> dict[str, Any]:
    live_readiness_store.reset()
    return {"ok": True, "latest_exists": False}


@app.get("/evidence-monitor/status")
def evidence_monitor_status() -> dict[str, Any]:
    return evidence_monitor_store.status()


@app.get("/evidence-monitor/latest")
def evidence_monitor_latest() -> dict[str, Any]:
    latest = evidence_monitor_store.latest()
    if latest is None:
        raise HTTPException(status_code=404, detail="No evidence growth report yet.")
    return latest.model_dump()


@app.post("/evidence-monitor/evaluate")
def evidence_monitor_evaluate() -> dict[str, Any]:
    status = _build_operator_status(include_evidence=True, include_evidence_growth=False)
    summary = build_operator_summary(status).model_dump()
    report = evidence_monitor_store.evaluate(evidence_monitor_store.read_inputs(status.model_dump(), summary))
    return report.model_dump()


@app.get("/evidence-monitor/history")
def evidence_monitor_history(limit: int = Query(20, ge=1, le=500)) -> dict[str, Any]:
    return {
        "items": evidence_monitor_store.history(limit),
        "limit": limit,
        "safety": evidence_monitor_store.status().get("safety"),
    }


@app.post("/evidence-monitor/reset")
def evidence_monitor_reset() -> dict[str, Any]:
    evidence_monitor_store.reset()
    return {"ok": True, "latest_exists": False, "history_count": 0}


@app.get("/signal-certifier/status")
def signal_certifier_status() -> dict[str, Any]:
    return signal_certifier_store.status()


@app.get("/signal-certifier/latest")
def signal_certifier_latest() -> dict[str, Any]:
    latest = signal_certifier_store.latest()
    if latest is None:
        raise HTTPException(status_code=404, detail="No signal path certification report yet.")
    return latest.model_dump()


@app.post("/signal-certifier/certify")
def signal_certifier_certify() -> dict[str, Any]:
    status = _build_operator_status(include_evidence=True, include_signal_certification=False)
    summary = build_operator_summary(status).model_dump()
    report = signal_certifier_store.certify(signal_certifier_store.read_inputs(status.model_dump(), summary))
    return report.model_dump()


@app.get("/signal-certifier/history")
def signal_certifier_history(limit: int = Query(20, ge=1, le=500)) -> dict[str, Any]:
    return {"items": signal_certifier_store.history(limit), "limit": limit, "safety": signal_certifier_store.status().get("safety")}


@app.post("/signal-certifier/reset")
def signal_certifier_reset() -> dict[str, Any]:
    signal_certifier_store.reset()
    return {"ok": True, "latest_exists": False, "history_count": 0}


@app.post("/commands/open-market")
def open_market(req: OpenMarketRequest) -> Command:
    direction = req.direction.upper()
    if direction not in {"BUY", "SELL"}:
        raise HTTPException(status_code=400, detail="direction must be BUY or SELL")

    cmd = Command(
        type="OPEN_MARKET",
        terminal_id=req.terminal_id,
        symbol=req.symbol,
        direction=direction,  # type: ignore[arg-type]
        volume=req.volume,
        sl=req.sl,
        tp=req.tp,
        comment=req.comment,
        live_confirm=req.live_confirm,
        provenance=runtime_provenance_metadata("bridge_command", "aurix_bridge_server.main.open_market"),
    )

    decision = risk_governor.evaluate_open_market(
        command=cmd,
        snapshot=store.latest_snapshot(),
        previous_decisions=store.list_risk_decisions(),
    )
    store.add_risk_decision(decision.model_dump())

    if not decision.approved:
        raise HTTPException(status_code=400, detail=decision.model_dump())

    cmd.risk_decision_id = decision.id
    return store.add_command(cmd)


@app.post("/commands/close-position")
def close_position(req: ClosePositionRequest) -> Command:
    cmd = Command(
        type="CLOSE_POSITION",
        terminal_id=req.terminal_id,
        ticket=req.ticket,
        volume=req.volume,
        comment=req.comment,
        live_confirm=req.live_confirm,
        provenance=runtime_provenance_metadata("bridge_command", "aurix_bridge_server.main.close_position"),
    )
    return store.add_command(cmd)


@app.post("/commands/kill-switch")
def kill_switch(terminal_id: str = DEFAULT_TERMINAL_ID, live_confirm: Optional[str] = None) -> Command:
    cmd = Command(
        type="KILL_SWITCH",
        terminal_id=terminal_id,
        comment="AURIX-KILL",
        live_confirm=live_confirm,
        provenance=runtime_provenance_metadata("bridge_command", "aurix_bridge_server.main.kill_switch"),
    )
    return store.add_command(cmd)


@app.post("/commands/cancel/{command_id}")
def cancel(command_id: str) -> dict[str, Any]:
    ok = store.cancel_command(command_id)
    return {"ok": ok, "command_id": command_id}
