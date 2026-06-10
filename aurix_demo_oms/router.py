from __future__ import annotations

from typing import Any

from aurix_event_bus import AurixEvent, AurixEventBus, AurixEventType
from aurix_event_bus.models import EventSafety

from .models import DemoOmsSafety, OmsOrderRequest, OmsValidationResult


def _event_safety() -> EventSafety:
    return EventSafety(
        event_bus_only=True,
        live_execution_allowed=False,
        live_arming_allowed=False,
        command_queueing_allowed=False,
        mt5_commands_queued=False,
        broker_order_created=False,
        ea_settings_modified=False,
        external_llm_used=False,
        strategy_config_mutated=False,
    )


def publish_risk_decision_event(event_bus: AurixEventBus | None, validation: OmsValidationResult, symbol: str, correlation_id: str | None, causation_id: str | None) -> dict[str, Any] | None:
    if event_bus is None:
        return None
    return event_bus.publish_event(
        AurixEvent(
            event_type=AurixEventType.RISK_DECISION_EVENT,
            source="demo_oms_validation_adapter",
            symbol=symbol,
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload={
                "id": validation.id,
                "intent_id": validation.intent_id,
                "status": validation.status,
                "approved": validation.approved,
                "risk_governor_checked": validation.risk_governor_checked,
                "risk_governor_approved": validation.risk_governor_approved,
                "risk_governor_decision": validation.risk_governor_decision,
                "rejection_reasons": [item.model_dump() for item in validation.rejection_reasons],
                "warnings": validation.warnings,
                "demo_oms_only": True,
                "safety": DemoOmsSafety().model_dump(),
            },
            safety=_event_safety(),
        )
    )


def publish_order_request_event(event_bus: AurixEventBus | None, request: OmsOrderRequest, validation: OmsValidationResult) -> dict[str, Any] | None:
    if event_bus is None:
        return None
    payload = request.model_dump(mode="json")
    if request.status == "READY_FOR_BROKER_EXECUTION":
        payload["event_status"] = "ORDER_REQUEST_READY_FOR_BROKER_EXECUTION"
    else:
        payload["event_status"] = "ORDER_REQUEST_BLOCKED"
    payload["validation"] = validation.model_dump(mode="json")
    payload["mt5_command_id"] = None
    payload["broker_order_id"] = None
    payload["safety"] = DemoOmsSafety().model_dump()
    return event_bus.publish_event(
        AurixEvent(
            event_type=AurixEventType.ORDER_REQUEST_EVENT,
            source="demo_oms_execution_agent",
            symbol=request.symbol,
            correlation_id=request.correlation_id,
            causation_id=request.causation_id,
            payload=payload,
            safety=_event_safety(),
        )
    )
