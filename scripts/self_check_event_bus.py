from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_event_bus import AurixEvent, AurixEventBus, AurixEventType, load_event_bus_config, project_events
from aurix_event_bus.models import EventSafety


def sample_snapshot() -> dict[str, Any]:
    return {
        "terminal_id": "AURIX-MAC-001",
        "received_at": "2026-06-09T12:00:00+00:00",
        "account": {"balance": 10000.0, "equity": 10001.0, "currency": "GBP"},
        "tick": {"symbol": "XAUUSDm", "bid": 2300.1, "ask": 2300.3, "spread_points": 20},
        "candles": [{"time": 1, "open": 2300.0, "high": 2301.0, "low": 2299.0, "close": 2300.5}],
        "positions": [],
        "orders": [],
        "deals": [],
        "raw": {"allow_live_trading": False},
    }


def assert_safe_flags(safety: dict[str, Any]) -> None:
    expected = EventSafety().model_dump()
    for key, value in expected.items():
        if safety.get(key) is not value:
            raise AssertionError(f"safety flag {key} expected {value}, got {safety.get(key)}")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        config = load_event_bus_config()
        bus = AurixEventBus(tmpdir, config)

        status = bus.get_latest_status()
        if status["event_count"] != 0 or status["last_sequence"] != 0:
            raise AssertionError(f"empty event bus status is not safe: {status}")
        assert_safe_flags(status["safety"])

        first = bus.publish_event(
            AurixEvent(
                event_type=AurixEventType.TICK_EVENT,
                source="self_check",
                symbol="XAUUSDm",
                correlation_id="corr-1",
                payload={"bid": 2300.1, "ask": 2300.3},
            )
        )
        if first["sequence"] != 1:
            raise AssertionError(f"publish one event should assign sequence 1, got {first}")

        many = bus.publish_many(
            [
                AurixEvent(event_type=AurixEventType.ACCOUNT_STATE_EVENT, source="self_check", symbol="XAUUSDm", correlation_id="corr-1", payload={"balance": 1}),
                AurixEvent(event_type=AurixEventType.CONTEXT_STATE_EVENT, source="self_check", symbol="XAUUSDm", correlation_id="corr-2", payload={"regime": "TEST", "directional_bias": "NEUTRAL"}),
                AurixEvent(event_type=AurixEventType.SIGNAL_EVENT, source="self_check", symbol="XAUUSDm", correlation_id="corr-2", payload={"id": "sig-1", "status": "OBSERVED"}),
                AurixEvent(event_type=AurixEventType.PAPER_TRADE_EVENT, source="self_check", symbol="XAUUSDm", correlation_id="corr-2", payload={"id": "paper-1", "status": "OPEN"}),
            ]
        )
        if [item["sequence"] for item in many] != [2, 3, 4, 5]:
            raise AssertionError(f"publish many did not preserve order: {many}")

        state = bus.get_latest_state()
        if (state.get("market") or {}).get("latest_tick", {}).get("bid") != 2300.1:
            raise AssertionError(f"projector did not update latest tick: {state}")
        if state.get("account", {}).get("balance") != 1:
            raise AssertionError(f"projector did not update account: {state}")
        if state.get("context", {}).get("regime") != "TEST":
            raise AssertionError(f"projector did not update context: {state}")
        if state.get("strategy", {}).get("latest_signal", {}).get("id") != "sig-1":
            raise AssertionError(f"projector did not update signal: {state}")
        if state.get("paper", {}).get("open_count") != 1:
            raise AssertionError(f"projector did not update paper trade count: {state}")
        if len(bus.load_events_by_correlation_id("corr-2")) != 3:
            raise AssertionError("correlation lookup failed")
        assert_safe_flags(first["safety"])

        projected = project_events([AurixEvent(**first)])
        if projected.last_sequence != 1:
            raise AssertionError("direct projector failed")

        reset = bus.reset_event_bus()
        if reset["event_count"] != 0 or bus.get_latest_state()["last_sequence"] != 0:
            raise AssertionError(f"reset failed: {reset}")

    with tempfile.TemporaryDirectory() as tmpdir:
        old_data_dir = os.environ.get("AURIX_DATA_DIR")
        os.environ["AURIX_DATA_DIR"] = tmpdir
        try:
            import importlib

            server = importlib.import_module("aurix_bridge_server.main")
            server.store.save_snapshot(sample_snapshot())
            before_paper = len(server.paper_ledger.list_trades())
            before_commands = len(server.store.list_commands())
            result = server.event_bus_collect()
            after_paper = len(server.paper_ledger.list_trades())
            after_commands = len(server.store.list_commands())
            if after_paper != before_paper or result.get("paper_trades_created") != 0:
                raise AssertionError(f"/event-bus/collect created paper trades: {result}")
            if after_commands != before_commands or result.get("commands_queued") != 0:
                raise AssertionError(f"/event-bus/collect queued commands: {result}")
            if result.get("safety", {}).get("live_execution_allowed") is not False:
                raise AssertionError(f"collect safety wrong: {result}")
        finally:
            if old_data_dir is None:
                os.environ.pop("AURIX_DATA_DIR", None)
            else:
                os.environ["AURIX_DATA_DIR"] = old_data_dir

    event_bus_dir = PROJECT_ROOT / "aurix_event_bus"
    for path in event_bus_dir.rglob("*.py"):
        if "/commands/open-market" in path.read_text(encoding="utf-8"):
            raise AssertionError(f"forbidden command endpoint reference introduced in {path}")

    live_config = (PROJECT_ROOT / "config/live_readiness.yaml").read_text(encoding="utf-8")
    event_config = (PROJECT_ROOT / "config/event_bus.yaml").read_text(encoding="utf-8")
    for text, label in [(live_config, "live_readiness"), (event_config, "event_bus")]:
        if "allow_live_arming: false" not in text:
            raise AssertionError(f"{label} live arming false is not enforced")
        if "allow_live_execution: false" not in text:
            raise AssertionError(f"{label} live execution false is not enforced")
        if "allow_command_queueing: false" not in text:
            raise AssertionError(f"{label} command queueing false is not enforced")

    print("OK: event bus self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
