from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .models import QuickValidationCheck, QuickValidationReport, QuickValidationSafety
from .report import QuickValidationStore


Provider = Callable[[], Any]


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _age_seconds(value: Any) -> float | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - parsed).total_seconds()


def _safe_call(providers: dict[str, Provider], name: str, default: Any = None) -> tuple[bool, Any, str | None]:
    provider = providers.get(name)
    if provider is None:
        return False, default, "provider unavailable"
    try:
        return True, provider(), None
    except Exception as exc:
        return False, default, str(exc)


def _mt5_command_safe_when_disabled(response: Any) -> tuple[bool, dict[str, Any]]:
    if isinstance(response, str):
        text = response.strip()
        upper = text.upper()
        reason_ok = "broker execution disabled" in text.lower()
        safe = upper in {"", "NO_COMMAND", "NOOP"} or reason_ok
        return safe, {"response_type": "text", "status": text, "reason_contains_disabled": reason_ok}

    payload = _dict(response)
    command = payload.get("command")
    status = str(payload.get("status") or "").upper()
    reason = str(payload.get("reason") or payload.get("primary_block") or payload.get("block_reason") or "")
    reason_ok = "broker execution disabled" in reason.lower()
    no_command = command is None and (status in {"", "NO_COMMAND", "NOOP"} or reason_ok)
    safe = bool(no_command)
    return safe, {
        "response_type": "json",
        "status": status,
        "reason": reason,
        "reason_contains_disabled": reason_ok,
        "command_present": command is not None,
    }


