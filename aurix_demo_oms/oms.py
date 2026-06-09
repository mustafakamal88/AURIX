from __future__ import annotations

from typing import Any

from aurix_event_bus import AurixEventBus, AurixEventType

from .config import DemoOmsConfig
from .models import DemoOmsSafety, OmsOrderIntent, OmsOrderRequest, OmsOrderState, OmsRejectionReason, OmsValidationResult
from .router import publish_order_request_event, publish_risk_decision_event
from .store import DemoOmsStore
from .validator import validate_order_intent as validate_intent


class DemoOms:
    def __init__(
        self,
        data_dir: str = "data",
        config: DemoOmsConfig | None = None,
        event_bus: AurixEventBus | None = None,
        snapshot_provider: Any | None = None,
    ):
        self.config = config or DemoOmsConfig()
        self.store = DemoOmsStore(data_dir, self.config)
        self.event_bus = event_bus
        self.snapshot_provider = snapshot_provider

    def get_demo_oms_status(self) -> dict[str, Any]:
        return self.store.status()

    def load_order_intents(self) -> list[dict[str, Any]]:
        return self.store.load_order_intents()

    def load_order_requests(self) -> list[dict[str, Any]]:
        return self.store.load_order_requests()

    def reset_demo_oms(self) -> dict[str, Any]:
        return self.store.reset()

    def history(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.store.history(limit)

    def _runtime_state(self) -> dict[str, Any]:
        if self.event_bus is None:
            return {}
        try:
            return self.event_bus.get_latest_state()
        except Exception:
            return {}

    def _snapshot(self) -> dict[str, Any] | None:
        if self.snapshot_provider is None:
            return None
        try:
            return self.snapshot_provider()
        except Exception:
            return None

    def _event_bus_enabled(self) -> bool:
        if self.event_bus is None:
            return False
        try:
            return bool(self.event_bus.config.enabled)
        except Exception:
            return False

    def process_latest_signal_event(self) -> dict[str, Any]:
        if self.event_bus is None:
            return {"status": "BLOCKED", "reason": "event_bus_unavailable", "safety": DemoOmsSafety().model_dump()}
        events = self.event_bus.load_events_by_type(AurixEventType.SIGNAL_EVENT.value, limit=50)
        if not events:
            return {"status": "BLOCKED", "reason": "no_signal_event", "safety": DemoOmsSafety().model_dump()}
        return self.process_signal_event(events[-1])

    def process_signal_event(self, signal_event: dict[str, Any]) -> dict[str, Any]:
        intent = self.create_order_intent(signal_event)
        validation = self.validate_order_intent(intent)
        risk_event = publish_risk_decision_event(self.event_bus, validation, intent.symbol, intent.correlation_id, intent.causation_id)
        request = self.create_order_request_dry_run(intent, validation)
        order_event = publish_order_request_event(self.event_bus, request, validation)
        return {
            "status": request.status if validation.approved else "BLOCKED",
            "intent": intent.model_dump(mode="json"),
            "request": request.model_dump(mode="json"),
            "validation": validation.model_dump(mode="json"),
            "risk_event": risk_event,
            "order_request_event": order_event,
            "safety": DemoOmsSafety().model_dump(),
            "paper_trades_created": 0,
            "commands_queued": 0,
            "broker_orders_created": 0,
        }

    def create_order_intent(self, signal_event: dict[str, Any]) -> OmsOrderIntent:
        payload = signal_event.get("payload") if isinstance(signal_event, dict) else {}
        payload = payload if isinstance(payload, dict) else {}
        direction = payload.get("direction")
        order_type = "MARKET_BUY" if direction == "BUY" else "MARKET_SELL" if direction == "SELL" else None
        intent = OmsOrderIntent(
            source_signal_event_id=signal_event.get("event_id"),
            source_signal_id=payload.get("signal_id") or payload.get("id"),
            strategy_name=payload.get("strategy_name"),
            strategy_version=payload.get("strategy_version"),
            symbol=payload.get("symbol") or signal_event.get("symbol") or self.config.symbol,
            direction=direction,
            order_type=order_type,
            entry_reference=payload.get("entry_reference"),
            stop_loss=payload.get("stop_loss") or payload.get("stop_loss_reference"),
            take_profit=payload.get("take_profit") or payload.get("take_profit_reference"),
            volume=float(payload.get("volume") or self.config.max_volume),
            confidence=float(payload.get("confidence") or 0.0),
            setup_reason=payload.get("setup_reason"),
            decision_trace=payload.get("decision_trace") if isinstance(payload.get("decision_trace"), dict) else {},
            correlation_id=signal_event.get("correlation_id") or payload.get("correlation_id"),
            causation_id=signal_event.get("event_id"),
            status=OmsOrderState.CREATED,
            safety=DemoOmsSafety(),
        )
        if self.config.require_strategy_signal_event and signal_event.get("event_type") != AurixEventType.SIGNAL_EVENT.value:
            intent.rejection_reasons.append(OmsRejectionReason(code="not_strategy_signal_event", message="OMS requires a SIGNAL_EVENT"))
        if self.config.require_signal_command_id_null and payload.get("command_id") is not None:
            intent.rejection_reasons.append(OmsRejectionReason(code="signal_command_id_present", message="signal command_id must be null"))
        if not self.config.allow_order_intent_creation:
            intent.rejection_reasons.append(OmsRejectionReason(code="order_intent_creation_disabled", message="order intent creation is disabled"))
        if intent.rejection_reasons:
            intent.status = OmsOrderState.REJECTED
        self.store.add_intent(intent)
        return intent

    def validate_order_intent(self, intent: OmsOrderIntent) -> OmsValidationResult:
        validation = validate_intent(
            intent,
            config=self.config,
            runtime_state=self._runtime_state(),
            snapshot=self._snapshot(),
            existing_requests=self.store.load_order_requests(),
            event_bus_enabled=self._event_bus_enabled(),
        )
        if intent.rejection_reasons:
            validation.rejection_reasons = [*intent.rejection_reasons, *validation.rejection_reasons]
            validation.approved = False
            validation.status = "BLOCK"
        intent.rejection_reasons = validation.rejection_reasons
        intent.warnings = validation.warnings
        intent.status = OmsOrderState.VALIDATED if validation.approved else OmsOrderState.REJECTED
        self.store.update_intent(intent)
        self.store.add_audit(
            "ORDER_INTENT_VALIDATED" if validation.approved else "ORDER_INTENT_REJECTED",
            intent_id=intent.id,
            status=intent.status.value,
            detail=validation.model_dump(mode="json"),
        )
        return validation

    def create_order_request_dry_run(self, intent: OmsOrderIntent, validation: OmsValidationResult) -> OmsOrderRequest:
        status = "DRY_RUN_ONLY" if validation.approved else "BLOCKED"
        if validation.approved and (not self.config.allow_order_request_event_creation or self.config.allow_command_queueing or self.config.allow_demo_command_queueing):
            status = "QUEUE_DISABLED"
        request = OmsOrderRequest(
            intent_id=intent.id,
            symbol=intent.symbol,
            direction=intent.direction,
            order_type=intent.order_type,
            volume=intent.volume,
            entry_reference=intent.entry_reference,
            stop_loss=intent.stop_loss,
            take_profit=intent.take_profit,
            status=status,
            mt5_command_id=None,
            broker_order_id=None,
            correlation_id=intent.correlation_id,
            causation_id=intent.id,
            safety=DemoOmsSafety(),
        )
        intent.status = OmsOrderState.DRY_RUN_READY if status == "DRY_RUN_ONLY" else OmsOrderState.BLOCKED
        self.store.update_intent(intent)
        self.store.add_request(request)
        return request
