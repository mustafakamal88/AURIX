from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aurix_common import legacy_runtime_provenance

from .evidence_integrity import build_evidence_integrity_status
from .models import AurixRuntimeDashboardSummary, RuntimeDashboardSafety
from .store import RuntimeDashboardStore


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _first(items: list[Any]) -> Any:
    return items[0] if items else None


def _age_seconds(value: Any) -> float | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - parsed).total_seconds()


def _count_status(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        status = str(item.get("status") or "UNKNOWN")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _market(snapshot: dict[str, Any] | None, decision: dict[str, Any], decision_status: dict[str, Any], risk: dict[str, Any]) -> dict[str, Any]:
    tick = _dict(_dict(snapshot).get("tick"))
    candles = _list(_dict(snapshot).get("candles"))
    spread = tick.get("spread_points")
    max_spread = _dict(decision_status.get("config")).get("max_spread_points")
    if max_spread is None:
        max_spread = _dict(decision.get("market_view")).get("max_spread_points")
    if max_spread is None:
        max_spread = _dict(risk.get("config")).get("max_spread_points")
    status = "UNKNOWN"
    try:
        status = "BLOCKED" if float(spread) > float(max_spread) else "OK"
    except (TypeError, ValueError):
        pass
    return {
        "symbol": tick.get("symbol") or decision.get("symbol"),
        "bid": tick.get("bid"),
        "ask": tick.get("ask"),
        "spread_points": spread,
        "max_spread_threshold": max_spread,
        "spread_status": status,
        "latest_tick_time": tick.get("time") or _dict(snapshot).get("received_at"),
        "latest_candle_time": _dict(candles[-1]).get("time") if candles else None,
        "snapshot_age_seconds": _age_seconds(_dict(snapshot).get("received_at")),
    }


def _decision(status: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    score = report.get("score")
    blocks = _list(report.get("blocking_reasons"))
    return {
        "action": status.get("latest_action") or report.get("action"),
        "direction": status.get("latest_direction") or report.get("direction"),
        "score": status.get("score") if status.get("score") is not None else _dict(score).get("total"),
        "confidence": status.get("confidence") if status.get("confidence") is not None else report.get("confidence"),
        "strategy": status.get("strategy") or report.get("strategy"),
        "setup_reason": status.get("setup_reason") or report.get("setup_reason"),
        "top_blocking_reason": status.get("top_blocking_reason") or _dict(_first(blocks) or {}).get("message"),
        "top_warning": status.get("top_warning") or _first(_list(report.get("warnings"))),
        "autonomy_level": status.get("autonomy_level") or report.get("autonomy_level"),
        "mode": status.get("mode") or report.get("mode"),
        "status": status.get("latest_status") or report.get("status"),
        "blocking_reasons": blocks,
        "warnings": _list(report.get("warnings")),
    }


def _fast_rsi(latest: list[dict[str, Any]], state: dict[str, Any]) -> dict[str, Any]:
    item = next((row for row in reversed(latest) if row.get("strategy_name") == "fast_rsi_first_reversal"), latest[-1] if latest else {})
    trace = _dict(item.get("decision_trace"))
    indicators = _dict(trace.get("indicators"))
    return {
        "status": item.get("status"),
        "direction": item.get("direction"),
        "rsi_current": indicators.get("rsi_current") or item.get("rsi_current"),
        "rsi_sma_current": indicators.get("rsi_sma_current") or item.get("rsi_sma_current"),
        "buy_extreme_state": trace.get("buy_extreme_state") or state.get("buy_extreme_state"),
        "sell_extreme_state": trace.get("sell_extreme_state") or state.get("sell_extreme_state"),
        "rejection_reasons": _list(item.get("rejection_reasons")),
        "last_evaluated_bar": trace.get("last_evaluated_bar") or state.get("last_evaluated_bar"),
        "decision_trace_available": bool(item.get("decision_trace")),
        "setup_reason": item.get("setup_reason"),
    }


def _health(decision: dict[str, Any], event_bus: dict[str, Any], snapshot: dict[str, Any] | None, warnings: list[str]) -> str:
    action = str(decision.get("action") or "")
    if action.startswith("BLOCKED"):
        return "BLOCKED"
    event_age = _age_seconds(event_bus.get("updated_at") or event_bus.get("runtime_state_generated_at"))
    snap_age = _age_seconds(_dict(snapshot).get("received_at"))
    if (event_age is not None and event_age > 180) or (snap_age is not None and snap_age > 180):
        return "STALE"
    if warnings:
        return "WARNING"
    return "HEALTHY"


def build_runtime_dashboard_summary(
    data_dir: str | Path = "data",
    *,
    runtime_provenance: dict[str, Any] | None = None,
    evidence_integrity: dict[str, Any] | None = None,
    runtime_environment: dict[str, Any] | None = None,
) -> AurixRuntimeDashboardSummary:
    store = RuntimeDashboardStore(data_dir)
    snapshot = store.latest_snapshot()
    account_raw = _dict(_dict(snapshot).get("account"))
    decision_status = _dict(store.read_json("decision_engine/status.json", {}))
    decision_report = _dict(store.read_json("decision_engine/report.json", {}))
    risk_status = _dict(store.read_json("risk_status.json", {}))
    strategy_status = _dict(store.read_json("strategy_agents/status.json", {}))
    strategy_latest = [item for item in _list(store.read_json("strategy_agents/latest_evaluations.json", [])) if isinstance(item, dict)]
    fast_state = _dict(store.read_json("strategy_agents/fast_rsi_first_reversal_state.json", {}))
    event_bus_status = _dict(store.read_json("event_bus/status.json", {}))
    event_bus_state = _dict(store.read_json("event_bus/state_snapshot.json", {}))
    recent_events = store.read_jsonl("event_bus/events.jsonl", 20)
    demo_oms_status = _dict(store.read_json("demo_oms/status.json", {}))
    demo_oms_requests = _list(store.read_json("demo_oms/order_requests.json", []))
    demo_queue_status = _dict(store.read_json("demo_command_queue/status.json", {}))
    demo_queue_previews = _list(store.read_json("demo_command_queue/previews.json", []))
    demo_queue_payloads = _list(store.read_json("demo_command_queue/payloads.json", []))
    demo_broker_execution = _dict(store.read_json("demo_broker_execution/status.json", {}))
    broker_status = _dict(store.read_json("broker_reconciliation/status.json", {}))
    broker_report = _dict(store.read_json("broker_reconciliation/report.json", {}))
    live_readiness = _dict(store.read_json("live_readiness_report.json", {}))
    evidence_growth = _dict(store.read_json("evidence_growth_report.json", {}))
    signal_cert = _dict(store.read_json("signal_path_certification_report.json", {}))
    paper_risk = _list(store.read_json("paper_risk_decisions.json", []))
    quick_validation = _dict(store.read_json("quick_validation_report.json", {}))
    context_items = _list(store.read_json("context_snapshots.json", []))
    operator_summary = _dict(store.read_json("operator_summary.json", {}))

    decision = _decision(decision_status, decision_report)
    market = _market(snapshot, decision_report, decision_status, risk_status)
    account = {
        "currency": account_raw.get("currency"),
        "balance": account_raw.get("balance"),
        "equity": account_raw.get("equity"),
        "free_margin": account_raw.get("free_margin") or account_raw.get("margin_free"),
        "margin_level": account_raw.get("margin_level"),
        "demo_real_hint": account_raw.get("trade_mode") or account_raw.get("server") or "unknown",
        "login": account_raw.get("login"),
    }
    blocks = [str(_dict(item).get("message") or item) for item in _list(decision.get("blocking_reasons"))]
    if decision.get("top_blocking_reason") and decision.get("top_blocking_reason") not in blocks:
        blocks.insert(0, str(decision.get("top_blocking_reason")))
    warnings = [str(item) for item in _list(decision.get("warnings"))]
    if decision.get("top_warning") and decision.get("top_warning") not in warnings:
        warnings.insert(0, str(decision.get("top_warning")))
    for source in (live_readiness, evidence_growth, signal_cert):
        warnings.extend(str(item) for item in _list(source.get("warnings")))
        blocks.extend(str(_dict(item).get("message") or item) for item in _list(source.get("blocking_reasons") or source.get("failed_checks")))
    blocks = list(dict.fromkeys([item for item in blocks if item]))
    warnings = list(dict.fromkeys([item for item in warnings if item]))

    latest_payload = _dict(demo_queue_payloads[-1]) if demo_queue_payloads else {}
    latest_preview = _dict(demo_queue_previews[-1]) if demo_queue_previews else {}
    latest_request = _dict(demo_oms_requests[-1]) if demo_oms_requests else {}
    latest_decision_event = next((event for event in reversed(recent_events) if event.get("event_type") == "AURIX_DECISION_EVENT"), None)
    safety = RuntimeDashboardSafety()
    runtime_provenance = runtime_provenance or legacy_runtime_provenance(data_dir, mode=str(decision.get("mode") or "UNKNOWN"), symbol=str(market.get("symbol") or "XAUUSDm"))
    evidence_integrity = evidence_integrity or build_evidence_integrity_status(data_dir)
    runtime_environment = runtime_environment or {}
    health = _health(decision, event_bus_status, snapshot, warnings)
    if evidence_integrity.get("status") == "ERROR":
        health = "ERROR"
    elif evidence_integrity.get("status") == "WARNING" and health == "HEALTHY":
        health = "WARNING"
    primary = blocks[0] if blocks else None
    next_action = "Wait for spread to normalize and a valid Fast RSI signal." if primary else "Continue monitoring; no dashboard action is available."
    raw = _dict(_dict(snapshot).get("raw"))
    railway_broker_execution = _dict(runtime_environment).get("broker_execution_enabled")
    ea_broker_execution = raw.get("broker_execution_enabled")
    broker_matched = railway_broker_execution == ea_broker_execution if ea_broker_execution is not None and railway_broker_execution is not None else None
    latest_gate = _dict(demo_broker_execution.get("latest_gate_decision"))
    latest_command = _dict(demo_broker_execution.get("latest_command"))
    risk_model = _dict(demo_broker_execution.get("risk_model"))
    latest_v2 = next((item for item in reversed(strategy_latest) if item.get("strategy_name") == "xauusd_paper_v2"), {})
    quick_summary = _dict(quick_validation.get("summary"))
    broker_execution_cockpit = {
        "railway_broker_execution": railway_broker_execution,
        "ea_broker_execution": ea_broker_execution,
        "broker_execution_matched": broker_matched,
        "terminal_id": _dict(snapshot).get("terminal_id") or runtime_environment.get("mt5_terminal_id"),
        "symbol": market.get("symbol") or "XAUUSDm",
        "positions_count": len(_list(_dict(snapshot).get("positions"))),
        "latest_command_state": latest_command.get("status") or ("NO_COMMAND" if railway_broker_execution is False else None),
        "latest_command_reason": latest_gate.get("reason") or demo_broker_execution.get("latest_gate_block"),
        "latest_primary_block": latest_gate.get("primary_block") or demo_broker_execution.get("latest_gate_block") or primary,
        "aurix_queue_state": demo_broker_execution.get("queue_state") or latest_gate.get("queue_state"),
        "spread_gate_state": demo_broker_execution.get("spread_gate") or latest_gate.get("spread_gate") or market.get("spread_status"),
        "engine_max_spread": demo_broker_execution.get("engine_max_spread_points") or market.get("max_spread_threshold"),
        "current_spread": market.get("spread_points"),
        "risk_model": risk_model,
        "selected_strategy": demo_broker_execution.get("selected_strategy") or decision.get("strategy") or _dict(strategy_status.get("latest_signal")).get("strategy_name"),
        "latest_signal_status": latest_v2.get("status") or _dict(strategy_status.get("latest_signal")).get("status"),
        "quick_validation_status": quick_validation.get("status"),
        "quick_validation_pass_count": quick_summary.get("pass_count"),
        "quick_validation_fail_count": quick_summary.get("fail_count"),
        "quick_validation_warning_count": quick_summary.get("warning_count"),
        "evidence_status": live_readiness.get("evidence_status") or _dict(store.read_json("evidence_gate_report.json", {})).get("status"),
        "live_readiness_status": live_readiness.get("status"),
        "live_readiness_arming_allowed": bool(live_readiness.get("live_arming_allowed")),
        "live_readiness_execution_allowed": bool(live_readiness.get("live_execution_allowed")),
        "read_only_dashboard": True,
        "no_commands_from_dashboard": True,
    }

    return AurixRuntimeDashboardSummary(
        symbol=market.get("symbol") or decision_report.get("symbol") or strategy_status.get("symbol"),
        account=account,
        market=market,
        session={
            "name": _dict(context_items[-1]).get("session_name") if context_items else operator_summary.get("session"),
            "latest_context": _dict(context_items[-1]) if context_items else {},
        },
        decision=decision,
        strategy_agents={
            "registered_count": strategy_status.get("registered_count"),
            "enabled_count": strategy_status.get("enabled_count"),
            "latest_statuses": strategy_status.get("latest_status_counts") or _count_status(strategy_latest),
            "latest_signal_strategy": _dict(strategy_status.get("latest_signal")).get("strategy_name"),
            "latest_signal_direction": _dict(strategy_status.get("latest_signal")).get("direction"),
            "paper_trade_creation_allowed": False,
            "order_request_creation_allowed": False,
        },
        fast_rsi=_fast_rsi(strategy_latest, fast_state),
        event_bus={
            "event_count": event_bus_status.get("event_count"),
            "last_sequence": event_bus_status.get("last_sequence"),
            "last_event_type": event_bus_status.get("last_event_type"),
            "runtime_state_generated_at": event_bus_state.get("generated_at"),
            "latest_decision_event": latest_decision_event,
        },
        demo_oms={
            "mode": demo_oms_status.get("mode"),
            "intent_count": demo_oms_status.get("order_intent_count"),
            "request_count": demo_oms_status.get("order_request_count"),
            "latest_request_status": demo_oms_status.get("latest_request_status") or latest_request.get("status"),
            "demo_execution_allowed": False,
            "live_execution_allowed": False,
            "command_queueing_allowed": False,
        },
        demo_command_queue={
            "mode": demo_queue_status.get("mode"),
            "preview_count": demo_queue_status.get("preview_count"),
            "payload_count": demo_queue_status.get("payload_count"),
            "latest_preview_status": demo_queue_status.get("latest_preview_status") or latest_preview.get("status"),
            "latest_payload_status": demo_queue_status.get("latest_payload_status") or latest_payload.get("status"),
            "manual_demo_arm": demo_queue_status.get("manual_demo_arm"),
            "demo_command_queueing_allowed": False,
            "mt5_command_queueing_allowed": False,
            "mt5_command_id": latest_payload.get("mt5_command_id"),
            "broker_order_id": latest_payload.get("broker_order_id"),
        },
        demo_broker_execution=demo_broker_execution,
        broker_reconciliation={
            "status": broker_status.get("status") or broker_report.get("status"),
            "broker_positions": broker_status.get("broker_position_count", len(_list(broker_report.get("broker_positions")))),
            "broker_orders": broker_status.get("broker_order_count", len(_list(broker_report.get("broker_orders")))),
            "mismatches": broker_status.get("mismatch_count", len(_list(broker_report.get("mismatches")))),
            "warnings": broker_status.get("warning_count", len(_list(broker_report.get("warnings")))),
            "unexpected_exposure": bool(_list(broker_report.get("mismatches"))),
        },
        live_readiness=live_readiness,
        evidence_growth=evidence_growth,
        signal_certification=signal_cert,
        paper_risk_audit=_dict(paper_risk[-1]) if paper_risk else {},
        quick_validation=quick_validation,
        broker_execution_cockpit=broker_execution_cockpit,
        runtime_provenance=runtime_provenance,
        evidence_integrity=evidence_integrity,
        runtime_environment=runtime_environment,
        safety=safety,
        health=health,
        top_blocks=blocks[:5],
        top_warnings=warnings[:5],
        next_expected_action=next_action,
    )
