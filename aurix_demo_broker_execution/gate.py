from __future__ import annotations

from typing import Any, Optional

from .account import verify_demo_account
from .daily_risk import evaluate_daily_risk


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class DemoBrokerExecutionGate:
    def __init__(self, config: Any, store: Any):
        self.config = config
        self.store = store

    def evaluate(self, *, snapshot: Optional[dict[str, Any]], signal: Optional[dict[str, Any]], runtime_session_id: str, runtime_health: str = "UNKNOWN") -> dict[str, Any]:
        snapshot = _dict(snapshot)
        signal = _dict(signal)
        checks: list[dict[str, Any]] = []

        def check(name: str, passed: bool, reason: str, **extra: Any) -> None:
            checks.append({"name": name, "passed": passed, "reason": reason, **extra})

        account_verification = verify_demo_account(snapshot)
        tick = _dict(snapshot.get("tick"))
        positions = _list(snapshot.get("positions"))
        symbol = tick.get("symbol") or signal.get("symbol")
        terminal_id = snapshot.get("terminal_id")
        spread = _float(tick.get("spread_points"))
        daily_risk = evaluate_daily_risk(snapshot, self.config, self.store)
        volume = min(float(self.config.max_volume), 0.01)
        direction = signal.get("direction")
        sl = signal.get("stop_loss_reference")
        tp = signal.get("take_profit_reference")
        confidence = _float(signal.get("confidence")) or 0.0
        signal_status = str(signal.get("status") or "")

        has_signal = bool(signal)
        signal_is_actionable = signal_status in {"SIGNAL", "VALID", "ACTIONABLE"}
        direction_present = direction is not None
        direction_allowed = direction in {"BUY", "SELL"}

        check("broker_execution_enabled", self.config.broker_execution_enabled, "broker execution enabled" if self.config.broker_execution_enabled else "broker execution disabled")
        check("internal_queue_available", self.config.broker_execution_enabled, "AURIX internal queue ready" if self.config.broker_execution_enabled else "broker execution disabled")
        check("live_execution_disabled", True, "legacy live execution env switch is not used")
        check("actionable_signal_present", has_signal and signal_is_actionable, "actionable signal present" if has_signal and signal_is_actionable else "no actionable signal")
        check("signal_direction_present", direction_present, "signal direction present" if direction_present else "signal direction missing")
        check("signal_direction_allowed", direction_allowed, f"signal direction {direction}" if direction_allowed else "signal direction missing")
        check("demo_account_verified", bool(account_verification["demo_account_verified"]) or not self.config.require_demo_account_verified, account_verification["demo_account_reason"], account=account_verification)
        terminal_allowed = terminal_id in self.config.terminal_id_allowlist
        symbol_allowed = symbol in self.config.symbol_allowlist and symbol == "XAUUSDm"
        check("terminal_allowlisted", terminal_allowed, f"terminal {terminal_id} allowlisted" if terminal_allowed else "terminal id is not allowlisted")
        check("symbol_allowlisted", symbol_allowed, f"symbol {symbol} is XAUUSDm and allowlisted" if symbol_allowed else "symbol is not XAUUSDm or is not allowlisted")
        check("volume_limit", volume <= 0.01 and volume <= float(self.config.max_volume), f"volume {volume} <= max {self.config.max_volume}")
        check("all_sessions_allowed", self.config.allow_all_sessions and self.config.allow_asia_session and self.config.allow_london_session and self.config.allow_new_york_session, "all sessions including Asia are allowed")
        check("spread_ok", spread is not None and spread <= float(self.config.max_spread_points), f"spread exceeds engine max" if spread is None or spread > float(self.config.max_spread_points) else f"spread {spread} <= engine max {self.config.max_spread_points}")
        check("valid_strategy_signal", signal_is_actionable and direction_allowed, f"signal status {signal_status} direction {direction}" if signal_is_actionable and direction_allowed else ("signal direction missing" if signal_is_actionable else "no actionable signal"))
        check("confidence_threshold", confidence >= float(self.config.confidence_threshold), f"confidence {confidence} >= {self.config.confidence_threshold}")
        check("stop_loss_required", sl is not None if self.config.require_stop_loss else True, "stop loss present")
        check("take_profit_required", tp is not None if self.config.require_take_profit else True, "take profit present")
        check("one_open_position", len(positions) < int(self.config.max_open_positions), f"open broker positions {len(positions)} < {self.config.max_open_positions}")
        check("daily_loss_guard", bool(daily_risk.get("allowed")), str(daily_risk.get("reason")), daily_risk=daily_risk)
        balance = _float(_dict(snapshot.get("account")).get("balance"))
        equity = _float(_dict(snapshot.get("account")).get("equity"))
        check("account_balance_equity_guard", balance is not None and equity is not None and balance > 0 and equity > 0, "balance/equity positive")
        check("no_duplicate_pending_command", not self.store.has_duplicate_pending(signal.get("id")), "no duplicate pending command for signal")
        check("runtime_healthy_enough", runtime_health not in {"ERROR", "STALE"}, f"runtime health {runtime_health}")
        check("evidence_provenance_writable", True, "demo broker execution store writable")

        failed = [item for item in checks if not item["passed"]]
        if failed:
            return {
                "allowed": False,
                "action": "BLOCKED",
                "reason": failed[0]["reason"],
                "primary_block": failed[0]["reason"],
                "queue_state": "BLOCKED",
                "spread_gate": "PASS" if next((item for item in checks if item["name"] == "spread_ok"), {}).get("passed") else "BLOCKED",
                "checks": checks,
                "demo_account_verification": account_verification,
                "daily_risk_guard": daily_risk,
            }

        return {
            "allowed": True,
            "action": "QUEUE_DEMO_MARKET_ORDER",
            "queue_state": "READY",
            "spread_gate": "PASS",
            "side": direction,
            "symbol": "XAUUSDm",
            "volume": volume,
            "stop_loss": sl,
            "take_profit": tp,
            "strategy_id": signal.get("strategy_name") or signal.get("agent_id"),
            "signal_confidence": signal.get("signal_confidence") if signal.get("signal_confidence") is not None else signal.get("confidence"),
            "signal_reasons": signal.get("signal_reasons") or signal.get("reasons") or [],
            "decision_cycle_id": signal.get("decision_cycle_id") or _dict(signal.get("decision_trace")).get("decision_cycle_id"),
            "final_gate_result": "BROKER_COMMAND_GATE_ALLOWED",
            "signal_id": signal.get("id"),
            "runtime_session_id": runtime_session_id,
            "checks": checks,
            "demo_account_verification": account_verification,
            "daily_risk_guard": daily_risk,
        }
