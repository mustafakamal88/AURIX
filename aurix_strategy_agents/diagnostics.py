from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aurix_common import write_json_atomic

from .models import utc_now_iso


REJECTION_MAP = {
    "balance_zone_reset": "RSI_NOT_EXTREME",
    "insufficient_m1_candles_for_rsi": "INSUFFICIENT_CANDLES",
    "invalid_candle_close": "MARKET_DATA_MISSING",
    "no_fast_rsi_first_reversal_setup": "NO_TRACE_PATTERN",
    "spread_above_max": "SPREAD_BLOCKED",
    "session_filter_blocked": "BLOCKED",
    "one_signal_per_bar": "WAITING_FOR_NEXT_CANDLE",
    "symbol_mismatch": "MARKET_DATA_MISSING",
}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _age_seconds(value: Any) -> float | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds())


def normalize_rejection_reason(result: dict[str, Any] | None) -> str | None:
    result = _dict(result)
    reasons = _list(result.get("rejection_reasons"))
    code = str(_dict(reasons[0]).get("code") or "").strip() if reasons else ""
    if code:
        return REJECTION_MAP.get(code, code.upper())
    status = str(result.get("status") or "").upper()
    if status == "SIGNAL":
        return None
    if status == "NO_SIGNAL":
        return "NO_ACTIONABLE_SIGNAL"
    if status == "ERROR":
        return "UNKNOWN"
    if status == "SKIPPED":
        return "UNKNOWN"
    return None


def result_state(result: dict[str, Any] | None, *, min_confidence: float = 0.60) -> str:
    result = _dict(result)
    if not result:
        return "STRATEGY_EVALUATION_MISSING"
    status = str(result.get("status") or "").upper()
    confidence = result.get("confidence")
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        confidence_value = 0.0
    if status == "SIGNAL":
        return "LOW_CONFIDENCE" if confidence_value < min_confidence else "ACTIONABLE"
    if status == "NO_SIGNAL":
        return "NO_SETUP"
    if status == "SKIPPED":
        rejection = normalize_rejection_reason(result)
        if rejection in {"INSUFFICIENT_CANDLES", "MARKET_DATA_MISSING"}:
            return "WAITING_FOR_DATA"
        return "WAITING_FOR_NEXT_CANDLE" if rejection == "WAITING_FOR_NEXT_CANDLE" else "BLOCKED"
    if status == "ERROR":
        return "ERROR"
    return "UNKNOWN"


def direction_candidate(result: dict[str, Any] | None) -> str:
    direction = _dict(result).get("direction")
    if direction in {"BUY", "SELL"}:
        return str(direction)
    return "NONE"


def strategy_diagnostic_row(result: dict[str, Any] | None, *, enabled: bool = True, registered: bool = True, min_confidence: float = 0.60) -> dict[str, Any]:
    result = _dict(result)
    if not registered:
        return {
            "strategy_name": None,
            "enabled": False,
            "status": "NOT_REGISTERED",
            "evaluated_at": None,
            "market_symbol": None,
            "timeframe": None,
            "direction_candidate": "NONE",
            "confidence": 0.0,
            "score": 0.0,
            "result": "STRATEGY_NOT_REGISTERED",
            "rejection_reason": "STRATEGY_NOT_REGISTERED",
            "latest_error": None,
        }
    if not enabled:
        return {
            "strategy_name": result.get("strategy_name"),
            "enabled": False,
            "status": "DISABLED",
            "evaluated_at": result.get("generated_at"),
            "market_symbol": result.get("symbol"),
            "timeframe": _dict(result.get("decision_trace")).get("timeframe"),
            "direction_candidate": "NONE",
            "confidence": 0.0,
            "score": 0.0,
            "result": "STRATEGY_DISABLED",
            "rejection_reason": "STRATEGY_DISABLED",
            "latest_error": None,
        }
    state = result_state(result, min_confidence=min_confidence)
    trace = _dict(result.get("decision_trace"))
    status_label = "RUNNING" if result else "NOT_RUNNING"
    if state == "WAITING_FOR_DATA":
        status_label = "WAITING_FOR_DATA"
    elif state == "ERROR":
        status_label = "ERROR"
    return {
        "strategy_name": result.get("strategy_name"),
        "enabled": True,
        "status": status_label,
        "evaluated_at": result.get("generated_at"),
        "market_symbol": result.get("symbol"),
        "timeframe": trace.get("timeframe"),
        "direction_candidate": direction_candidate(result),
        "confidence": result.get("confidence", 0.0) if result else 0.0,
        "score": result.get("score", result.get("confidence", 0.0)) if result else 0.0,
        "result": state,
        "rejection_reason": normalize_rejection_reason(result) or ("NO_ACTIONABLE_SIGNAL" if state == "NO_SETUP" else None),
        "latest_error": (result.get("error") or result.get("setup_reason")) if state == "ERROR" else None,
    }


