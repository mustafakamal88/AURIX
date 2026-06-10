from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_broker_reconciliation import BrokerReconciliationReport, BrokerReconciliationStore
from aurix_dashboard_runtime import build_runtime_dashboard_summary
from aurix_decision_engine import AurixDecisionEngine, load_decision_engine_config
from aurix_decision_engine.config import DecisionEngineConfig
from aurix_demo_command_queue import DemoCommandQueueStore
from aurix_demo_oms import DemoOmsStore
from aurix_event_bus import AurixEvent, AurixEventBus, AurixEventType, load_event_bus_config
from aurix_strategy_agents import load_strategy_agent_config, StrategyAgentRegistry
from aurix_strategy_agents.evaluator import StrategyAgentStore


def snapshot(spread: float = 20.0, ea_live: bool = False) -> dict[str, Any]:
    return {"account": {"balance": 100.0, "equity": 100.0, "currency": "GBP"}, "tick": {"symbol": "XAUUSDm", "bid": 2300.0, "ask": 2300.2, "spread_points": spread}, "positions": [], "orders": [], "raw": {"broker_execution_enabled": ea_live}}


def seed_strategy(tmpdir: str, items: list[dict[str, Any]]) -> StrategyAgentStore:
    config = load_strategy_agent_config()
    registry = StrategyAgentRegistry(config, tmpdir)
    store = StrategyAgentStore(tmpdir, config)
    store._write_json_atomic(store.latest_file, items)
    store._write_json_atomic(store.status_file, store.status(registry))
    return store


def seed_broker(tmpdir: str, status: str = "CLEAN", positions: int = 0, orders: int = 0) -> BrokerReconciliationStore:
    store = BrokerReconciliationStore(tmpdir)
    store.add_report(BrokerReconciliationReport(status=status, broker_positions=[{"symbol": "XAUUSDm"} for _ in range(positions)], broker_orders=[{"symbol": "XAUUSDm"} for _ in range(orders)]))  # type: ignore[arg-type]
    return store


def bus(tmpdir: str, spread: float = 20.0) -> AurixEventBus:
    event_bus = AurixEventBus(tmpdir, load_event_bus_config())
    event_bus.publish_event(AurixEvent(event_type=AurixEventType.TICK_EVENT, source="self_check", symbol="XAUUSDm", payload={"spread_points": spread, "bid": 1, "ask": 2}))
    event_bus.publish_event(AurixEvent(event_type=AurixEventType.SESSION_STATE_EVENT, source="self_check", symbol="XAUUSDm", payload={"session_allowed": True}))
    return event_bus


def signal(direction: str = "BUY", confidence: float = 0.8) -> dict[str, Any]:
    return {"id": f"sig-{direction}", "agent_id": "fast_rsi_first_reversal_v1", "strategy_name": "fast_rsi_first_reversal", "strategy_version": "1.0.0", "symbol": "XAUUSDm", "status": "SIGNAL", "direction": direction, "confidence": confidence, "setup_reason": "self-check", "command_id": None}


def engine(tmpdir: str, *, event_bus=None, strategy=None, broker=None, snap=None, config=None) -> AurixDecisionEngine:
    return AurixDecisionEngine(
        tmpdir,
        config or load_decision_engine_config(),
        event_bus=event_bus,
        snapshot_provider=lambda: snap if snap is not None else snapshot(),
        strategy_agent_store=strategy or seed_strategy(tmpdir, []),
        demo_oms_store=DemoOmsStore(tmpdir),
        broker_reconciliation_store=broker or seed_broker(tmpdir),
        demo_command_queue_store=DemoCommandQueueStore(tmpdir),
        risk_status_provider=lambda: {"can_trade": True},
    )


