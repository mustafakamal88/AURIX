from __future__ import annotations

from datetime import datetime
from typing import Any

from aurix_bridge_server.models import utc_now_iso

from .models import LongForwardDailyReport


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_daily_report(inputs: dict[str, Any]) -> LongForwardDailyReport:
    operator_status = as_dict(inputs.get("operator_status"))
    forward_status = as_dict(inputs.get("forward_test_status"))
    campaign = as_dict(forward_status.get("campaign"))
    analytics = as_dict(inputs.get("analytics_summary"))
    journal = as_dict(inputs.get("journal_status"))
    ai_review = as_dict(inputs.get("ai_review"))
    evidence = as_dict(inputs.get("evidence_report"))
    market_quality = as_dict(inputs.get("market_quality"))
    paper_trades = as_list(inputs.get("paper_trades"))
    safety = as_dict(operator_status.get("safety"))
    generated_at = utc_now_iso()

    wins = int(analytics.get("wins") or 0)
    losses = int(analytics.get("losses") or 0)
    recommendations = [
        "continue paper forward testing until evidence targets are met",
        "do not enable live trading from long forward-test mode",
    ]
    if evidence.get("blocking_reasons"):
        recommendations.append("address evidence gate blocking reasons before any live-readiness review")
    if market_quality.get("ok") is False:
        recommendations.append("review market data quality warnings before interpreting results")
    if journal.get("entries_count", 0) == 0:
        recommendations.append("generate journal entries after more closed paper trades")
    if ai_review.get("summary"):
        recommendations.append("review local AI summary for non-execution observations")

    return LongForwardDailyReport(
        date=datetime.now().date().isoformat(),
        generated_at=generated_at,
        sessions_observed=[str(item) for item in campaign.get("sessions_observed") or []],
        candles_recorded=int(campaign.get("recorded_candles") or market_quality.get("candles_count") or 0),
        paper_trades_opened=len(paper_trades),
        paper_trades_closed=int(campaign.get("closed_paper_trades") or analytics.get("closed_trades") or 0),
        wins=wins,
        losses=losses,
        win_rate=as_float(analytics.get("win_rate")),
        total_r=as_float(analytics.get("total_r")),
        expectancy_r=as_float(analytics.get("expectancy_r")),
        evidence_status=evidence.get("status"),
        blocking_reasons=[str(reason) for reason in evidence.get("blocking_reasons") or []],
        safety_status={
            "paper_only": safety.get("paper_only", True),
            "live_execution_allowed": False,
            "command_queueing_allowed": False,
            "external_llm_allowed": False,
            "mt5_commands_queued": False,
        },
        recommendations=list(dict.fromkeys(recommendations)),
    )
