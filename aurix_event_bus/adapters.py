from __future__ import annotations

from typing import Any
from uuid import uuid4

from aurix_bridge_server.models import utc_now_iso as bridge_utc_now_iso

from .bus import AurixEventBus
from .models import AurixEvent, AurixEventType, EventSafety


def _event(event_type: AurixEventType, source: str, symbol: str, payload: dict[str, Any], correlation_id: str) -> AurixEvent:
    return AurixEvent(
        event_type=event_type,
        source=source,
        symbol=symbol,
        correlation_id=correlation_id,
        payload=payload,
        safety=EventSafety(),
    )


def _latest(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    return items[-1] if items else None


def publish_account_event_from_latest_snapshot(event_bus: AurixEventBus, snapshot: dict[str, Any] | None, correlation_id: str | None = None) -> list[dict[str, Any]]:
    if not snapshot or not isinstance(snapshot.get("account"), dict):
        return []
    cid = correlation_id or uuid4().hex
    symbol = str((snapshot.get("tick") or {}).get("symbol") or event_bus.config.symbol)
    return event_bus.publish_many([_event(AurixEventType.ACCOUNT_STATE_EVENT, "bridge_snapshot_collector", symbol, snapshot["account"], cid)])


def publish_market_event_from_latest_snapshot(
    event_bus: AurixEventBus,
    snapshot: dict[str, Any] | None,
    market_quality: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> list[dict[str, Any]]:
    if not snapshot:
        return []
    cid = correlation_id or uuid4().hex
    symbol = str((snapshot.get("tick") or {}).get("symbol") or event_bus.config.symbol)
    events: list[AurixEvent] = []
    tick = snapshot.get("tick")
    if isinstance(tick, dict) and tick:
        events.append(_event(AurixEventType.TICK_EVENT, "bridge_snapshot_collector", symbol, tick, cid))
    candles = snapshot.get("candles")
    if isinstance(candles, list) and candles:
        latest_candle = candles[-1]
        if isinstance(latest_candle, dict):
            events.append(_event(AurixEventType.CANDLE_CLOSED_EVENT, "bridge_snapshot_collector", symbol, latest_candle, cid))
    if isinstance(market_quality, dict) and market_quality:
        events.append(_event(AurixEventType.MARKET_QUALITY_EVENT, "market_quality_collector", symbol, market_quality, cid))
    return event_bus.publish_many(events)


def publish_snapshot_events_from_bridge_state(
    event_bus: AurixEventBus,
    snapshot: dict[str, Any] | None,
    market_quality: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> list[dict[str, Any]]:
    if not snapshot:
        return []
    cid = correlation_id or uuid4().hex
    symbol = str((snapshot.get("tick") or {}).get("symbol") or event_bus.config.symbol)
    events: list[AurixEvent] = []
    events.extend(
        [
            _event(AurixEventType.ACCOUNT_STATE_EVENT, "bridge_snapshot_collector", symbol, snapshot.get("account") or {}, cid),
            _event(AurixEventType.POSITION_STATE_EVENT, "bridge_snapshot_collector", symbol, {"items": snapshot.get("positions") or []}, cid),
            _event(AurixEventType.ORDER_STATE_EVENT, "bridge_snapshot_collector", symbol, {"items": snapshot.get("orders") or []}, cid),
            _event(AurixEventType.TRADE_HISTORY_EVENT, "bridge_snapshot_collector", symbol, {"items": snapshot.get("deals") or []}, cid),
        ]
    )
    if isinstance(snapshot.get("tick"), dict) and snapshot.get("tick"):
        events.append(_event(AurixEventType.TICK_EVENT, "bridge_snapshot_collector", symbol, snapshot["tick"], cid))
    candles = snapshot.get("candles") or []
    if candles and isinstance(candles[-1], dict):
        events.append(_event(AurixEventType.CANDLE_CLOSED_EVENT, "bridge_snapshot_collector", symbol, candles[-1], cid))
    if isinstance(market_quality, dict) and market_quality:
        events.append(_event(AurixEventType.MARKET_QUALITY_EVENT, "market_quality_collector", symbol, market_quality, cid))
    return event_bus.publish_many(events)


def publish_context_event_from_current_context(event_bus: AurixEventBus, context: dict[str, Any] | None, correlation_id: str | None = None) -> list[dict[str, Any]]:
    if not context:
        return []
    cid = correlation_id or uuid4().hex
    symbol = str(context.get("symbol") or event_bus.config.symbol)
    events = [_event(AurixEventType.CONTEXT_STATE_EVENT, "context_observation_collector", symbol, context, cid)]
    if context.get("session_name") or context.get("session_allowed") is not None:
        events.append(
            _event(
                AurixEventType.SESSION_STATE_EVENT,
                "context_observation_collector",
                symbol,
                {
                    "session_name": context.get("session_name"),
                    "session_allowed": context.get("session_allowed"),
                    "current_session": context.get("session_name"),
                    "allowed": context.get("session_allowed"),
                },
                cid,
            )
        )
    return event_bus.publish_many(events)


def publish_existing_signal_event_from_latest_strategy_signal(event_bus: AurixEventBus, signals: list[dict[str, Any]], correlation_id: str | None = None) -> list[dict[str, Any]]:
    latest = _latest(signals)
    if not latest:
        return []
    cid = correlation_id or uuid4().hex
    symbol = str(latest.get("symbol") or event_bus.config.symbol)
    return event_bus.publish_many([_event(AurixEventType.SIGNAL_EVENT, "strategy_signal_observation_collector", symbol, latest, cid)])


def publish_paper_trade_event_from_latest_trade(event_bus: AurixEventBus, trades: list[dict[str, Any]], correlation_id: str | None = None) -> list[dict[str, Any]]:
    latest = _latest(trades)
    if not latest:
        return []
    cid = correlation_id or uuid4().hex
    symbol = str(latest.get("symbol") or event_bus.config.symbol)
    return event_bus.publish_many([_event(AurixEventType.PAPER_TRADE_EVENT, "paper_trade_observation_collector", symbol, latest, cid)])


def publish_paper_risk_event_from_latest_decision(event_bus: AurixEventBus, decision: dict[str, Any] | None, correlation_id: str | None = None) -> list[dict[str, Any]]:
    if not decision:
        return []
    cid = correlation_id or uuid4().hex
    symbol = str(decision.get("symbol") or event_bus.config.symbol)
    return event_bus.publish_many([_event(AurixEventType.PAPER_RISK_DECISION_EVENT, "paper_risk_observation_collector", symbol, decision, cid)])


def publish_safety_state_event(event_bus: AurixEventBus, snapshot: dict[str, Any] | None = None, correlation_id: str | None = None) -> list[dict[str, Any]]:
    cid = correlation_id or uuid4().hex
    raw = snapshot.get("raw") if isinstance(snapshot, dict) else {}
    payload = EventSafety().model_dump()
    payload.update(
        {
            "allow_paper_trade_creation": False,
            "allow_demo_execution": False,
            "require_ea_live_trading_disabled_now": True,
            "ea_allow_live_trading_seen": (raw or {}).get("allow_live_trading") if isinstance(raw, dict) else None,
        }
    )
    return event_bus.publish_many([_event(AurixEventType.SAFETY_STATE_EVENT, "event_bus_safety_collector", event_bus.config.symbol, payload, cid)])


def publish_heartbeat_event(event_bus: AurixEventBus, correlation_id: str | None = None) -> list[dict[str, Any]]:
    cid = correlation_id or uuid4().hex
    payload = {
        "ok": True,
        "time": bridge_utc_now_iso(),
        "mode": event_bus.config.mode,
        "event_bus_only": True,
    }
    return event_bus.publish_many([_event(AurixEventType.SYSTEM_HEARTBEAT_EVENT, "event_bus_heartbeat", event_bus.config.symbol, payload, cid)])


def collect_observation_events(
    *,
    event_bus: AurixEventBus,
    snapshot: dict[str, Any] | None,
    market_quality: dict[str, Any] | None,
    context: dict[str, Any] | None,
    signals: list[dict[str, Any]],
    paper_trades: list[dict[str, Any]],
    latest_paper_risk_decision: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    correlation_id = uuid4().hex
    before_paper_count = len(paper_trades)
    published: list[dict[str, Any]] = []
    published.extend(publish_snapshot_events_from_bridge_state(event_bus, snapshot, market_quality, correlation_id))
    published.extend(publish_context_event_from_current_context(event_bus, context, correlation_id))
    published.extend(publish_existing_signal_event_from_latest_strategy_signal(event_bus, signals, correlation_id))
    published.extend(publish_paper_trade_event_from_latest_trade(event_bus, paper_trades, correlation_id))
    published.extend(publish_paper_risk_event_from_latest_decision(event_bus, latest_paper_risk_decision, correlation_id))
    published.extend(publish_safety_state_event(event_bus, snapshot, correlation_id))
    published.extend(publish_heartbeat_event(event_bus, correlation_id))
    return [
        *published,
        {
            "collector_summary": True,
            "correlation_id": correlation_id,
            "paper_trades_before": before_paper_count,
            "paper_trade_creation_attempted": False,
            "commands_queued": False,
            "mt5_execution_attempted": False,
        },
    ]