def assert_no_side_effects(tmpdir: str, before_oms: int, before_payloads: int = 0) -> None:
    if len(DemoOmsStore(tmpdir).load_order_requests()) != before_oms:
        raise AssertionError("decision engine created OMS order requests")
    if len(DemoCommandQueueStore(tmpdir).load_payloads()) != before_payloads:
        raise AssertionError("decision engine queued MT5 command payloads")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        before_oms = len(DemoOmsStore(tmpdir).load_order_requests())
        before_payloads = len(DemoCommandQueueStore(tmpdir).load_payloads())
        report = engine(tmpdir, event_bus=None).evaluate()
        if report["action"] != "SYSTEM_NOT_READY":
            raise AssertionError(f"no runtime state should be SYSTEM_NOT_READY: {report}")
        assert_no_side_effects(tmpdir, before_oms, before_payloads)

        report = engine(tmpdir, event_bus=bus(tmpdir), strategy=seed_strategy(tmpdir, [signal()]), broker=seed_broker(tmpdir, "MISMATCH", 1, 0)).evaluate()
        if report["action"] != "BLOCKED_BY_BROKER_STATE":
            raise AssertionError(f"broker mismatch did not block: {report}")

        report = engine(tmpdir, event_bus=bus(tmpdir, 300), strategy=seed_strategy(tmpdir, [signal()]), snap=snapshot(300)).evaluate()
        if report["action"] != "BLOCKED_BY_SPREAD":
            raise AssertionError(f"spread did not block: {report}")

        report = engine(tmpdir, event_bus=bus(tmpdir), strategy=seed_strategy(tmpdir, [])).evaluate()
        if report["action"] != "BLOCKED_BY_NO_SIGNAL":
            raise AssertionError(f"no signal did not block: {report}")

        report = engine(tmpdir, event_bus=bus(tmpdir), strategy=seed_strategy(tmpdir, [signal(confidence=0.4)])).evaluate()
        if report["action"] != "BLOCKED_BY_LOW_CONFIDENCE":
            raise AssertionError(f"low confidence did not block: {report}")

        report = engine(tmpdir, event_bus=bus(tmpdir), strategy=seed_strategy(tmpdir, [signal("BUY", 0.9)])).evaluate()
        if report["action"] != "TRADE_LONG":
            raise AssertionError(f"BUY signal did not produce TRADE_LONG advisory: {report}")
        if report["status"] != "READY":
            raise AssertionError(f"actionable advisory decision should be READY: {report}")
        if report["execution_view"].get("order_request_created") is not False or report["execution_view"].get("mt5_command_queued") is not False:
            raise AssertionError(f"decision engine implied execution side effects: {report}")
        assert_no_side_effects(tmpdir, before_oms, before_payloads)

        report = engine(tmpdir, event_bus=bus(tmpdir), strategy=seed_strategy(tmpdir, [signal("SELL", 0.9)])).evaluate()
        if report["action"] != "TRADE_SHORT":
            raise AssertionError(f"SELL signal did not produce TRADE_SHORT advisory: {report}")
        assert_no_side_effects(tmpdir, before_oms, before_payloads)

        config = load_decision_engine_config().model_copy(update={"autonomy_level": "OBSERVE_ONLY"})
        report = engine(tmpdir, event_bus=bus(tmpdir), strategy=seed_strategy(tmpdir, [signal("BUY", 0.9)]), config=config).evaluate()
        if report["action"] in {"TRADE_LONG", "TRADE_SHORT"}:
            raise AssertionError(f"OBSERVE_ONLY returned trade action: {report}")

        for update in [{"allow_live_execution": True}]:
            cfg = load_decision_engine_config().model_copy(update=update)
            report = engine(tmpdir, event_bus=bus(tmpdir), strategy=seed_strategy(tmpdir, [signal()]), config=cfg).evaluate()
            if report["action"] != "SYSTEM_NOT_READY":
                raise AssertionError(f"safety violation did not produce SYSTEM_NOT_READY: {report}")
            assert_no_side_effects(tmpdir, before_oms, before_payloads)

        report = engine(tmpdir, event_bus=bus(tmpdir), strategy=seed_strategy(tmpdir, [signal()]), snap=snapshot(ea_live=True)).evaluate()
        if report["action"] not in {"TRADE_LONG", "TRADE_SHORT"} or report["status"] != "READY":
            raise AssertionError(f"EA broker execution state should not block advisory decision result: {report}")
        assert_no_side_effects(tmpdir, before_oms, before_payloads)

        legacy_config_data = load_decision_engine_config().model_dump()
        legacy_config_data["allow_mt5_command_queueing"] = True
        cfg = DecisionEngineConfig(**legacy_config_data)
        if "allow_mt5_command_queueing" in cfg.model_dump() or hasattr(cfg, "allow_mt5_command_queueing"):
            raise AssertionError("legacy allow_mt5_command_queueing became an active config field")
        report = engine(tmpdir, event_bus=bus(tmpdir), strategy=seed_strategy(tmpdir, [signal("BUY", 0.9)]), config=cfg).evaluate()
        if report["action"] not in {"TRADE_LONG", "TRADE_SHORT"} or report["status"] != "READY":
            raise AssertionError(f"legacy unknown config key changed advisory runtime behavior: {report}")
        if report["execution_view"].get("order_request_created") is not False or report["execution_view"].get("mt5_command_queued") is not False:
            raise AssertionError(f"advisory decision implied command/order creation: {report}")
        assert_no_side_effects(tmpdir, before_oms, before_payloads)

        dashboard_summary = build_runtime_dashboard_summary(tmpdir).model_dump(mode="json")
        dashboard_safety = dashboard_summary["safety"]
        dashboard_cockpit = dashboard_summary["broker_execution_cockpit"]
        if dashboard_safety["read_only_dashboard"] is not True or dashboard_cockpit["no_commands_from_dashboard"] is not True:
            raise AssertionError(f"dashboard read-only safety flags wrong: {dashboard_safety}")
        if dashboard_safety["order_request_creation_allowed"] is not False or dashboard_safety["mt5_commands_queued"] is not False:
            raise AssertionError(f"dashboard read-only path allows command/order creation: {dashboard_safety}")
        if dashboard_summary["demo_command_queue"].get("mt5_delivery_state") != "NO_COMMAND":
            raise AssertionError(f"dashboard summary should not queue MT5 command: {dashboard_summary['demo_command_queue']}")
        assert_no_side_effects(tmpdir, before_oms, before_payloads)

        event_bus = bus(tmpdir)
        report = engine(tmpdir, event_bus=event_bus, strategy=seed_strategy(tmpdir, [signal()])).evaluate()
        if not event_bus.load_events_by_type(AurixEventType.AURIX_DECISION_EVENT.value, 10):
            raise AssertionError("event bus did not receive AURIX_DECISION_EVENT")

        reset = engine(tmpdir).reset()
        if reset["latest_exists"]:
            raise AssertionError(f"reset failed: {reset}")

    for path in (PROJECT_ROOT / "aurix_decision_engine").rglob("*.py"):
        if "/commands/open-market" in path.read_text(encoding="utf-8"):
            raise AssertionError(f"forbidden command endpoint reference introduced in {path}")

    print("OK: decision engine self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
