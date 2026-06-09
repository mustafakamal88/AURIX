from __future__ import annotations

from typing import Any

from aurix_event_bus import AurixEvent, AurixEventBus, AurixEventType
from aurix_event_bus.models import EventSafety

from .models import DemoCommandPreview, DemoCommandValidationResult, DemoMt5CommandPayload


def _safety() -> EventSafety:
    return EventSafety(event_bus_only=True, live_execution_allowed=False, live_arming_allowed=False, command_queueing_allowed=False, mt5_commands_queued=False, broker_order_created=False, ea_settings_modified=False, external_llm_used=False, strategy_config_mutated=False)


def publish_preview_event(event_bus: AurixEventBus | None, preview: DemoCommandPreview, validation: DemoCommandValidationResult | None = None) -> dict[str, Any] | None:
    if event_bus is None:
        return None
    payload = preview.model_dump(mode="json")
    if validation:
        payload["validation"] = validation.model_dump(mode="json")
    return event_bus.publish_event(AurixEvent(event_type=AurixEventType.DEMO_COMMAND_PREVIEW_EVENT, source="demo_command_queue_adapter", symbol=preview.symbol, correlation_id=preview.correlation_id or preview.id, causation_id=preview.causation_id, payload=payload, safety=_safety()))


def publish_payload_event(event_bus: AurixEventBus | None, payload_obj: DemoMt5CommandPayload, validation: DemoCommandValidationResult) -> dict[str, Any] | None:
    if event_bus is None:
        return None
    payload = payload_obj.model_dump(mode="json")
    payload["validation"] = validation.model_dump(mode="json")
    return event_bus.publish_event(AurixEvent(event_type=AurixEventType.DEMO_COMMAND_QUEUE_EVENT, source="demo_command_queue_adapter", symbol=payload_obj.symbol, correlation_id=payload_obj.correlation_id or payload_obj.id, causation_id=payload_obj.causation_id, payload=payload, safety=_safety()))
