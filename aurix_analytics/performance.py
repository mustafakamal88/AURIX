from __future__ import annotations

from typing import Any, Optional

from .models import PaperPerformanceReport


CLOSED_STATUSES = {"CLOSED_TP", "CLOSED_SL", "CLOSED_MANUAL", "EXPIRED"}


def generate_paper_performance_report(
    trades: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    contexts: list[dict[str, Any]],
    market_quality: dict[str, Any],
) -> PaperPerformanceReport:
    signals_by_id = {str(signal.get("id")): signal for signal in signals if signal.get("id")}
    context_by_snapshot_time = {
        str(context.get("snapshot_updated_at")): context for context in contexts if context.get("snapshot_updated_at")
    }
    enriched = [_enrich_trade(trade, signals_by_id, context_by_snapshot_time) for trade in trades]
    closed = [trade for trade in enriched if trade.get("status") in CLOSED_STATUSES]
    open_trades = [trade for trade in enriched if trade.get("status") == "OPEN"]
    r_values = [_as_float(trade.get("r_multiple")) for trade in closed]
    r_values = [value for value in r_values if value is not None]
    pnl_values = [_as_float(trade.get("pnl_points")) for trade in closed]
    pnl_values = [value for value in pnl_values if value is not None]
    wins = [value for value in r_values if value > 0]
    losses = [value for value in r_values if value < 0]
    total_positive_r = sum(wins)
    total_negative_r = abs(sum(losses))
    warnings: list[str] = []
    notes: list[str] = []

    if not closed:
        warnings.append("no closed paper trades yet")
    if not market_quality:
        notes.append("market quality snapshot missing")

    return PaperPerformanceReport(
        total_trades=len(enriched),
        open_trades=len(open_trades),
        closed_trades=len(closed),
        wins=len(wins),
        losses=len(losses),
        win_rate=_ratio(len(wins), len(closed)),
        total_pnl_points=round(sum(pnl_values), 6),
        average_pnl_points=round(_average(pnl_values), 6),
        total_r=round(sum(r_values), 6),
        average_r=round(_average(r_values), 6),
        best_trade_r=round(max(r_values), 6) if r_values else None,
        worst_trade_r=round(min(r_values), 6) if r_values else None,
        profit_factor=_profit_factor(total_positive_r, total_negative_r, wins),
        expectancy_r=round(_average(r_values), 6),
        max_consecutive_wins=_max_consecutive(closed, want_win=True),
        max_consecutive_losses=_max_consecutive(closed, want_win=False),
        by_direction=_group_metrics(closed, "direction"),
        by_session=_group_metrics(closed, "session"),
        by_regime=_group_metrics(closed, "regime"),
        warnings=warnings,
        notes=notes,
    )


def summary_from_report(report: PaperPerformanceReport) -> dict[str, Any]:
    return {
        "generated_at": report.generated_at,
        "total_trades": report.total_trades,
        "open_trades": report.open_trades,
        "closed_trades": report.closed_trades,
        "wins": report.wins,
        "losses": report.losses,
        "win_rate": report.win_rate,
        "total_r": report.total_r,
        "expectancy_r": report.expectancy_r,
        "profit_factor": report.profit_factor,
        "warnings": report.warnings,
    }


def _enrich_trade(
    trade: dict[str, Any],
    signals_by_id: dict[str, dict[str, Any]],
    context_by_snapshot_time: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    enriched = dict(trade)
    signal = signals_by_id.get(str(trade.get("signal_id")))
    if signal:
        enriched["session"] = signal.get("context_session")
        enriched["regime"] = signal.get("context_regime")
    if not enriched.get("session") or not enriched.get("regime"):
        context = context_by_snapshot_time.get(str(trade.get("snapshot_opened_at")))
        if context:
            enriched.setdefault("session", context.get("session_name"))
            enriched.setdefault("regime", context.get("regime"))
    return enriched


def _group_metrics(trades: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for trade in trades:
        key = str(trade.get(field) or "UNKNOWN")
        groups.setdefault(key, []).append(trade)

    return {key: _metrics_for_trades(items) for key, items in sorted(groups.items())}


def _metrics_for_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    r_values = [_as_float(trade.get("r_multiple")) for trade in trades]
    r_values = [value for value in r_values if value is not None]
    pnl_values = [_as_float(trade.get("pnl_points")) for trade in trades]
    pnl_values = [value for value in pnl_values if value is not None]
    wins = [value for value in r_values if value > 0]
    losses = [value for value in r_values if value < 0]
    return {
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": _ratio(len(wins), len(trades)),
        "total_pnl_points": round(sum(pnl_values), 6),
        "average_pnl_points": round(_average(pnl_values), 6),
        "total_r": round(sum(r_values), 6),
        "average_r": round(_average(r_values), 6),
        "expectancy_r": round(_average(r_values), 6),
    }


def _max_consecutive(trades: list[dict[str, Any]], want_win: bool) -> int:
    best = 0
    current = 0
    ordered = sorted(trades, key=lambda trade: str(trade.get("closed_at") or trade.get("opened_at") or ""))
    for trade in ordered:
        r_value = _as_float(trade.get("r_multiple"))
        matched = (r_value is not None and r_value > 0) if want_win else (r_value is not None and r_value < 0)
        if matched:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def _profit_factor(total_positive_r: float, total_negative_r: float, wins: list[float]) -> Optional[float]:
    if total_negative_r == 0:
        return None if not wins else float("inf")
    return round(total_positive_r / total_negative_r, 6)


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