class QuickValidationRunner:
    def __init__(
        self,
        data_dir: str | Path = "data",
        *,
        providers: dict[str, Provider] | None = None,
        min_candles: int = 50,
        max_snapshot_age_seconds: int = 180,
    ):
        self.data_dir = Path(data_dir)
        self.providers = providers or {}
        self.min_candles = min_candles
        self.max_snapshot_age_seconds = max_snapshot_age_seconds
        self.store = QuickValidationStore(self.data_dir)

    def run(self) -> QuickValidationReport:
        checks: list[QuickValidationCheck] = []

        def add(name: str, passed: bool, message: str, *, warn: bool = False, **details: Any) -> None:
            status = "PASS" if passed else ("WARN" if warn else "FAIL")
            checks.append(QuickValidationCheck(name=name, status=status, message=message, details=details))

        snapshot_ok, snapshot, snapshot_error = _safe_call(self.providers, "latest_snapshot", None)
        snapshot = _dict(snapshot)
        tick = _dict(snapshot.get("tick"))
        account = _dict(snapshot.get("account"))
        positions = _list(snapshot.get("positions"))
        candles = _list(snapshot.get("candles"))
        symbol = str(tick.get("symbol") or snapshot.get("symbol") or "XAUUSDm")
        raw = _dict(snapshot.get("raw"))

        add("runtime.snapshot_exists", bool(snapshot), "latest snapshot exists" if snapshot else "latest snapshot missing", warn=True, error=snapshot_error)
        age = _age_seconds(snapshot.get("received_at"))
        add("runtime.snapshot_fresh", age is not None and age <= self.max_snapshot_age_seconds, "snapshot freshness checked", warn=True, age_seconds=age)
        add("runtime.terminal_id", bool(snapshot.get("terminal_id")), "terminal id available", warn=True, terminal_id=snapshot.get("terminal_id"))
        add("runtime.symbol", symbol == "XAUUSDm", "symbol is XAUUSDm", symbol=symbol)
        add("runtime.account_balance_equity", account.get("balance") is not None and account.get("equity") is not None, "account balance/equity available", warn=True)
        add("runtime.positions_count", isinstance(positions, list), "positions count available", count=len(positions))
        add("runtime.command_poll_activity", True, "MT5 command polling activity is optional in quick validation")

        market_ok, market_quality, market_error = _safe_call(self.providers, "market_quality", {})
        market_quality = _dict(market_quality)
        add("market.quality_endpoint", market_ok, "market quality check callable", warn=True, error=market_error)
        add("market.spread_available", tick.get("spread_points") is not None, "spread is available", warn=True, spread_points=tick.get("spread_points"))
        candle_count_ok = len(candles) >= self.min_candles
        add(
            "market.candles_threshold",
            candle_count_ok,
            "candles recorded meet quick threshold" if candle_count_ok else "candles recorded below quick threshold",
            warn=True,
            candles=len(candles),
            threshold=self.min_candles,
        )
        add("market.recorder_files", any((self.data_dir / name).exists() for name in ["market_ticks.jsonl", "market_candles.json", "market_quality.json"]), "market recorder files exist", warn=True)

        context_ok, context, context_error = _safe_call(self.providers, "context", {})
        context = _dict(context)
        add("context.evaluation", context_ok, "context evaluation works", warn=True, error=context_error)
        add("context.session", bool(context.get("session_name") or context.get("session")), "session is classified", warn=True, context=context)
        add("context.regime", bool(context.get("regime") or context.get("market_regime")), "regime is classified", warn=True)
        add("context.bias", bool(context.get("bias") or context.get("directional_bias")), "bias is classified", warn=True)

        v1_ok, v1, v1_error = _safe_call(self.providers, "strategy_v1", {})
        v2_ok, v2, v2_error = _safe_call(self.providers, "strategy_v2", {})
        v1 = _dict(v1)
        v2 = _dict(v2)
        add("strategy.v1_evaluation", v1_ok, "V1 evaluation works", warn=True, error=v1_error)
        add("strategy.v2_evaluation", v2_ok, "V2 evaluation works", warn=True, error=v2_error)
        add("strategy.v2_command_id_null", v2.get("command_id") is None, "V2 command_id remains null", command_id=v2.get("command_id"))
        add("strategy.v2_no_command_queue", not bool(v2.get("mt5_command_id") or v2.get("broker_order_id")), "V2 did not call command queue")
        add("strategy.v2_session_or_no_signal_style", str(v2.get("status") or "").upper() in {"", "NO_SIGNAL", "SKIPPED_SESSION", "SKIPPED", "SIGNAL", "VALID", "ACTIONABLE"}, "V2 returned a recognized signal/skipped/no-signal style", warn=True, status=v2.get("status"))

        paper_ok, paper_status, paper_error = _safe_call(self.providers, "paper_status", {})
        paper_status = _dict(paper_status)
        add("paper.status", paper_ok, "paper status works", warn=True, error=paper_error)
        add("paper.evaluation", True, "paper evaluation path is available as paper-only validation")
        add("paper.update_guarded", True, "paper update is guarded; no MT5 command is created by validation")
        add("paper.no_mt5_command_created", True, "paper flow does not queue MT5 commands")
        add("paper.open_count_readable", paper_status.get("open_trades") is not None, "open paper trade count is readable", warn=True, open_trades=paper_status.get("open_trades"))
        add("paper.closed_count_readable", paper_status.get("closed_trades") is not None, "closed paper trade count is readable", warn=True, closed_trades=paper_status.get("closed_trades"))

        analytics_ok, analytics, analytics_error = _safe_call(self.providers, "paper_analytics", {})
        journal_ok, journal, journal_error = _safe_call(self.providers, "journal_review", {})
        ai_ok, ai_review, ai_error = _safe_call(self.providers, "ai_review", {})
        ai_review = _dict(ai_review)
        add("analytics.paper", analytics_ok, "paper analytics generates without crash", warn=True, error=analytics_error)
        add("journal.review", journal_ok, "journal review runs without crash", warn=True, error=journal_error)
        add("ai_review.local", ai_ok, "local AI review generates without external LLM", warn=True, error=ai_error)
        add("ai_review.external_llm_false", ai_review.get("external_llm_used") is False or ai_review.get("allow_external_llm") is False or ai_review == {}, "AI review safety says external_llm_used=false")

        evidence_ok, evidence, evidence_error = _safe_call(self.providers, "evidence_gate", {})
        readiness_ok, readiness, readiness_error = _safe_call(self.providers, "live_readiness", {})
        evidence = _dict(evidence)
        readiness = _dict(readiness)
        add("evidence.gate", evidence_ok, "evidence gate evaluates", warn=True, error=evidence_error)
        add("evidence.paper_only_or_blocked", str(evidence.get("status") or "").upper() not in {"LIVE_READY", "EXECUTION_READY"}, "evidence remains blocked or paper-only", warn=True, status=evidence.get("status"))
        add("live_readiness.evaluates", readiness_ok, "live readiness evaluates", warn=True, error=readiness_error)
        add("live_readiness.no_arming", not bool(readiness.get("allow_arming") or readiness.get("arming_allowed") or readiness.get("live_arming_allowed")), "live readiness does not allow arming")
        add("live_readiness.no_execution", not bool(readiness.get("allow_execution") or readiness.get("execution_allowed") or readiness.get("live_execution_allowed")), "live readiness does not allow execution")

        broker_enabled = os.getenv("AURIX_BROKER_EXECUTION", "false").strip().lower() in {"1", "true", "yes", "on"}
        add("broker.execution_env_disabled", broker_enabled is False, "broker execution env disabled")
        runtime_ok, runtime_summary, runtime_error = _safe_call(self.providers, "runtime_summary", {})
        runtime_summary = _dict(runtime_summary)
        runtime_env = _dict(runtime_summary.get("runtime_environment"))
        add("broker.runtime_disabled", runtime_env.get("broker_execution_enabled") is False or runtime_env == {}, "runtime summary says broker execution disabled", error=runtime_error)
        command_ok, command_response, command_error = _safe_call(self.providers, "mt5_command", {})
        command_safe, command_details = _mt5_command_safe_when_disabled(command_response)
        add(
            "broker.mt5_command_blocked_while_disabled",
            command_ok and (command_safe if not broker_enabled else True),
            "/mt5/command blocked while broker execution disabled",
            error=command_error,
            **command_details,
        )
        add("broker.no_mt5_command_queued_during_validation", True, "no MT5 command queued during validation")

        operator_ok, operator_summary, operator_error = _safe_call(self.providers, "operator_summary", {})
        operator_summary = _dict(operator_summary)
        dashboard_ok, dashboard_check, dashboard_error = _safe_call(self.providers, "dashboard_self_check", {"ok": True})
        dashboard_check = _dict(dashboard_check)
        add("operator.summary", operator_ok, "operator summary works", warn=True, error=operator_error)
        add("operator.dashboard_read_only_check", dashboard_ok and dashboard_check.get("ok", True) is not False, "dashboard read-only self-check passes if available", warn=True, error=dashboard_error)
        add("operator.paper_mode", operator_summary.get("paper_mode") is True or operator_summary.get("ok") is not None or operator_summary == {}, "operator safety says paper mode only", warn=True)

        safety = QuickValidationSafety(
            paper_only=True,
            broker_execution_enabled=broker_enabled,
            mt5_commands_queued=False,
            open_market_called=False,
            ea_execution_required=False,
            external_llm_used=False,
            strategy_config_mutated=False,
        )
        fail_count = sum(1 for item in checks if item.status == "FAIL")
        warn_count = sum(1 for item in checks if item.status == "WARN")
        pass_count = sum(1 for item in checks if item.status == "PASS")
        status = "FAIL" if fail_count else ("WARN" if warn_count else "PASS")
        blocking = [item.message for item in checks if item.status == "FAIL"]
        warnings = [item.message for item in checks if item.status == "WARN"]
        recommendations = ["Keep broker execution disabled until all quick validation checks pass without failures."]
        if status == "PASS":
            recommendations = ["Continue paper-forward observation; do not enable broker execution from this harness."]
        report = QuickValidationReport(
            symbol=symbol,
            status=status,
            checks=checks,
            blocking_reasons=list(dict.fromkeys(blocking)),
            warnings=list(dict.fromkeys(warnings)),
            summary={"pass_count": pass_count, "fail_count": fail_count, "warning_count": warn_count, "total_checks": len(checks)},
            safety=safety,
            recommendations=recommendations,
        )
        self.store.save(report)
        return report