def build_strategy_pipeline_snapshot(
    *,
    data_dir: str | Path,
    session_id: str = "unknown",
    market_data_fresh: bool = False,
    decision_loop_alive: bool = False,
    registry_status: dict[str, Any] | None = None,
    latest_evaluations: list[dict[str, Any]] | None = None,
    fast_rsi_state: dict[str, Any] | None = None,
    min_confidence: float = 0.60,
) -> dict[str, Any]:
    registry_status = _dict(registry_status)
    latest_evaluations = [item for item in _list(latest_evaluations) if isinstance(item, dict)]
    registered_count = int(registry_status.get("registered_count") or 0)
    enabled_count = int(registry_status.get("enabled_count") or 0)
    config = _dict(registry_status.get("config"))
    registered_entries = [item for item in _list(config.get("registered_agents")) if isinstance(item, dict)]
    strategy_names = [str(item.get("source_strategy")) for item in registered_entries if item.get("source_strategy")]
    latest = latest_evaluations[-1] if latest_evaluations else {}
    latest_at = latest.get("generated_at") or registry_status.get("last_evaluation_at")
    latest_row = strategy_diagnostic_row(latest, enabled=enabled_count > 0, registered=registered_count > 0, min_confidence=min_confidence)
    if registered_count == 0:
        latest_row = strategy_diagnostic_row(None, registered=False, min_confidence=min_confidence)
    elif enabled_count == 0:
        latest_row = strategy_diagnostic_row(latest, enabled=False, min_confidence=min_confidence)
    elif not latest_evaluations:
        latest_row["result"] = "STRATEGY_EVALUATION_MISSING"
        latest_row["rejection_reason"] = "STRATEGY_NOT_RUNNING"

    fast_rsi_result = next((item for item in reversed(latest_evaluations) if item.get("strategy_name") == "fast_rsi_first_reversal"), {})
    v1_result = next((item for item in reversed(latest_evaluations) if item.get("strategy_name") == "xauusd_paper_v1"), {})
    v2_result = next((item for item in reversed(latest_evaluations) if item.get("strategy_name") == "xauusd_paper_v2"), {})

    return {
        "generated_at": utc_now_iso(),
        "session_id": session_id,
        "market_data_fresh": bool(market_data_fresh),
        "decision_loop_alive": bool(decision_loop_alive),
        "strategy_registry_loaded": registered_count > 0,
        "registered_strategy_count": registered_count,
        "enabled_strategy_count": enabled_count,
        "registered_strategy_names": strategy_names,
        "evaluations_this_session": int(registry_status.get("evaluations_this_session") or len(latest_evaluations)),
        "decision_loop_not_alive_reason": None if decision_loop_alive else "status file stale" if latest_at else "strategy loop not started",
        "latest_evaluation_at": latest_at,
        "latest_evaluation_age_seconds": _age_seconds(latest_at),
        "latest_strategy_name": latest_row.get("strategy_name"),
        "latest_strategy_status": latest_row.get("status") or "UNKNOWN",
        "latest_result": latest_row.get("result") or "UNKNOWN",
        "latest_direction_candidate": latest_row.get("direction_candidate") or "NONE",
        "latest_confidence": latest_row.get("confidence"),
        "latest_score": latest_row.get("score"),
        "latest_rejection_reason": latest_row.get("rejection_reason"),
        "latest_error": latest_row.get("latest_error"),
        "v1_state": strategy_diagnostic_row(v1_result, registered=registered_count > 0, min_confidence=min_confidence),
        "v2_state": strategy_diagnostic_row(v2_result, registered=registered_count > 0, min_confidence=min_confidence),
        "fast_rsi_state": {
            **strategy_diagnostic_row(fast_rsi_result, registered=registered_count > 0, min_confidence=min_confidence),
            "runtime_state": _dict(fast_rsi_state),
        },
        "evaluations": [strategy_diagnostic_row(item, min_confidence=min_confidence) for item in latest_evaluations],
    }


def write_strategy_pipeline_snapshot(data_dir: str | Path, snapshot: dict[str, Any]) -> dict[str, Any]:
    path = Path(data_dir) / "strategy_pipeline" / "status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, snapshot)
    return snapshot
