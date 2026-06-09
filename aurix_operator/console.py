from __future__ import annotations

from typing import Any

from aurix_bridge_server.models import utc_now_iso
from aurix_market_data.quality import build_quality_report

from .health import age_seconds, as_dict, as_float, as_list, read_ea_allow_live_trading
from .models import OperatorStatus, OperatorSummary


def build_operator_status(
    *,
    service: str,
    terminal_id: str,
    store: Any,
    market_recorder: Any,
    market_config: Any,
    context_engine: Any,
    risk_status: dict[str, Any],
    strategy_status: dict[str, Any],
    paper_status: dict[str, Any],
    supervisor_status: dict[str, Any],
    paper_risk_audit_status: dict[str, Any] | None = None,
    analytics_summary: dict[str, Any] | None = None,
    journal_status: dict[str, Any] | None = None,
    ai_review_status: dict[str, Any] | None = None,
    backtest_status: dict[str, Any] | None = None,
    research_status: dict[str, Any] | None = None,
    evidence_status: dict[str, Any] | None = None,
    daemon_status: dict[str, Any] | None = None,
    forward_test_status: dict[str, Any] | None = None,
    orchestrator_status: dict[str, Any] | None = None,
    long_forward_test_status: dict[str, Any] | None = None,
    live_readiness_status: dict[str, Any] | None = None,
    evidence_growth_status: dict[str, Any] | None = None,
    signal_certification_status: dict[str, Any] | None = None,
    event_bus_status: dict[str, Any] | None = None,
    strategy_agents_status: dict[str, Any] | None = None,
    backtest_compare_v1_v2: dict[str, Any] | None = None,
) -> OperatorStatus:
    snapshot = store.latest_snapshot()
    account = as_dict(snapshot.get("account")) if snapshot else {}
    tick = as_dict(snapshot.get("tick")) if snapshot else {}
    positions = as_list(snapshot.get("positions")) if snapshot else []
    orders = as_list(snapshot.get("orders")) if snapshot else []
    commands = store.list_commands()
    open_commands = [cmd for cmd in commands if cmd.get("status") not in {"EXECUTION_BLOCKED", "EXECUTION_FAILED", "EXECUTION_FILLED", "CANCELLED", "EXPIRED"}]
    results = store.list_results()
    signals = store.list_strategy_signals()
    latest_signal = signals[-1] if signals else {}
    v2_signals = [signal for signal in signals if signal.get("strategy_name") == "xauusd_paper_v2"]
    latest_v2_signal = v2_signals[-1] if v2_signals else {}
    market_quality = build_quality_report(snapshot, market_config)
    latest_context = context_engine.latest()
    ea_allow_live_trading = read_ea_allow_live_trading(snapshot)
    safety = {
        "live_trading_enabled": False,
        "paper_only": True,
        "ea_allow_live_trading_seen": ea_allow_live_trading,
        "command_queueing_from_supervisor": bool(as_dict(supervisor_status.get("safety")).get("allow_command_queueing", False)),
        "strategy_command_id_present": bool(latest_signal.get("command_id")),
        "open_market_execution_added": False,
    }

    return OperatorStatus(
        service=service,
        timestamp=utc_now_iso(),
        bridge={
            "terminal_id": snapshot.get("terminal_id") if snapshot else terminal_id,
            "snapshot_received": snapshot is not None,
            "latest_snapshot_received_at": snapshot.get("received_at") if snapshot else None,
            "latest_snapshot_age_seconds": age_seconds(snapshot.get("received_at")) if snapshot else None,
            "positions_count": len(positions),
            "orders_count": len(orders),
        },
        account={
            "balance": as_float(account.get("balance")),
            "equity": as_float(account.get("equity")),
            "currency": account.get("currency"),
            "login": account.get("login"),
            "server": account.get("server"),
        },
        market={
            "symbol": tick.get("symbol") or market_config.symbol,
            "bid": as_float(tick.get("bid")),
            "ask": as_float(tick.get("ask")),
            "spread_points": as_float(tick.get("spread_points")),
            "quality": market_quality,
            "recorder": market_recorder.status(),
        },
        context={
            "latest": latest_context,
            "status": context_engine.status(),
        },
        risk=risk_status,
        strategy={
            "status": strategy_status,
            "latest_signal": latest_signal,
            "latest_signal_v2": latest_v2_signal,
            "signals_count": len(signals),
        },
        paper=paper_status,
        paper_risk_audit=paper_risk_audit_status or {},
        supervisor=supervisor_status,
        analytics=analytics_summary or {},
        journal=journal_status or {},
        ai_review=ai_review_status or {},
        backtest={**(backtest_status or {}), "compare_v1_v2": backtest_compare_v1_v2 or {}},
        research=research_status or {},
        evidence=evidence_status or {},
        daemon=daemon_status or {},
        forward_test=forward_test_status or {},
        orchestrator=orchestrator_status or {},
        long_forward_test=long_forward_test_status or {},
        live_readiness=live_readiness_status or {},
        evidence_growth=evidence_growth_status or {},
        signal_certification=signal_certification_status or {},
        event_bus=event_bus_status or {},
        strategy_agents=strategy_agents_status or {},
        commands={
            "open_count": len(open_commands),
            "total_count": len(commands),
            "open": open_commands,
            "latest": commands[-5:],
        },
        execution={
            "results_count": len(results),
            "latest": results[-5:],
        },
        safety=safety,
    )


