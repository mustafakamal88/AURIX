from __future__ import annotations

from typing import Any

from aurix_event_bus import AurixEvent, AurixEventBus, AurixEventType
from aurix_event_bus.models import EventSafety

from .models import AurixDecisionReport


def _safety() -> EventSafety:
    return EventSafety(event_bus_only=True, live_execution_allowed=False, live_arming_allowed=False, command_queueing_allowed=False, mt5_commands_queued=False, broker_order_created=False, ea_settings_modified=False, external_llm_used=False, strategy_config_mutated=False)


def publish_decision_events(event_bus: AurixEventBus | None, report: AurixDecisionReport) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if event_bus is None:
        return None, None
    autonomy = event_bus.publish_event(AurixEvent(event_type=AurixEventType.AUTONOMY_STATE_EVENT, source="decision_engine", symbol=report.symbol, correlation_id=report.id, payload={"report_id": report.id, "autonomy_level": report.autonomy_level, "status": report.status.value, "action": report.action.value, "safety": report.safety.model_dump()}, safety=_safety()))
    decision = event_bus.publish_event(AurixEvent(event_type=AurixEventType.AURIX_DECISION_EVENT, source="decision_engine", symbol=report.symbol, correlation_id=report.id, causation_id=autonomy.get("event_id") if autonomy else None, payload={"report_id": report.id, "action": report.action.value, "direction": report.direction, "status": report.status.value, "confidence": report.confidence, "score": report.score.total, "strategy": report.strategy, "signal_id": report.signal_id, "setup_reason": report.setup_reason, "blocking_reason_count": len(report.blocking_reasons), "warning_count": len(report.warnings), "autonomy_level": report.autonomy_level, "demo_execution_allowed": False, "live_execution_allowed": False, "command_queueing_allowed": False, "safety": report.safety.model_dump()}, safety=_safety()))
    return autonomy, decision
