from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_broker_reconciliation import BrokerReconciliationReport, BrokerReconciliationStore, load_broker_reconciliation_config
from aurix_demo_command_queue import DemoCommandQueueAdapter, load_demo_command_queue_config
from aurix_demo_oms import DemoOmsStore
from aurix_demo_oms.models import OmsOrderRequest
from aurix_event_bus import AurixEventBus, AurixEventType, load_event_bus_config


def snapshot(*, positions: list[dict[str, Any]] | None = None, orders: list[dict[str, Any]] | None = None, currency: str = "GBP", ea_live: bool = False, spread: float = 20.0) -> dict[str, Any]:
    return {
        "account": {"balance": 100.0, "equity": 100.0, "currency": currency},
        "tick": {"symbol": "XAUUSDm", "spread_points": spread},
        "positions": positions or [],
        "orders": orders or [],
        "raw": {"broker_execution_enabled": ea_live},
    }


def seed_clean_recon(tmpdir: str) -> BrokerReconciliationStore:
    store = BrokerReconciliationStore(tmpdir, load_broker_reconciliation_config())
    store.add_report(BrokerReconciliationReport(status="CLEAN", account={"balance": 100.0, "equity": 100.0, "currency": "GBP"}))  # type: ignore[arg-type]
    return store


def seed_request(tmpdir: str, **updates: Any) -> DemoOmsStore:
    store = DemoOmsStore(tmpdir)
    store.reset()
    data = {
        "intent_id": "intent-1",
        "symbol": "XAUUSDm",
        "direction": "BUY",
        "order_type": "MARKET_BUY",
        "volume": 0.01,
        "entry_reference": 2300.0,
        "stop_loss": 2299.0,
        "take_profit": 2302.0,
        "status": "DRY_RUN_ONLY",
        "mt5_command_id": None,
        "broker_order_id": None,
    }
    data.update(updates)
    store.add_request(OmsOrderRequest(**data))
    return store


def codes(result: dict[str, Any]) -> set[str]:
    validation = result.get("validation") or {}
    return {str(item.get("code")) for item in validation.get("rejection_reasons") or []}


def assert_safe(result: dict[str, Any]) -> None:
    payload = result.get("payload") or {}
    if payload and (payload.get("mt5_command_id") is not None or payload.get("queued_at") is not None or payload.get("broker_order_id") is not None):
        raise AssertionError(f"payload created executable IDs: {payload}")
    safety = result.get("safety") or payload.get("safety") or {}
    for key in ["mt5_commands_queued", "broker_order_created", "paper_trade_created", "ea_settings_modified"]:
        if safety.get(key) is not False:
            raise AssertionError(f"safety flag {key} expected false: {safety}")


def make_adapter(tmpdir: str, *, config=None, oms_store=None, recon_store=None, snap=None, bus=None) -> DemoCommandQueueAdapter:
    return DemoCommandQueueAdapter(
        tmpdir,
        config or load_demo_command_queue_config(),
        event_bus=bus or AurixEventBus(tmpdir, load_event_bus_config()),
        snapshot_provider=lambda: snap or snapshot(),
        demo_oms_store=oms_store or seed_request(tmpdir),
        broker_reconciliation_store=recon_store or seed_clean_recon(tmpdir),
    )


def main() -> int:
    config_text = (PROJECT_ROOT / "config/demo_command_queue.yaml").read_text(encoding="utf-8")
    for required in ["allow_demo_command_queueing: false", "allow_mt5_command_queueing: false", "allow_demo_execution: false", "allow_live_execution: false", "allow_real_account_execution: false", "manual_demo_arm: false"]:
        if required not in config_text:
            raise AssertionError(f"demo command queue config missing {required}")

    with tempfile.TemporaryDirectory() as tmpdir:
        adapter = make_adapter(tmpdir)
        status = adapter.get_demo_command_queue_status()
        if status["preview_count"] != 0 or status["payload_count"] != 0:
            raise AssertionError(f"empty queue status is not safe: {status}")

        preview_result = adapter.preview_latest_oms_request()
        if not preview_result.get("preview", {}).get("id"):
            raise AssertionError(f"valid mock OMS request did not create preview: {preview_result}")
        assert_safe(preview_result)

        dry = adapter.dry_run_latest_oms_request()
        if not dry.get("payload", {}).get("id"):
            raise AssertionError(f"valid mock OMS request did not create dry-run payload: {dry}")
        if dry["payload"]["status"] not in {"QUEUE_DISABLED", "BLOCKED", "DRY_RUN_ONLY"}:
            raise AssertionError(f"unexpected payload status: {dry}")
        if "manual_demo_arm_false" not in codes(dry) or "demo_command_queueing_disabled" not in codes(dry):
            raise AssertionError(f"default-off queue gates not enforced: {dry}")
        assert_safe(dry)

        bad_recon = BrokerReconciliationStore(tmpdir, load_broker_reconciliation_config())
        bad_recon.add_report(BrokerReconciliationReport(status="MISMATCH"))
        blocked = make_adapter(tmpdir, recon_store=bad_recon).dry_run_latest_oms_request()
        if "broker_reconciliation_not_clean" not in codes(blocked):
            raise AssertionError(f"broker reconciliation not clean did not block: {blocked}")

        for field, code in [("allow_live_execution", "live_execution_enabled"), ("allow_real_account_execution", "real_account_execution_enabled")]:
            config = load_demo_command_queue_config().model_copy(update={field: True})
            result = make_adapter(tmpdir, config=config).dry_run_latest_oms_request()
            if code not in codes(result):
                raise AssertionError(f"{field}=true did not enforce {code}: {result}")

        wrong = make_adapter(tmpdir, oms_store=seed_request(tmpdir, symbol="EURUSD")).dry_run_latest_oms_request()
        if "symbol_mismatch" not in codes(wrong):
            raise AssertionError(f"wrong symbol not rejected: {wrong}")

        volume = make_adapter(tmpdir, oms_store=seed_request(tmpdir, volume=0.02)).dry_run_latest_oms_request()
        if "volume_above_max" not in codes(volume):
            raise AssertionError(f"above max volume not rejected: {volume}")

        open_position = make_adapter(tmpdir, snap=snapshot(positions=[{"symbol": "XAUUSDm", "ticket": 1}])).dry_run_latest_oms_request()
        if "open_broker_position" not in codes(open_position):
            raise AssertionError(f"open broker position not rejected: {open_position}")

        bus = AurixEventBus(tmpdir, load_event_bus_config())
        event_adapter = make_adapter(tmpdir, bus=bus)
        event_adapter.dry_run_latest_oms_request()
        if not bus.load_events_by_type(AurixEventType.DEMO_COMMAND_PREVIEW_EVENT.value, 10):
            raise AssertionError("event bus did not receive DEMO_COMMAND_PREVIEW_EVENT")
        if not bus.load_events_by_type(AurixEventType.DEMO_COMMAND_QUEUE_EVENT.value, 10):
            raise AssertionError("event bus did not receive DEMO_COMMAND_QUEUE_EVENT")

        reset = adapter.reset_demo_command_queue()
        if reset["preview_count"] != 0 or reset["payload_count"] != 0:
            raise AssertionError(f"reset failed: {reset}")

    queue_dir = PROJECT_ROOT / "aurix_demo_command_queue"
    for path in queue_dir.rglob("*.py"):
        if "/commands/open-market" in path.read_text(encoding="utf-8"):
            raise AssertionError(f"forbidden command endpoint reference introduced in {path}")

    print("OK: demo command queue self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
