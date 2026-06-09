from __future__ import annotations

from typing import Any

from aurix_demo_oms import DemoOmsStore
from aurix_event_bus import AurixEventBus, AurixEventType

from .adapters import publish_broker_reconciliation_event
from .config import BrokerReconciliationConfig
from .models import (
    AurixExpectedState,
    BrokerAccountSnapshot,
    BrokerHistorySnapshot,
    BrokerOrderSnapshot,
    BrokerPositionSnapshot,
    BrokerReconciliationReport,
    BrokerReconciliationSafety,
    ReconciliationCheck,
    ReconciliationMismatch,
)
from .store import BrokerReconciliationStore


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class BrokerReconciler:
    def __init__(
        self,
        data_dir: str = "data",
        config: BrokerReconciliationConfig | None = None,
        event_bus: AurixEventBus | None = None,
        snapshot_provider: Any | None = None,
        demo_oms_store: DemoOmsStore | None = None,
    ):
        self.config = config or BrokerReconciliationConfig()
        self.store = BrokerReconciliationStore(data_dir, self.config)
        self.event_bus = event_bus
        self.snapshot_provider = snapshot_provider
        self.demo_oms_store = demo_oms_store or DemoOmsStore(data_dir)

    def status(self) -> dict[str, Any]:
        return self.store.status()

    def latest(self) -> dict[str, Any] | None:
        return self.store.latest()

    def history(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.store.history(limit)

    def reset(self) -> dict[str, Any]:
        return self.store.reset()

    def _snapshot(self) -> dict[str, Any] | None:
        if self.snapshot_provider is None:
            return None
        try:
            snapshot = self.snapshot_provider()
        except Exception:
            return None
        return snapshot if isinstance(snapshot, dict) else None

    def _event_bus_enabled(self) -> bool:
        if self.event_bus is None:
            return False
        try:
            return bool(self.event_bus.config.enabled)
        except Exception:
            return False

    def _event_count(self, event_type: AurixEventType) -> int:
        if self.event_bus is None:
            return 0
        try:
            return len(self.event_bus.load_events_by_type(event_type.value, limit=500))
        except Exception:
            return 0

    def run(self) -> dict[str, Any]:
        report = self.reconcile()
        event = publish_broker_reconciliation_event(self.event_bus, report)
        if event:
            report.event_id = event.get("event_id")
        dumped = self.store.add_report(report)
        return dumped

    def reconcile(self) -> BrokerReconciliationReport:
        snapshot = self._snapshot()
        account_raw = _as_dict(snapshot.get("account")) if snapshot else {}
        positions_raw = _as_list(snapshot.get("positions")) if snapshot else []
        orders_raw = _as_list(snapshot.get("orders")) if snapshot else []
        deals_raw = _as_list(snapshot.get("deals")) if snapshot else []
        raw = _as_dict(snapshot.get("raw")) if snapshot else {}
        tick = _as_dict(snapshot.get("tick")) if snapshot else {}
        symbol = tick.get("symbol") or self.config.symbol
        checks: list[ReconciliationCheck] = []
        mismatches: list[ReconciliationMismatch] = []
        warnings: list[str] = []
        recommendations: list[str] = []

        def check(name: str, status: str, message: str) -> None:
            checks.append(ReconciliationCheck(name=name, status=status, message=message))  # type: ignore[arg-type]

        def mismatch(code: str, message: str, severity: str = "MISMATCH", detail: dict[str, Any] | None = None) -> None:
            mismatches.append(ReconciliationMismatch(code=code, message=message, severity=severity, detail=detail or {}))  # type: ignore[arg-type]

        if not self.config.enabled:
            mismatch("config_disabled", "Broker reconciliation config is disabled", "BLOCKED")
            check("config_enabled", "BLOCKED", "config disabled")
        else:
            check("config_enabled", "PASS", "config enabled")
        if self.config.mode != "RECONCILIATION_ONLY":
            mismatch("mode_not_reconciliation_only", f"mode must be RECONCILIATION_ONLY, got {self.config.mode}", "BLOCKED")
            check("mode", "BLOCKED", "mode is not reconciliation-only")
        else:
            check("mode", "PASS", "mode is reconciliation-only")

        for flag, code in [
            (self.config.allow_broker_order_creation, "broker_order_creation_enabled"),
            (self.config.allow_broker_order_modification, "broker_order_modification_enabled"),
            (self.config.allow_broker_order_close, "broker_order_close_enabled"),
            (self.config.allow_demo_execution, "demo_execution_enabled"),
            (self.config.allow_live_execution, "live_execution_enabled"),
            (self.config.allow_live_arming, "live_arming_enabled"),
            (self.config.allow_command_queueing or self.config.allow_mt5_command_queueing, "command_queueing_enabled"),
        ]:
            if flag:
                mismatch(code, f"safety config violation: {code}", "BLOCKED")

        event_bus_ok = self._event_bus_enabled()
        if self.config.require_event_bus_enabled and not event_bus_ok:
            mismatch("event_bus_unavailable", "event bus is required but unavailable", "BLOCKED")
            check("event_bus_available", "BLOCKED", "event bus unavailable")
        else:
            check("event_bus_available", "PASS", "event bus available")

        if snapshot is None or not account_raw:
            warnings.append("broker account data unavailable")
            check("broker_account_data", "WARN", "broker account data unavailable")
        else:
            check("broker_account_data", "PASS", "broker account data available")

        account = BrokerAccountSnapshot(
            balance=_as_float(account_raw.get("balance")),
            equity=_as_float(account_raw.get("equity")),
            currency=account_raw.get("currency"),
            login=account_raw.get("login"),
            server=account_raw.get("server"),
            raw=account_raw,
        ) if account_raw else None

        if account and account.currency and account.currency != self.config.account_currency and self.config.alert_on_account_currency_mismatch:
            mismatch("account_currency_mismatch", f"account currency {account.currency} does not match {self.config.account_currency}")
        elif account and account.currency:
            check("account_currency", "PASS", "account currency matches")
        else:
            warnings.append("account currency unavailable")
            check("account_currency", "WARN", "account currency unavailable")

        if symbol != self.config.symbol and self.config.alert_on_symbol_mismatch:
            mismatch("symbol_mismatch", f"broker symbol {symbol} does not match {self.config.symbol}")
        else:
            check("symbol", "PASS", f"symbol is {symbol}")

        ea_allow_live = raw.get("allow_live_trading")
        if self.config.require_ea_live_trading_disabled_now and ea_allow_live is True:
            mismatch("ea_live_trading_enabled", "EA reports AllowLiveTrading=true", "BLOCKED")
            check("ea_live_trading_disabled", "BLOCKED", "EA live trading is enabled")
        elif ea_allow_live is False:
            check("ea_live_trading_disabled", "PASS", "EA live trading is disabled")
        else:
            warnings.append("EA AllowLiveTrading state unavailable")
            check("ea_live_trading_disabled", "WARN", "EA live trading state unavailable")

        positions = [BrokerPositionSnapshot(ticket=item.get("ticket"), symbol=item.get("symbol"), type=item.get("type"), direction=item.get("direction"), volume=_as_float(item.get("volume")), price_open=_as_float(item.get("price_open")), profit=_as_float(item.get("profit")), raw=item) for item in positions_raw if isinstance(item, dict)]
        orders = [BrokerOrderSnapshot(ticket=item.get("ticket"), symbol=item.get("symbol"), type=item.get("type"), direction=item.get("direction"), volume=_as_float(item.get("volume")), price_open=_as_float(item.get("price_open")), raw=item) for item in orders_raw if isinstance(item, dict)]
        symbol_positions = [item for item in positions if item.symbol == self.config.symbol or item.symbol is None]
        symbol_orders = [item for item in orders if item.symbol == self.config.symbol or item.symbol is None]

        check("broker_positions_readable", "PASS" if snapshot is not None else "WARN", f"positions read: {len(positions)}")
        check("broker_orders_readable", "PASS" if snapshot is not None else "WARN", f"orders read: {len(orders)}")
        if len(symbol_positions) > self.config.expected_max_broker_positions:
            mismatch("unexpected_broker_position", f"unexpected broker positions for {self.config.symbol}: {len(symbol_positions)}", detail={"count": len(symbol_positions)})
        if len(symbol_orders) > self.config.expected_max_broker_orders:
            mismatch("unexpected_broker_order", f"unexpected broker orders for {self.config.symbol}: {len(symbol_orders)}", detail={"count": len(symbol_orders)})

        history = BrokerHistorySnapshot(available=bool(deals_raw), count=len(deals_raw), latest=deals_raw[-1] if deals_raw and isinstance(deals_raw[-1], dict) else None)
        if not deals_raw:
            warnings.append("broker history unavailable or empty")
            check("broker_history_readable", "WARN", "broker history unavailable or empty")
        else:
            check("broker_history_readable", "PASS", f"history records read: {len(deals_raw)}")

        requests = self.demo_oms_store.load_order_requests() if self.demo_oms_store else []
        if self.config.require_demo_oms_available and self.demo_oms_store is None:
            mismatch("demo_oms_unavailable", "Demo OMS store is required but unavailable", "BLOCKED")
        with_mt5_command = [item for item in requests if item.get("mt5_command_id")]
        with_broker_order = [item for item in requests if item.get("broker_order_id")]
        executed_statuses = {"EXECUTED", "FILLED", "ORDER_FILLED", "BROKER_FILLED", "READY_FOR_DEMO_ONLY"}
        executed_requests = [item for item in requests if str(item.get("status") or "").upper() in executed_statuses]
        if with_mt5_command:
            mismatch("oms_request_has_mt5_command_id", "OMS dry-run request has mt5_command_id while command queueing is disabled")
        if with_broker_order:
            mismatch("oms_request_has_broker_order_id", "OMS dry-run request has broker_order_id while execution is disabled")
        if executed_requests:
            mismatch("oms_request_marked_executed", "OMS request is marked executed in dry-run mode")

        filled_events = self._event_count(AurixEventType.ORDER_FILLED_EVENT)
        if filled_events and not deals_raw and not positions:
            mismatch("fill_event_without_broker_support", "ORDER_FILLED_EVENT exists without broker position/history support")

        expected = AurixExpectedState(
            symbol=self.config.symbol,
            expected_broker_positions=self.config.expected_max_broker_positions,
            expected_broker_orders=self.config.expected_max_broker_orders,
            demo_oms_request_count=len(requests),
            latest_demo_oms_request_status=requests[-1].get("status") if requests else None,
            order_requests_with_mt5_command_id=len(with_mt5_command),
            order_requests_with_broker_order_id=len(with_broker_order),
            executed_order_request_count=len(executed_requests),
            order_filled_event_count=filled_events,
        )

        if any(item.severity == "BLOCKED" for item in mismatches):
            status = "BLOCKED"
            recommendations.append("Restore read-only safety flags before continuing.")
        elif snapshot is None or account is None:
            status = "NO_BROKER_DATA"
            recommendations.append("Wait for the MT5 bridge EA to publish a fresh snapshot.")
        elif any(item.severity == "MISMATCH" for item in mismatches):
            status = "MISMATCH"
            recommendations.append("Investigate broker exposure before enabling any future demo command queueing.")
        elif warnings:
            status = "WARNINGS"
            recommendations.append("Review missing non-critical broker data before advancing execution work.")
        else:
            status = "CLEAN"
            recommendations.append("Broker state matches AURIX dry-run/no-execution expectations.")

        return BrokerReconciliationReport(
            symbol=self.config.symbol,
            mode=self.config.mode,
            status=status,  # type: ignore[arg-type]
            account=account,
            broker_positions=positions,
            broker_orders=orders,
            broker_history_summary=history,
            aurix_expected_state=expected,
            checks=checks,
            mismatches=mismatches,
            warnings=warnings,
            recommendations=recommendations,
            safety=BrokerReconciliationSafety(),
        )
