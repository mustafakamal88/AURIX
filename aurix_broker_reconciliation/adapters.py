from __future__ import annotations

from typing import Any

from aurix_event_bus import AurixEvent, AurixEventBus, AurixEventType
from aurix_event_bus.models import EventSafety

from .models import BrokerReconciliationReport


def publish_broker_reconciliation_event(event_bus: AurixEventBus | None, report: BrokerReconciliationReport) -> dict[str, Any] | None:
    if event_bus is None:
        return None
    payload = {
        "report_id": report.id,
        "status": report.status,
        "symbol": report.symbol,
        "broker_position_count": len(report.broker_positions),
        "broker_order_count": len(report.broker_orders),
        "mismatch_count": len(report.mismatches),
        "warning_count": len(report.warnings),
        "unexpected_position_detected": any(item.code == "unexpected_broker_position" for item in report.mismatches),
        "unexpected_order_detected": any(item.code == "unexpected_broker_order" for item in report.mismatches),
        "live_execution_allowed": False,
        "command_queueing_allowed": False,
        "safety": report.safety.model_dump(),
    }
    return event_bus.publish_event(
        AurixEvent(
            event_type=AurixEventType.BROKER_RECONCILIATION_EVENT,
            source="broker_reconciliation_engine",
            symbol=report.symbol,
            correlation_id=report.id,
            payload=payload,
            safety=EventSafety(
                event_bus_only=True,
                live_execution_allowed=False,
                live_arming_allowed=False,
                command_queueing_allowed=False,
                mt5_commands_queued=False,
                broker_order_created=False,
                ea_settings_modified=False,
                external_llm_used=False,
                strategy_config_mutated=False,
            ),
        )
    )
