from __future__ import annotations

from typing import Any

from aurix_broker_reconciliation import BrokerReconciliationStore
from aurix_demo_oms import DemoOmsStore
from aurix_event_bus import AurixEventBus
from aurix_trade_explanations import TradeExplanationStore, build_trade_explanation

from .config import DemoCommandQueueConfig
from .models import DemoCommandPreview, DemoMt5CommandPayload
from .models import DemoCommandQueueRejection
from .router import publish_payload_event, publish_preview_event
from .store import DemoCommandQueueStore
from .validator import validate_command_preview as validate_preview


class DemoCommandQueueAdapter:
    def __init__(
        self,
        data_dir: str = "data",
        config: DemoCommandQueueConfig | None = None,
        event_bus: AurixEventBus | None = None,
        snapshot_provider: Any | None = None,
        demo_oms_store: DemoOmsStore | None = None,
        broker_reconciliation_store: BrokerReconciliationStore | None = None,
    ):
        self.config = config or DemoCommandQueueConfig()
        self.store = DemoCommandQueueStore(data_dir, self.config)
        self.event_bus = event_bus
        self.snapshot_provider = snapshot_provider
        self.demo_oms_store = demo_oms_store or DemoOmsStore(data_dir)
        self.broker_reconciliation_store = broker_reconciliation_store or BrokerReconciliationStore(data_dir)
        self.trade_explanation_store = TradeExplanationStore(data_dir)
        self.provenance_provider = lambda component, source: {}

    def get_demo_command_queue_status(self) -> dict[str, Any]:
        return self.store.status()

    def load_previews(self) -> list[dict[str, Any]]:
        return self.store.load_previews()

    def load_payloads(self) -> list[dict[str, Any]]:
        return self.store.load_payloads()

    def history(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.store.history(limit)

    def reset_demo_command_queue(self) -> dict[str, Any]:
        return self.store.reset()

    def _snapshot(self) -> dict[str, Any] | None:
        if self.snapshot_provider is None:
            return None
        try:
            value = self.snapshot_provider()
        except Exception:
            return None
        return value if isinstance(value, dict) else None

    def _latest_oms_request(self) -> dict[str, Any] | None:
        requests = self.demo_oms_store.load_order_requests()
        return requests[-1] if requests else None

    def _oms_intent_for_request(self, request: dict[str, Any]) -> dict[str, Any]:
        intent_id = request.get("intent_id")
        for item in reversed(self.demo_oms_store.load_order_intents()):
            if item.get("id") == intent_id:
                return item
        return {}

    def _latest_decision(self) -> dict[str, Any]:
        if self.event_bus is not None:
            try:
                events = self.event_bus.load_events_by_type("AURIX_DECISION_EVENT", limit=20)
            except Exception:
                events = []
            if events:
                payload = events[-1].get("payload")
                return payload if isinstance(payload, dict) else {}
        return {}

    def _strategy_diagnostics_for(self, request: dict[str, Any], intent: dict[str, Any]) -> dict[str, Any]:
        strategy_name = request.get("strategy_name") or intent.get("strategy_name")
        if not strategy_name or self.event_bus is None:
            return {}
        try:
            events = self.event_bus.load_events_by_type("SIGNAL_EVENT", limit=50)
        except Exception:
            return {}
        source_signal_id = request.get("source_signal_id") or intent.get("source_signal_id")
        source_event_id = request.get("source_signal_event_id") or intent.get("source_signal_event_id")
        for event in reversed(events):
            payload = event.get("payload") if isinstance(event, dict) else {}
            payload = payload if isinstance(payload, dict) else {}
            if source_event_id and event.get("event_id") == source_event_id:
                return payload
            if source_signal_id and (payload.get("signal_id") == source_signal_id or payload.get("id") == source_signal_id):
                return payload
            if payload.get("strategy_name") == strategy_name:
                return payload
        return {}

    def _write_trade_explanation(self, request: dict[str, Any], preview: DemoCommandPreview, validation, payload: DemoMt5CommandPayload) -> dict[str, Any]:
        intent = self._oms_intent_for_request(request)
        explanation = build_trade_explanation(
            oms_request=request,
            oms_intent=intent,
            preview=preview.model_dump(mode="json"),
            validation=validation.model_dump(mode="json"),
            payload=payload.model_dump(mode="json"),
            snapshot=self._snapshot(),
            decision=self._latest_decision(),
            strategy_diagnostics=self._strategy_diagnostics_for(request, intent),
        )
        explanation["trade_id"] = str(payload.id)
        explanation["mt5_order_id"] = payload.broker_order_id or "unknown"
        return self.trade_explanation_store.write(explanation)

    def preview_latest_oms_request(self) -> dict[str, Any]:
        request = self._latest_oms_request()
        if request is None:
            preview = DemoCommandPreview(status="BLOCKED", validation_status="BLOCK")
            preview.rejection_reasons.append(DemoCommandQueueRejection(code="demo_oms_request_missing", message="No Demo OMS request exists"))
            self.store.add_preview(preview)
            publish_preview_event(self.event_bus, preview)
            return {"status": "BLOCKED", "preview": preview.model_dump(mode="json"), "validation": None, "safety": preview.safety.model_dump()}
        return self.preview_oms_request(request)

    def preview_oms_request(self, oms_request: dict[str, Any]) -> dict[str, Any]:
        preview = self._build_preview(oms_request)
        validation = self.validate_command_preview(preview, oms_request)
        preview.validation_status = validation.status
        preview.rejection_reasons = validation.rejection_reasons
        preview.warnings = validation.warnings
        preview.status = "BLOCKED" if not validation.approved else "PREVIEW_CREATED"
        self.store.add_preview(preview)
        event = publish_preview_event(self.event_bus, preview, validation)
        return {"status": preview.status, "preview": preview.model_dump(mode="json"), "validation": validation.model_dump(mode="json"), "event": event, "safety": preview.safety.model_dump()}

    def _build_preview(self, request: dict[str, Any]) -> DemoCommandPreview:
        return DemoCommandPreview(
            source_oms_request_id=request.get("id"),
            source_oms_intent_id=request.get("intent_id"),
            source_signal_id=request.get("source_signal_id"),
            source_signal_event_id=request.get("source_signal_event_id"),
            strategy_name=request.get("strategy_name"),
            strategy_version=request.get("strategy_version"),
            symbol=request.get("symbol") or self.config.symbol,
            direction=request.get("direction"),
            order_type=request.get("order_type"),
            volume=float(request.get("volume") or 0.0),
            entry_reference=request.get("entry_reference"),
            stop_loss=request.get("stop_loss"),
            take_profit=request.get("take_profit"),
            max_slippage_points=self.config.max_slippage_points,
            ttl_seconds=self.config.command_ttl_seconds,
            correlation_id=request.get("correlation_id"),
            causation_id=request.get("id"),
            provenance=self.provenance_provider("demo_command_queue", "aurix_demo_command_queue.adapter._build_preview"),
        )

    def validate_command_preview(self, preview: DemoCommandPreview, oms_request: dict[str, Any] | None = None):
        return validate_preview(
            preview,
            config=self.config,
            oms_request=oms_request,
            broker_reconciliation=self.broker_reconciliation_store.latest(),
            snapshot=self._snapshot(),
        )

    def build_mt5_command_payload(self, preview: DemoCommandPreview, validation) -> DemoMt5CommandPayload:
        status = "READY_FOR_BROKER_EXECUTION" if validation.approved else "BLOCKED"
        return DemoMt5CommandPayload(
            preview_id=preview.id,
            command_type="OPEN_MARKET",
            symbol=preview.symbol,
            side=preview.direction,
            volume=preview.volume,
            sl=preview.stop_loss,
            tp=preview.take_profit,
            deviation_points=preview.max_slippage_points,
            ttl_seconds=preview.ttl_seconds,
            status=status,
            mt5_command_id=None,
            queued_at=None,
            broker_order_id=None,
            correlation_id=preview.correlation_id,
            causation_id=preview.id,
            provenance=self.provenance_provider("demo_command_queue", "aurix_demo_command_queue.adapter.build_mt5_command_payload"),
        )

    def dry_run_latest_oms_request(self) -> dict[str, Any]:
        request = self._latest_oms_request()
        if request is None:
            preview_result = self.preview_latest_oms_request()
            return {**preview_result, "payload": None}
        preview = self._build_preview(request)
        validation = self.validate_command_preview(preview, request)
        preview.validation_status = validation.status
        preview.rejection_reasons = validation.rejection_reasons
        preview.warnings = validation.warnings
        preview.status = "BLOCKED" if not validation.approved else "PREVIEW_CREATED"
        self.store.add_preview(preview)
        preview_event = publish_preview_event(self.event_bus, preview, validation)
        payload = self.build_mt5_command_payload(preview, validation)
        explanation = self._write_trade_explanation(request, preview, validation, payload)
        self.store.add_payload(payload)
        payload_event = publish_payload_event(self.event_bus, payload, validation)
        return {
            "status": payload.status,
            "preview": preview.model_dump(mode="json"),
            "payload": payload.model_dump(mode="json"),
            "validation": validation.model_dump(mode="json"),
            "trade_explanation": explanation,
            "preview_event": preview_event,
            "payload_event": payload_event,
            "paper_trades_created": 0,
            "commands_queued": 0,
            "broker_orders_created": 0,
            "safety": payload.safety.model_dump(),
        }