def build_operator_summary(status: OperatorStatus) -> OperatorSummary:
    market_quality = as_dict(as_dict(status.market.get("quality")))
    context_latest = as_dict(status.context.get("latest"))
    supervisor = as_dict(status.supervisor)
    paper_risk = as_dict(status.paper_risk_audit)
    paper_risk_latest = as_dict(paper_risk.get("latest"))
    analytics = as_dict(status.analytics)
    journal = as_dict(status.journal)
    ai_review = as_dict(status.ai_review)
    backtest = as_dict(status.backtest)
    backtest_latest = as_dict(backtest.get("latest"))
    research = as_dict(status.research)
    research_latest = as_dict(research.get("latest"))
    research_best_expectancy = as_dict(research_latest.get("best_by_expectancy"))
    evidence = as_dict(status.evidence)
    evidence_latest = as_dict(evidence.get("latest"))
    daemon = as_dict(status.daemon)
    forward_test = as_dict(status.forward_test)
    campaign = as_dict(forward_test.get("campaign"))
    campaign_progress = as_dict(campaign.get("progress"))
    orchestrator = as_dict(status.orchestrator)
    long_forward = as_dict(status.long_forward_test)
    live_readiness = as_dict(status.live_readiness)
    live_readiness_latest = as_dict(live_readiness.get("latest"))
    evidence_growth = as_dict(status.evidence_growth)
    evidence_growth_latest = as_dict(evidence_growth.get("latest"))
    signal_certification = as_dict(status.signal_certification)
    signal_certification_latest = as_dict(signal_certification.get("latest"))
    event_bus = as_dict(status.event_bus)
    event_bus_state = as_dict(event_bus.get("runtime_state"))
    strategy_agents = as_dict(status.strategy_agents)
    strategy_agent_signal = as_dict(strategy_agents.get("latest_signal"))
    latest_v2_signal = as_dict(status.strategy.get("latest_signal_v2"))
    comparison = as_dict(as_dict(status.backtest).get("compare_v1_v2"))
    comparison_v2 = as_dict(comparison.get("v2"))
    comparison_delta = as_dict(comparison.get("delta"))
    warnings: list[str] = []

    if not status.bridge.get("snapshot_received"):
        warnings.append("snapshot missing")
    if not market_quality.get("ok"):
        warnings.extend(str(reason) for reason in market_quality.get("reasons") or ["market quality not ok"])
    if status.commands.get("open_count", 0) > 0:
        warnings.append(f"open commands present: {status.commands.get('open_count')}")
    if status.safety.get("live_trading_enabled") is not False:
        warnings.append("live trading safety flag is not false")
    if status.safety.get("ea_allow_live_trading_seen") is True:
        warnings.append("EA reports allow_live_trading=true")
    if status.safety.get("command_queueing_from_supervisor"):
        warnings.append("supervisor command queueing is enabled")
    if status.safety.get("strategy_command_id_present"):
        warnings.append("latest strategy signal has command_id")

    return OperatorSummary(
        ok=len(warnings) == 0,
        mode=str(supervisor.get("mode") or "PAPER"),
        symbol=market_quality.get("symbol") or status.market.get("symbol"),
        session=context_latest.get("session_name"),
        regime=context_latest.get("regime"),
        spread_points=as_float(market_quality.get("spread_points")),
        market_quality_ok=bool(market_quality.get("ok")),
        paper_open_count=int(status.paper.get("open_trades") or supervisor.get("paper_open_count") or 0),
        paper_closed_trades=int(analytics.get("closed_trades") or status.paper.get("closed_trades") or 0),
        paper_win_rate=float(analytics.get("win_rate") or 0.0),
        paper_total_r=float(analytics.get("total_r") or 0.0),
        paper_expectancy_r=float(analytics.get("expectancy_r") or 0.0),
        paper_risk_decision_count=int(paper_risk.get("decision_count") or 0),
        paper_risk_latest_status=paper_risk_latest.get("risk_status"),
        paper_risk_latest_signal_id=paper_risk_latest.get("signal_id"),
        paper_risk_latest_trade_id=paper_risk_latest.get("trade_id"),
        supervisor_loop_count=int(supervisor.get("loop_count") or 0),
        journal_entry_count=int(journal.get("entries_count") or 0),
        journal_latest_classification=journal.get("latest_classification"),
        ai_review_latest_summary=ai_review.get("latest_summary"),
        ai_review_action_items_count=int(ai_review.get("latest_action_items_count") or 0),
        backtest_trade_count=int(backtest_latest.get("trades") or backtest.get("trades_count") or 0),
        backtest_expectancy_r=float(backtest_latest.get("expectancy_r") or 0.0),
        research_best_expectancy_r=float(research_best_expectancy.get("expectancy_r") or 0.0),
        research_warning_count=int(research.get("warning_count") or 0),
        evidence_status=evidence_latest.get("status"),
        evidence_live_ready=bool(evidence_latest.get("live_ready")),
        evidence_blocking_reasons_count=len(evidence_latest.get("blocking_reasons") or []),
        daemon_running=bool(daemon.get("running")),
        daemon_loop_count=int(daemon.get("loop_count") or 0),
        daemon_last_heartbeat_at=daemon.get("last_heartbeat_at"),
        daemon_errors=[str(error) for error in daemon.get("errors") or []],
        forward_test_status=campaign.get("status"),
        forward_test_progress_percent=float(campaign_progress.get("percent") or 0.0),
        forward_test_closed_paper_trades=int(campaign.get("closed_paper_trades") or 0),
        orchestrator_running=bool(orchestrator.get("running")),
        orchestrator_current_session=orchestrator.get("current_session"),
        orchestrator_session_allowed=bool(orchestrator.get("session_allowed")),
        orchestrator_forward_test_progress=float(orchestrator.get("forward_test_progress") or 0.0),
        orchestrator_evidence_status=orchestrator.get("evidence_status"),
        long_forward_test_running=bool(long_forward.get("running")),
        long_forward_test_progress=float(long_forward.get("forward_test_progress") or 0.0),
        long_forward_test_evidence_status=long_forward.get("evidence_status"),
        live_readiness_status=live_readiness_latest.get("status"),
        live_readiness_score=float(live_readiness_latest.get("score") or 0.0),
        live_readiness_arming_allowed=bool(live_readiness_latest.get("live_arming_allowed")),
        live_readiness_execution_allowed=bool(live_readiness_latest.get("live_execution_allowed")),
        evidence_growth_status=evidence_growth_latest.get("status"),
        evidence_growth_overall_progress=float(evidence_growth_latest.get("overall_progress") or 0.0),
        signal_certification_status=signal_certification_latest.get("status"),
        signal_certification_trade_id=signal_certification_latest.get("certified_trade_id"),
        signal_certification_strategy=signal_certification_latest.get("strategy"),
        signal_certification_direction=signal_certification_latest.get("direction"),
        signal_certification_trade_status=signal_certification_latest.get("trade_status"),
        signal_certification_warning_count=len(signal_certification_latest.get("warnings") or []),
        signal_certification_failed_count=len(signal_certification_latest.get("failed_checks") or []),
        v2_signal_status=latest_v2_signal.get("status"),
        backtest_v2_trade_count=int(comparison_v2.get("trades") or 0),
        backtest_v2_expectancy_r=float(comparison_v2.get("expectancy_r") or 0.0),
        backtest_v1_v2_expectancy_delta_r=as_float(comparison_delta.get("expectancy_r")),
        event_bus_enabled=bool(event_bus.get("enabled")),
        event_count=int(event_bus.get("event_count") or 0),
        last_sequence=int(event_bus.get("last_sequence") or 0),
        last_event_type=event_bus.get("last_event_type"),
        runtime_state_generated_at=event_bus_state.get("generated_at") or event_bus.get("runtime_state_generated_at"),
        strategy_agents_enabled=bool(strategy_agents.get("enabled")),
        strategy_agents_registered=int(strategy_agents.get("registered_count") or 0),
        strategy_agents_latest_status_counts=as_dict(strategy_agents.get("latest_status_counts")),
        latest_strategy_agent_signal=strategy_agent_signal.get("direction") or strategy_agent_signal.get("status"),
        warnings=warnings,
    )
