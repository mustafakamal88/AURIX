from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
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
    age_seconds: int = 0,
    account: dict[str, Any] | None = None,
) -> dict[str, Any]:
    received_at = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    return {
        "terminal_id": "AURIX-MAC-001",
        "received_at": received_at.isoformat(),
        "account": account or {"balance": 10000.0, "equity": 10000.0, "currency": currency},
        "tick": {"symbol": "XAUUSDm", "bid": 2300.1, "ask": 2300.3, "spread_points": 20, "time": received_at.isoformat()},
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
        if report["status"] != "UNKNOWN" or "required MT5 broker snapshot/account data missing" not in report.get("reasons", []):
            raise AssertionError(f"no broker data should return UNKNOWN with exact reason: {report}")
        assert_safe(report)

        reconciler, bus = build(tmpdir, snap=snapshot())
        report = reconciler.run()
        if report["status"] != "CLEAN":
            raise AssertionError(f"clean empty broker state should be CLEAN: {report}")
        if bus.load_events_by_type(AurixEventType.BROKER_RECONCILIATION_EVENT.value, 5)[-1]["payload"]["report_id"] != report["id"]:
            raise AssertionError("event bus did not receive BROKER_RECONCILIATION_EVENT")

        live_style = snapshot(
            positions=[],
            orders=[],
            deals=[],
            account={"balance": None, "equity": None, "currency": "GBP", "raw": {"balance": 108.76, "equity": 108.76}},
        )
        reconciler, _ = build(tmpdir, snap=live_style)
        report = reconciler.run()
        report_file = Path(tmpdir) / "broker_reconciliation" / "report.json"
        if not report_file.exists():
            raise AssertionError("live broker reconciliation report file was not generated")
        live_report = reconciler.latest()
        if not live_report:
            raise AssertionError("live broker reconciliation report path did not load")
        expected_clean_fields = {
            "status": "CLEAN",
            "positions_count": 0,
            "orders_count": 0,
            "expected_positions_count": 0,
            "expected_orders_count": 0,
            "unexpected_exposure": False,
            "mismatches_count": 0,
        }
        for key, expected in expected_clean_fields.items():
            if live_report.get(key) != expected:
                raise AssertionError(f"live clean report field {key} expected {expected}: {live_report}")
        account_report = live_report.get("account") or {}
        if account_report.get("balance") != 108.76 or account_report.get("equity") != 108.76:
            raise AssertionError(f"raw account balance/equity were not normalized: {live_report}")
        if (live_report.get("snapshot_age_seconds") or 999999) > 10:
            raise AssertionError(f"live snapshot age should be small: {live_report}")

        stale_report = build(tmpdir, snap=snapshot(age_seconds=600))[0].run()
        if stale_report["status"] != "UNKNOWN" or "MT5 snapshot stale" not in stale_report.get("reasons", []):
            raise AssertionError(f"stale broker snapshot should be UNKNOWN: {stale_report}")

        position = {"ticket": 100, "symbol": "XAUUSDm", "volume": 0.01}
        report = build(tmpdir, snap=snapshot(positions=[position]))[0].run()
        if report["status"] != "DIRTY" or "unexpected_broker_position" not in mismatch_codes(report):
            raise AssertionError(f"unexpected position did not mismatch: {report}")

        order = {"ticket": 200, "symbol": "XAUUSDm", "volume": 0.01}
        report = build(tmpdir, snap=snapshot(orders=[order]))[0].run()
        if report["status"] != "DIRTY" or "unexpected_broker_order" not in mismatch_codes(report):
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
        if report["status"] != "DIRTY" or "oms_request_has_broker_order_id" not in mismatch_codes(report):
            raise AssertionError(f"OMS broker_order_id did not mismatch: {report}")

        for field, code in [
            ("allow_live_execution", "live_execution_enabled"),
            ("allow_command_queueing", "command_queueing_enabled"),
        ]:
            config = load_broker_reconciliation_config().model_copy(update={field: True})
            report = build(tmpdir, config=config, snap=snapshot())[0].run()
            if report["status"] != "DIRTY" or code not in mismatch_codes(report):
                raise AssertionError(f"{field}=true did not block: {report}")

        report = build(tmpdir, snap=snapshot(ea_live=True))[0].run()
        if report["status"] != "DIRTY" or "ea_live_trading_enabled" not in mismatch_codes(report):
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
