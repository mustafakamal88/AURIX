from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_evidence_gate import EvidenceGate, EvidenceGateConfig


def operator_inputs(ok: bool = True, live_disabled: bool = True, open_commands: int = 0) -> tuple[dict, dict]:
    status = {
        "commands": {"open_count": open_commands},
        "safety": {
            "live_trading_enabled": False if live_disabled else True,
            "ea_allow_live_trading_seen": False if live_disabled else True,
        },
    }
    summary = {"ok": ok, "market_quality_ok": ok, "warnings": [] if ok else ["operator warning"]}
    return status, summary


def paper_report(closed: int = 50, expectancy: float = 0.2, profit_factor: float = 1.5, max_losses: int = 3) -> dict:
    return {
        "closed_trades": closed,
        "expectancy_r": expectancy,
        "profit_factor": profit_factor,
        "max_consecutive_losses": max_losses,
        "by_session": {
            "LONDON": {"trades": 10, "expectancy_r": 0.2},
            "NY_OPEN": {"trades": 10, "expectancy_r": 0.3},
            "NY_LATE": {"trades": 10, "expectancy_r": 0.1},
        },
        "warnings": [],
    }


def passing_inputs(**overrides) -> dict:
    operator_status, operator_summary = operator_inputs()
    data = {
        "paper_analytics": paper_report(),
        "backtest_report": {"trades": 50, "expectancy_r": 0.15, "profit_factor": 1.4, "max_consecutive_losses": 3, "warnings": []},
        "research_report": {"total_variants": 10, "warnings": []},
        "market_status": {"candle_count": 1000, "quality": {"ok": True}},
        "operator_status": operator_status,
        "operator_summary": operator_summary,
        "journal_entries": [{"id": "j1"}],
        "ai_review_report": {"id": "a1"},
        "paper_trades": [{"opened_at": f"2026-01-{day:02d}T09:00:00+00:00"} for day in range(1, 11)],
    }
    data.update(overrides)
    return data


def assert_blocked(report, reason: str) -> None:
    if report.live_ready is not False:
        raise AssertionError(f"live_ready must never be true, got {report}")
    if not any(reason in item for item in report.blocking_reasons):
        raise AssertionError(f"expected block containing {reason!r}, got {report.blocking_reasons}")


def main() -> int:
    config = EvidenceGateConfig(allow_live_readiness=False)
    gate = EvidenceGate(config)

    empty = gate.evaluate({})
    assert_blocked(empty, "closed paper trades below minimum")
    if empty.safety.get("commands_queued") is not False or empty.safety.get("no_mt5_execution") is not True:
        raise AssertionError(f"safety flags wrong: {empty.safety}")

    low_sample = gate.evaluate(passing_inputs(paper_analytics=paper_report(closed=5)))
    assert_blocked(low_sample, "closed paper trades below minimum")

    poor_expectancy = gate.evaluate(passing_inputs(paper_analytics=paper_report(expectancy=-0.1)))
    assert_blocked(poor_expectancy, "expectancy below minimum")

    bad_status, bad_summary = operator_inputs(ok=False)
    operator_warning = gate.evaluate(passing_inputs(operator_status=bad_status, operator_summary=bad_summary))
    assert_blocked(operator_warning, "operator summary not ok")

    live_disabled_pass = gate.evaluate(passing_inputs())
    if live_disabled_pass.checks["live_trading_disabled"]["passed"] is not True:
        raise AssertionError(f"live trading disabled check should pass: {live_disabled_pass.checks}")

    if live_disabled_pass.status != "ELIGIBLE_PAPER_ONLY" or live_disabled_pass.live_ready is not False:
        raise AssertionError(f"passing metrics should be paper-only eligible with live_ready false, got {live_disabled_pass}")
    if live_disabled_pass.safety.get("live_readiness_allowed_by_config") is not False:
        raise AssertionError(f"live readiness config safety flag wrong: {live_disabled_pass.safety}")

    print("OK: evidence gate self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
