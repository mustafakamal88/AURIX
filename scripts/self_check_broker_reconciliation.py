from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_broker_reconciliation import BrokerReconciler, load_broker_reconciliation_config
from aurix_broker_reconciliation.config import BrokerReconciliationConfig
from aurix_demo_oms import DemoOmsStore
from aurix_demo_oms.models import OmsOrderRequest
from aurix_event_bus import AurixEventBus, AurixEventType, load_event_bus_config


def snapshot(
    *,
    positions: list[dict[str, Any]] | None = None,
    orders: list[dict[str, Any]] | None = None,
    deals: list[dict[str, Any]] | None = None,
    currency: str = "GBP",
    ea_live: bool = False,
) -> dict[str, Any]:
    return {
        "terminal_id": "AURIX-MAC-001",
        "received_at": "2026-06-09T12:00:00+00:00",
        "account": {"balance": 10000.0, "equity": 10000.0, "currency": currency},
        "tick": {"symbol": "XAUUSDm", "bid": 2300.1, "ask": 2300.3, "spread_points": 20},
        "positions": positions or [],
        "orders": orders or [],
        "deals": deals or [{"ticket": 1, "symbol": "XAUUSDm"}],
        "raw": {"broker_execution_enabled": ea_live},
    }


def mismatch_codes(report: dict[str, Any]) -> set[str]:
    return {str(item.get("code")) for item in report.get("mismatches") or []}


def assert_safe(report: dict[str, Any]) -> None:
    safety = report.get("safety") or {}
    for key in [
        "broker_order_created",
        "broker_order_modified",
        "broker_order_closed",
        "mt5_commands_queued",
        "paper_trade_created",
        "ea_settings_modified",
    ]:
        if safety.get(key) is not False:
            raise AssertionError(f"safety flag {key} expected false: {safety}")


def build(tmpdir: str, config: BrokerReconciliationConfig | None = None, snap: dict[str, Any] | None = None) -> tuple[BrokerReconciler, AurixEventBus]:
    bus = AurixEventBus(tmpdir, load_event_bus_config())
    oms_store = DemoOmsStore(tmpdir)
    reconciler = BrokerReconciler(tmpdir, config or load_broker_reconciliation_config(), event_bus=bus, snapshot_provider=lambda: snap, demo_oms_store=oms_store)
    return reconciler, bus


def main() -> int:
    config_text = (PROJECT_ROOT / "config/broker_reconciliation.yaml").read_text(encoding="utf-8")
    for required in [
        "allow_broker_order_creation: false",
        "allow_broker_order_modification: false",
        "allow_broker_order_close: false",
        "allow_live_execution: false",
        "allow_command_queueing: false",
        "allow_mt5_command_queueing: false",
    ]:
        if required not in config_text:
            raise AssertionError(f"broker reconciliation config does not enforce {required}")

    with tempfile.TemporaryDirectory() as tmpdir:
        reconciler, bus = build(tmpdir, snap=None)
        report = reconciler.run()
        if report["status"] != "NO_BROKER_DATA":
            raise AssertionError(f"no broker data should return NO_BROKER_DATA: {report}")
        assert_safe(report)

        reconciler, bus = build(tmpdir, snap=snapshot())
        report = reconciler.run()
        if report["status"] != "CLEAN":
            raise AssertionError(f"clean empty broker state should be CLEAN: {report}")
        if bus.load_events_by_type(AurixEventType.BROKER_RECONCILIATION_EVENT.value, 5)[-1]["payload"]["report_id"] != report["id"]:
            raise AssertionError("event bus did not receive BROKER_RECONCILIATION_EVENT")

        position = {"ticket": 100, "symbol": "XAUUSDm", "volume": 0.01}
        report = build(tmpdir, snap=snapshot(positions=[position]))[0].run()
        if report["status"] != "MISMATCH" or "unexpected_broker_position" not in mismatch_codes(report):
            raise AssertionError(f"unexpected position did not mismatch: {report}")

        order = {"ticket": 200, "symbol": "XAUUSDm", "volume": 0.01}
        report = build(tmpdir, snap=snapshot(orders=[order]))[0].run()
        if report["status"] != "MISMATCH" or "unexpected_broker_order" not in mismatch_codes(report):
            raise AssertionError(f"unexpected order did not mismatch: {report}")

        oms_store = DemoOmsStore(tmpdir)
        oms_store.reset()
        request = OmsOrderRequest(
            intent_id="intent-1",
            symbol="XAUUSDm",
            direction="BUY",
            order_type="MARKET_BUY",
            volume=0.01,
            status="DRY_RUN_ONLY",
            broker_order_id="broker-1",
        )
        oms_store.add_request(request)
        bus = AurixEventBus(tmpdir, load_event_bus_config())
        reconciler = BrokerReconciler(tmpdir, load_broker_reconciliation_config(), event_bus=bus, snapshot_provider=lambda: snapshot(), demo_oms_store=oms_store)
        report = reconciler.run()
        if report["status"] != "MISMATCH" or "oms_request_has_broker_order_id" not in mismatch_codes(report):
            raise AssertionError(f"OMS broker_order_id did not mismatch: {report}")

        for field, code in [
            ("allow_live_execution", "live_execution_enabled"),
            ("allow_command_queueing", "command_queueing_enabled"),
        ]:
            config = load_broker_reconciliation_config().model_copy(update={field: True})
            report = build(tmpdir, config=config, snap=snapshot())[0].run()
            if report["status"] != "BLOCKED" or code not in mismatch_codes(report):
                raise AssertionError(f"{field}=true did not block: {report}")

        report = build(tmpdir, snap=snapshot(ea_live=True))[0].run()
        if report["status"] != "BLOCKED" or "ea_live_trading_enabled" not in mismatch_codes(report):
            raise AssertionError(f"EA live trading true did not block: {report}")

        reset = reconciler.reset()
        if reset["latest_exists"]:
            raise AssertionError(f"reset failed: {reset}")

    recon_dir = PROJECT_ROOT / "aurix_broker_reconciliation"
    for path in recon_dir.rglob("*.py"):
        if "/commands/open-market" in path.read_text(encoding="utf-8"):
            raise AssertionError(f"forbidden command endpoint reference introduced in {path}")

    print("OK: broker reconciliation self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
