from __future__ import annotations

from typing import Iterable

from .models import AurixEvent, AurixEventType, AurixRuntimeState, utc_now_iso
from .state import initial_runtime_state


def _merge(target: dict, payload: dict) -> dict:
    updated = dict(target)
    updated.update(payload)
    return updated


def project_event(state: AurixRuntimeState, event: AurixEvent) -> AurixRuntimeState:
    payload = event.payload
    state.generated_at = utc_now_iso()
    state.symbol = event.symbol or state.symbol
    state.last_sequence = event.sequence
    state.last_event_id = event.event_id
    state.safety = _merge(state.safety, event.safety.model_dump())

    if event.event_type == AurixEventType.TICK_EVENT:
        state.market["latest_tick"] = payload
    elif event.event_type == AurixEventType.CANDLE_CLOSED_EVENT:
        state.market["latest_candle"] = payload
    elif event.event_type == AurixEventType.ACCOUNT_STATE_EVENT:
        state.account = payload
    elif event.event_type in {
        AurixEventType.POSITION_STATE_EVENT,
        AurixEventType.POSITION_OPENED_EVENT,
        AurixEventType.POSITION_UPDATED_EVENT,
        AurixEventType.POSITION_CLOSED_EVENT,
    }:
        state.positions = {"items": payload.get("items", payload if isinstance(payload, list) else []), "latest": payload}
    elif event.event_type in {
        AurixEventType.ORDER_STATE_EVENT,
        AurixEventType.ORDER_REQUEST_EVENT,
        AurixEventType.ORDER_ACCEPTED_EVENT,
        AurixEventType.ORDER_REJECTED_EVENT,
        AurixEventType.ORDER_FILLED_EVENT,
        AurixEventType.ORDER_CANCELLED_EVENT,
    }:
        state.orders = {"items": payload.get("items", payload if isinstance(payload, list) else []), "latest": payload}
        state.execution["latest_order_event"] = {"event_type": event.event_type.value, "payload": payload}
        if event.event_type == AurixEventType.ORDER_REQUEST_EVENT:
            state.execution["latest_order_request"] = payload
    elif event.event_type == AurixEventType.TRADE_HISTORY_EVENT:
        state.trade_history = {"items": payload.get("items", []), "latest": payload}
    elif event.event_type == AurixEventType.MARKET_QUALITY_EVENT:
        state.market["quality"] = payload
    elif event.event_type == AurixEventType.SESSION_STATE_EVENT:
        state.session = payload
    elif event.event_type == AurixEventType.CONTEXT_STATE_EVENT:
        state.context = payload
    elif event.event_type == AurixEventType.SIGNAL_EVENT:
        state.strategy["latest_signal"] = payload
    elif event.event_type == AurixEventType.STRATEGY_EVALUATION_EVENT:
        state.strategy["latest_evaluation"] = payload
    elif event.event_type == AurixEventType.STRATEGY_REGISTRY_EVENT:
        state.strategy["registry"] = payload
    elif event.event_type == AurixEventType.RISK_DECISION_EVENT:
        state.risk["latest_decision"] = payload
    elif event.event_type == AurixEventType.PAPER_RISK_DECISION_EVENT:
        state.paper["latest_risk_decision"] = payload
    elif event.event_type == AurixEventType.PAPER_TRADE_EVENT:
        status = str(payload.get("status") or "").upper()
        state.paper["latest_trade"] = payload
        if status == "OPEN":
            state.paper["open_count"] = int(state.paper.get("open_count") or 0) + 1
        elif status in {"CLOSED", "TP", "SL", "MANUAL_CLOSED"}:
            state.paper["closed_count"] = int(state.paper.get("closed_count") or 0) + 1
    elif event.event_type == AurixEventType.JOURNAL_EVENT:
        state.journal["latest"] = payload
    elif event.event_type == AurixEventType.AI_REVIEW_EVENT:
        state.journal["latest_review"] = payload
    elif event.event_type == AurixEventType.ALERT_EVENT:
        state.alerts["latest"] = payload
    elif event.event_type == AurixEventType.SYSTEM_HEARTBEAT_EVENT:
        state.health = payload
    elif event.event_type == AurixEventType.SAFETY_STATE_EVENT:
        state.safety = _merge(state.safety, payload)
    elif event.event_type == AurixEventType.BROKER_RECONCILIATION_EVENT:
        state.execution["latest_broker_reconciliation"] = payload
        state.health["broker_reconciliation_status"] = payload.get("status")
    elif event.event_type == AurixEventType.DEMO_COMMAND_PREVIEW_EVENT:
        state.execution["latest_demo_command_preview"] = payload
    elif event.event_type == AurixEventType.DEMO_COMMAND_QUEUE_EVENT:
        state.execution["latest_demo_command_queue_event"] = payload

    return state


def project_events(events: Iterable[AurixEvent], symbol: str = "XAUUSDm", mode: str = "EVENT_BUS_ONLY") -> AurixRuntimeState:
    state = initial_runtime_state(symbol, mode)
    for event in events:
        state = project_event(state, event)
    return state
