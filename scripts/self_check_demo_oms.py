from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_demo_oms import DemoOms, load_demo_oms_config
from aurix_event_bus import AurixEvent, AurixEventBus, AurixEventType, load_event_bus_config


def snapshot(spread: float = 20.0, currency: str = "GBP", ea_live: bool = False) -> dict[str, Any]:
    return {
        "terminal_id": "AURIX-MAC-001",
        "received_at": "2026-06-09T12:00:00+00:00",
        "account": {"balance": 10000.0, "equity": 10000.0, "currency": currency},
        "tick": {"symbol": "XAUUSDm", "bid": 2300.1, "ask": 2300.3, "spread_points": spread},
        "positions": [],
        "orders": [],
        "raw": {"broker_execution_enabled": ea_live},
    }


def signal_event(**overrides: Any) -> AurixEvent:
    payload = {
        "id": "eval-1",
        "signal_id": "sig-1",
        "strategy_name": "fast_rsi_first_reversal",
        "strategy_version": "0.1.0",
        "symbol": "XAUUSDm",
        "status": "SIGNAL",
        "direction": "BUY",
        "entry_reference": 2300.2,
        "stop_loss_reference": 2299.2,
        "take_profit_reference": 2302.2,
        "volume": 0.01,
        "confidence": 0.8,
        "setup_reason": "self-check",
        "decision_trace": {"source": "self_check"},
        "command_id": None,
    }
    payload.update(overrides.pop("payload", {}))
    return AurixEvent(
        event_type=overrides.pop("event_type", AurixEventType.SIGNAL_EVENT),
        source="self_check",
        symbol=payload.get("symbol", "XAUUSDm"),
        correlation_id="self-check-corr",
        payload=payload,
        **overrides,
    )


def assert_safe(result: dict[str, Any]) -> None:
    request = result.get("request") or {}
    safety = result.get("safety") or {}
    if request.get("mt5_command_id") is not None:
        raise AssertionError(f"MT5 command id was created: {request}")
    if request.get("broker_order_id") is not None:
        raise AssertionError(f"broker order id was created: {request}")
    for key in ["paper_trade_created", "mt5_commands_queued", "broker_order_created", "ea_settings_modified"]:
        if safety.get(key) is not False:
            raise AssertionError(f"safety flag {key} expected false: {safety}")


def codes(result: dict[str, Any]) -> set[str]:
    validation = result.get("validation") or {}
    return {str(item.get("code")) for item in validation.get("rejection_reasons") or []}


def main() -> int:
    config_text = (PROJECT_ROOT / "config/demo_oms.yaml").read_text(encoding="utf-8")
    for required in [
        "allow_demo_execution: false",
        "allow_live_execution: false",
        "allow_real_account_execution: false",
        "allow_command_queueing: false",
        "allow_demo_command_queueing: false",
    ]:
        if required not in config_text:
            raise AssertionError(f"Demo OMS config does not enforce {required}")

    with tempfile.TemporaryDirectory() as tmpdir:
        config = load_demo_oms_config()
        bus = AurixEventBus(tmpdir, load_event_bus_config())
        current_snapshot = snapshot()
        oms = DemoOms(tmpdir, config, event_bus=bus, snapshot_provider=lambda: current_snapshot)

        status = oms.get_demo_oms_status()
        if status["order_intent_count"] != 0 or status["order_request_count"] != 0:
            raise AssertionError(f"empty OMS status is not safe: {status}")
        if any(status.get(key) for key in ["demo_execution_allowed", "live_execution_allowed", "command_queueing_allowed", "broker_order_created", "mt5_commands_queued"]):
            raise AssertionError(f"empty OMS safety flags are not safe: {status}")

        published_signal = bus.publish_event(signal_event())
        result = oms.process_signal_event(published_signal)
        assert_safe(result)
        if result["intent"]["status"] != "DRY_RUN_READY":
            raise AssertionError(f"valid mock signal did not create dry-run-ready intent: {result}")
        if result["request"]["status"] != "DRY_RUN_ONLY":
            raise AssertionError(f"valid mock signal did not create dry-run request: {result}")
        state = bus.get_latest_state()
        latest_request = (state.get("execution") or {}).get("latest_order_request") or {}
        if latest_request.get("id") != result["request"]["id"]:
            raise AssertionError(f"event bus did not receive ORDER_REQUEST_EVENT dry-run form: {state}")

        oms.reset_demo_oms()
        blocked = oms.process_signal_event(bus.publish_event(signal_event(payload={"command_id": "cmd-1"})))
        if "signal_command_id_present" not in codes(blocked):
            raise AssertionError(f"non-null command_id was not rejected: {blocked}")
        assert_safe(blocked)

        oms.reset_demo_oms()
        wrong_symbol = oms.process_signal_event(bus.publish_event(signal_event(payload={"symbol": "EURUSD"})))
        if "symbol_mismatch" not in codes(wrong_symbol):
            raise AssertionError(f"wrong symbol was not rejected: {wrong_symbol}")

        oms.reset_demo_oms()
        volume = oms.process_signal_event(bus.publish_event(signal_event(payload={"volume": 0.02})))
        if "volume_above_max" not in codes(volume):
            raise AssertionError(f"above-max volume was not rejected: {volume}")

        oms.reset_demo_oms()
        current_snapshot = snapshot(spread=300)
        spread = oms.process_signal_event(bus.publish_event(signal_event()))
        if "spread_above_max" not in codes(spread):
            raise AssertionError(f"above-max spread was not rejected: {spread}")

        oms.reset_demo_oms()
        bad_config = config.model_copy(update={"allow_real_account_execution": True})
        bad_oms = DemoOms(tmpdir, bad_config, event_bus=bus, snapshot_provider=lambda: snapshot())
        real = bad_oms.process_signal_event(bus.publish_event(signal_event()))
        if "real_account_execution_enabled" not in codes(real):
            raise AssertionError(f"real account execution was not blocked: {real}")

        for field, code in [
            ("allow_live_execution", "live_execution_enabled"),
            ("allow_demo_execution", "demo_execution_enabled"),
            ("allow_command_queueing", "command_queueing_enabled"),
        ]:
            bad_oms = DemoOms(tmpdir, config.model_copy(update={field: True}), event_bus=bus, snapshot_provider=lambda: snapshot())
            result = bad_oms.process_signal_event(bus.publish_event(signal_event()))
            if code not in codes(result):
                raise AssertionError(f"{field}=true did not enforce {code}: {result}")

        no_risk_oms = DemoOms(tmpdir, config, event_bus=bus, snapshot_provider=lambda: None)
        no_risk_oms.reset_demo_oms()
        risk = no_risk_oms.process_signal_event(bus.publish_event(signal_event()))
        if "risk_governor_validation_unavailable" not in codes(risk):
            raise AssertionError(f"risk unavailable did not block deterministically: {risk}")

        reset = no_risk_oms.reset_demo_oms()
        if reset["order_intent_count"] != 0 or reset["order_request_count"] != 0:
            raise AssertionError(f"reset failed: {reset}")

    oms_dir = PROJECT_ROOT / "aurix_demo_oms"
    for path in oms_dir.rglob("*.py"):
        if "/commands/open-market" in path.read_text(encoding="utf-8"):
            raise AssertionError(f"forbidden command endpoint reference introduced in {path}")

    print("OK: demo OMS self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
