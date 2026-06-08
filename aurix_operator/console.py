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
    analytics_summary: dict[str, Any] | None = None,
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
            "signals_count": len(signals),
        },
        paper=paper_status,
        supervisor=supervisor_status,
        analytics=analytics_summary or {},
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
    analytics = as_dict(status.analytics)
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
        supervisor_loop_count=int(supervisor.get("loop_count") or 0),
        warnings=warnings,
    )
