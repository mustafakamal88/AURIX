from __future__ import annotations

from typing import Any

from aurix_broker_reconciliation import BrokerReconciliationStore
from aurix_demo_command_queue import DemoCommandQueueStore
from aurix_demo_oms import DemoOmsStore
from aurix_event_bus import AurixEventBus
from aurix_strategy_agents.evaluator import StrategyAgentStore

from .autonomy import apply_autonomy
from .config import DecisionEngineConfig
from .models import (
    AurixDecisionAction,
    AurixDecisionInput,
    AurixDecisionReason,
    AurixDecisionRecommendation,
    AurixDecisionReport,
    AurixDecisionSourceState,
    AurixDecisionStatus,
)
from .router import publish_decision_events
from .scoring import calculate_score
from .store import DecisionEngineStore


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class AurixDecisionEngine:
    def __init__(
        self,
        data_dir: str = "data",
        config: DecisionEngineConfig | None = None,
        event_bus: AurixEventBus | None = None,
        snapshot_provider: Any | None = None,
        strategy_agent_store: StrategyAgentStore | None = None,
        demo_oms_store: DemoOmsStore | None = None,
        broker_reconciliation_store: BrokerReconciliationStore | None = None,
        demo_command_queue_store: DemoCommandQueueStore | None = None,
        risk_status_provider: Any | None = None,
    ):
        self.config = config or DecisionEngineConfig()
        self.store = DecisionEngineStore(data_dir, self.config)
        self.event_bus = event_bus
        self.snapshot_provider = snapshot_provider
        self.strategy_agent_store = strategy_agent_store or StrategyAgentStore(data_dir)
        self.demo_oms_store = demo_oms_store or DemoOmsStore(data_dir)
        self.broker_reconciliation_store = broker_reconciliation_store or BrokerReconciliationStore(data_dir)
        self.demo_command_queue_store = demo_command_queue_store or DemoCommandQueueStore(data_dir)
        self.risk_status_provider = risk_status_provider

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
            value = self.snapshot_provider()
        except Exception:
            return None
        return value if isinstance(value, dict) else None

    def _runtime_state(self) -> dict[str, Any]:
        if self.event_bus is None:
            return {}
        try:
            return self.event_bus.get_latest_state()
        except Exception:
            return {}

    def _risk_status(self) -> dict[str, Any]:
        if self.risk_status_provider is None:
            return {}
        try:
            value = self.risk_status_provider()
        except Exception:
            return {}
        return value if isinstance(value, dict) else {}

    def evaluate(self) -> dict[str, Any]:
        report = self.build_decision()
        _, decision_event = publish_decision_events(self.event_bus, report)
        if decision_event:
            report.event_id = decision_event.get("event_id")
        return self.store.add_report(report)

    def build_input(self) -> AurixDecisionInput:
        return AurixDecisionInput(
            runtime_state=self._runtime_state(),
            strategy_agents_status=self.strategy_agent_store._read_json(self.strategy_agent_store.status_file, {}) if hasattr(self.strategy_agent_store, "_read_json") else {},
            strategy_agent_latest=self.strategy_agent_store.latest(),
            broker_reconciliation=self.broker_reconciliation_store.latest() or {},
            demo_oms_status=self.demo_oms_store.status(),
            demo_command_queue_status=self.demo_command_queue_store.status(),
            snapshot=self._snapshot(),
        )

    def _select_signal(self, latest: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, bool]:
        low_conf = False
        for strategy in self.config.strategy_priority:
            matches = [item for item in latest if item.get("strategy_name") == strategy or item.get("agent_id") == strategy]
            for item in reversed(matches):
                if item.get("status") != "SIGNAL":
                    continue
                if item.get("direction") not in {"BUY", "SELL"}:
                    continue
                if item.get("command_id") is not None:
                    continue
                confidence = float(item.get("confidence") or 0.0)
                if confidence < self.config.min_signal_confidence:
                    low_conf = True
                    continue
                return item, low_conf
        return None, low_conf

    def build_decision(self) -> AurixDecisionReport:
        data = self.build_input()
        snapshot = _as_dict(data.snapshot)
        account = _as_dict(snapshot.get("account"))
        tick = _as_dict(snapshot.get("tick"))
        raw = _as_dict(snapshot.get("raw"))
        runtime = data.runtime_state
        broker = data.broker_reconciliation
        demo_oms = data.demo_oms_status
        queue = data.demo_command_queue_status
        risk = self._risk_status()
        reasons: list[AurixDecisionReason] = []
        blocks: list[AurixDecisionReason] = []
        warnings: list[str] = []

        def reason(code: str, message: str) -> AurixDecisionReason:
            return AurixDecisionReason(code=code, message=message)

        def block(code: str, message: str) -> None:
            blocks.append(reason(code, message))

        source = AurixDecisionSourceState(
            event_bus_available=bool(runtime),
            strategy_agent_available=bool(data.strategy_agent_latest or data.strategy_agents_status),
            broker_reconciliation_available=bool(broker),
            demo_oms_available=bool(demo_oms),
            demo_command_queue_available=bool(queue),
            account_available=bool(account),
            market_available=bool(tick),
        )

        safety_violation = False
        if not self.config.enabled or self.config.mode != "DECISION_ONLY":
            safety_violation = True
            block("decision_engine_config_invalid", "decision engine config is disabled or not DECISION_ONLY")
        for flag, code in [
            (self.config.allow_order_request_creation, "order_request_creation_enabled"),
            (self.config.allow_demo_command_queueing or self.config.allow_mt5_command_queueing, "command_queueing_enabled"),
            (self.config.allow_demo_execution or self.config.allow_live_execution, "execution_enabled"),
            (self.config.allow_live_arming, "live_arming_enabled"),
            (self.config.allow_real_account_execution, "real_account_execution_enabled"),
            (self.config.allow_paper_trade_creation, "paper_trade_creation_enabled"),
        ]:
            if flag:
                safety_violation = True
                block(code, f"safety config violation: {code}")
        if self.config.require_event_bus_state and not runtime:
            block("event_bus_state_missing", "event bus runtime state is unavailable")
        if self.config.require_strategy_agent_status and not source.strategy_agent_available:
            block("strategy_agent_state_missing", "strategy agent state is unavailable")
        if self.config.require_ea_live_trading_disabled_now and raw.get("broker_execution_enabled") is True:
            safety_violation = True
            block("ea_live_trading_enabled", "EA reports AURIX_BROKER_EXECUTION=true")
        if self.config.require_account_currency_match and account.get("currency") and account.get("currency") != self.config.account_currency:
            block("account_currency_mismatch", f"account currency {account.get('currency')} does not match {self.config.account_currency}")
        if self.config.require_symbol_match and tick.get("symbol") and tick.get("symbol") != self.config.symbol:
            block("symbol_mismatch", f"market symbol {tick.get('symbol')} does not match {self.config.symbol}")

        broker_clean = broker.get("status") == "CLEAN"
        broker_positions = int(broker.get("broker_position_count") or len(broker.get("broker_positions") or []) or 0)
        broker_orders = int(broker.get("broker_order_count") or len(broker.get("broker_orders") or []) or 0)
        if self.config.require_broker_reconciliation_clean and not broker_clean:
            block("broker_reconciliation_not_clean", "broker reconciliation is not CLEAN")
        if broker_positions > self.config.max_broker_positions or broker_orders > self.config.max_broker_orders:
            block("broker_exposure_present", "broker position/order count exceeds decision limits")

        spread = _as_float(tick.get("spread_points"))
        if spread is not None and spread > self.config.max_spread_points:
            block("spread_above_max", f"spread {spread} exceeds max {self.config.max_spread_points}")
        elif spread is None:
            warnings.append("spread unavailable")

        session = _as_dict(runtime.get("session"))
        context = _as_dict(runtime.get("context"))
        session_allowed = session.get("session_allowed")
        if session_allowed is False or context.get("session_allowed") is False:
            block("session_not_allowed", "runtime state reports session not allowed")

        selected, low_conf = self._select_signal(data.strategy_agent_latest)
        if not selected and not low_conf:
            block("no_actionable_signal", "no prioritized actionable strategy signal is available")
        if not selected and low_conf:
            block("signal_confidence_below_threshold", "latest actionable signal confidence is below threshold")

        if risk and risk.get("can_trade") is False:
            block("risk_governor_block", "risk governor status reports can_trade=false")

        confidence = float(selected.get("confidence") or 0.0) if selected else 0.0
        session_ok = not any(item.code == "session_not_allowed" for item in blocks)
        system_ok = not safety_violation and source.event_bus_available and source.strategy_agent_available
        score = calculate_score(confidence=confidence, spread_points=spread, broker_clean=broker_clean, session_ok=session_ok, system_ok=system_ok, config=self.config)

        action = AurixDecisionAction.WAIT
        status = AurixDecisionStatus.WAITING
        if safety_violation or any(item.code in {"event_bus_state_missing", "strategy_agent_state_missing"} for item in blocks):
            action = AurixDecisionAction.SYSTEM_NOT_READY
            status = AurixDecisionStatus.BLOCKED
        elif any(item.code.startswith("broker_") for item in blocks):
            action = AurixDecisionAction.BLOCKED_BY_BROKER_STATE
            status = AurixDecisionStatus.BLOCKED
        elif any(item.code == "spread_above_max" for item in blocks):
            action = AurixDecisionAction.BLOCKED_BY_SPREAD
            status = AurixDecisionStatus.BLOCKED
        elif any(item.code == "session_not_allowed" for item in blocks):
            action = AurixDecisionAction.BLOCKED_BY_SESSION
            status = AurixDecisionStatus.BLOCKED
        elif any(item.code == "risk_governor_block" for item in blocks):
            action = AurixDecisionAction.BLOCKED_BY_RISK
            status = AurixDecisionStatus.BLOCKED
        elif any(item.code == "signal_confidence_below_threshold" for item in blocks):
            action = AurixDecisionAction.BLOCKED_BY_LOW_CONFIDENCE
            status = AurixDecisionStatus.BLOCKED
        elif any(item.code == "no_actionable_signal" for item in blocks):
            action = AurixDecisionAction.BLOCKED_BY_NO_SIGNAL
            status = AurixDecisionStatus.BLOCKED
        elif selected:
            action = AurixDecisionAction.TRADE_LONG if selected.get("direction") == "BUY" else AurixDecisionAction.TRADE_SHORT
            action = apply_autonomy(self.config.autonomy_level, action)
            status = AurixDecisionStatus.READY if action in {AurixDecisionAction.TRADE_LONG, AurixDecisionAction.TRADE_SHORT} else AurixDecisionStatus.WAITING

        if not self.config.allow_demo_execution:
            warnings.append("execution disabled: no order request created")
        if not self.config.allow_demo_command_queueing and not self.config.allow_mt5_command_queueing:
            warnings.append("demo command queueing disabled: no MT5 command queued")
        if self.config.autonomy_level == "ADVISORY_ONLY":
            warnings.append("advisory-only mode: monitor/manual action only")

        if self.config.block_when_command_queue_disabled and not self.config.allow_mt5_command_queueing:
            action = AurixDecisionAction.BLOCKED_BY_COMMAND_QUEUE_DISABLED
            status = AurixDecisionStatus.BLOCKED
        if self.config.block_when_execution_disabled and not self.config.allow_demo_execution:
            action = AurixDecisionAction.BLOCKED_BY_EXECUTION_DISABLED
            status = AurixDecisionStatus.BLOCKED

        reasons.append(reason("decision_evaluated", f"decision action {action.value} selected"))
        recs = [AurixDecisionRecommendation(message="No execution is performed by Part 33.")]
        if action in {AurixDecisionAction.TRADE_LONG, AurixDecisionAction.TRADE_SHORT}:
            recs.append(AurixDecisionRecommendation(message="Candidate can be monitored or passed to later dry-run workflows only."))

        return AurixDecisionReport(
            symbol=self.config.symbol,
            mode=self.config.mode,
            autonomy_level=self.config.autonomy_level,
            action=action,
            direction=selected.get("direction") if selected else None,
            status=status,
            confidence=confidence,
            score=score,
            strategy=selected.get("strategy_name") if selected else None,
            strategy_version=selected.get("strategy_version") if selected else None,
            signal_id=selected.get("id") or selected.get("signal_id") if selected else None,
            signal_event_id=selected.get("event_id") if selected else None,
            setup_reason=selected.get("setup_reason") if selected else None,
            decision_reasons=reasons,
            blocking_reasons=blocks,
            warnings=warnings,
            recommendations=recs,
            source_state=source,
            risk_view=risk,
            execution_view={"demo_oms": demo_oms, "demo_command_queue": queue, "order_request_created": False, "mt5_command_queued": False},
            broker_view={"status": broker.get("status"), "positions": broker_positions, "orders": broker_orders},
        )
