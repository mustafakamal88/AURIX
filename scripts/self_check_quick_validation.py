#!/usr/bin/env python3
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aurix_quick_validation import QuickValidationRunner


def sample_snapshot(candle_count: int = 60) -> dict[str, Any]:
    return {
        "terminal_id": "AURIX-VPS-001",
        "received_at": datetime.now(timezone.utc).isoformat(),
        "account": {"balance": 10000.0, "equity": 10000.0, "currency": "GBP"},
        "tick": {"symbol": "XAUUSDm", "bid": 2300.0, "ask": 2300.2, "spread_points": 20},
        "candles": [{"time": i, "open": 1, "high": 2, "low": 1, "close": 1.5} for i in range(candle_count)],
        "positions": [],
        "orders": [],
        "raw": {"broker_execution_enabled": False},
    }


def providers(snapshot: dict[str, Any] | None, command_log: list[str], mt5_response: Any | None = None) -> dict[str, Any]:
    mt5_response = mt5_response if mt5_response is not None else {"ok": True, "command": None, "status": "NO_COMMAND", "reason": "broker execution disabled"}
    return {
        "latest_snapshot": lambda: snapshot,
        "market_quality": lambda: {"ok": True, "reasons": []},
        "context": lambda: {"session_name": "LONDON", "regime": "RANGE", "bias": "NEUTRAL"},
        "strategy_v1": lambda: {"status": "NO_SIGNAL", "command_id": None},
        "strategy_v2": lambda: {"status": "NO_SIGNAL", "command_id": None, "mt5_command_id": None, "broker_order_id": None},
        "paper_status": lambda: {"open_trades": 0, "closed_trades": 0},
        "paper_analytics": lambda: {"ok": True, "closed_trades": 0},
        "journal_review": lambda: {"ok": True, "entries": []},
        "ai_review": lambda: {"ok": True, "external_llm_used": False},
        "evidence_gate": lambda: {"status": "ELIGIBLE_PAPER_ONLY"},
        "live_readiness": lambda: {"status": "BLOCKED", "allow_arming": False, "allow_execution": False},
        "runtime_summary": lambda: {"runtime_environment": {"broker_execution_enabled": False}},
        "mt5_command": lambda: mt5_response,
        "operator_summary": lambda: {"ok": True, "paper_mode": True},
        "dashboard_self_check": lambda: {"ok": True},
        "open_market": lambda: command_log.append("/commands/open-market"),
    }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    with TemporaryDirectory(prefix="aurix-quick-validation-") as tmpdir:
        command_log: list[str] = []
        missing = QuickValidationRunner(tmpdir, providers=providers(None, command_log)).run()
        require(missing.status in {"WARN", "FAIL"}, f"missing snapshot should be WARN/FAIL, got {missing.status}")
        require(missing.safety.paper_only is True, "missing snapshot report must stay paper-only")

        report = QuickValidationRunner(tmpdir, providers=providers(sample_snapshot(), command_log)).run()
        checks = {check.name: check for check in report.checks}
        require(checks["broker.mt5_command_blocked_while_disabled"].status == "PASS", "broker disabled command state should pass")
        require(checks["market.candles_threshold"].status == "PASS", "candle count >= threshold should pass")

        no_command_report = QuickValidationRunner(
            tmpdir,
            providers=providers(sample_snapshot(), command_log, {"ok": True, "command": None, "status": "NO_COMMAND"}),
        ).run()
        require({check.name: check for check in no_command_report.checks}["broker.mt5_command_blocked_while_disabled"].status == "PASS", "NO_COMMAND response should pass")

        text_noop_report = QuickValidationRunner(tmpdir, providers=providers(sample_snapshot(), command_log, "NOOP")).run()
        require({check.name: check for check in text_noop_report.checks}["broker.mt5_command_blocked_while_disabled"].status == "PASS", "NOOP response should pass")

        executable_report = QuickValidationRunner(
            tmpdir,
            providers=providers(sample_snapshot(), command_log, {"ok": True, "status": "COMMAND_AVAILABLE", "command": {"command_id": "unsafe"}}),
        ).run()
        require({check.name: check for check in executable_report.checks}["broker.mt5_command_blocked_while_disabled"].status == "FAIL", "executable command must fail when broker execution is disabled")

        low_candle_report = QuickValidationRunner(tmpdir, providers=providers(sample_snapshot(10), command_log)).run()
        low_candle_check = {check.name: check for check in low_candle_report.checks}["market.candles_threshold"]
        require(low_candle_check.status == "WARN", "candle count below threshold should warn")
        require(low_candle_check.message == "candles recorded below quick threshold", "low candle warning wording is wrong")

        require(checks["strategy.v2_command_id_null"].status == "PASS", "V2 command_id must remain null")
        require(checks["paper.no_mt5_command_created"].status == "PASS", "paper flow must not queue commands")
        require(checks["live_readiness.no_arming"].status == "PASS", "live readiness arming must remain false")
        require(checks["live_readiness.no_execution"].status == "PASS", "live readiness execution must remain false")
        require(report.safety.paper_only is True, "paper_only safety flag wrong")
        require(report.safety.broker_execution_enabled is False, "broker execution safety flag wrong")
        require(report.safety.mt5_commands_queued is False, "MT5 command safety flag wrong")
        require(report.safety.open_market_called is False, "open market safety flag wrong")
        require(report.safety.external_llm_used is False, "external LLM safety flag wrong")
        require(report.safety.strategy_config_mutated is False, "strategy config safety flag wrong")
        require(command_log == [], f"open-market provider should never be called: {command_log}")
        latest = QuickValidationRunner(tmpdir, providers=providers(sample_snapshot(), command_log)).store.latest()
        require(latest is not None and latest.get("safety", {}).get("paper_only") is True, "latest report was not persisted safely")

    print("OK: quick validation self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
