from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aurix_live_readiness import LiveReadinessConfig, LiveReadinessEvaluator, LiveReadinessStore


def sample_inputs(open_commands: int = 0, ea_live: bool = False) -> dict:
    return {
        "evidence_gate_report": {"status": "ELIGIBLE_PAPER_ONLY", "blocking_reasons": []},
        "forward_test_status": {"campaign": {"status": "COMPLETED", "closed_paper_trades": 50, "recorded_candles": 1000, "days_observed": 10}},
        "long_forward_test_status": {"running": False, "recorded_candles": 1000, "days_observed": 10},
        "operator_status": {
            "paper": {"open_trades": 0, "closed_trades": 50},
            "commands": {"open_count": open_commands, "open": [{}] * open_commands},
            "safety": {"ea_allow_live_trading_seen": ea_live},
            "journal": {"entries_count": 1},
        },
        "operator_summary": {"ok": True, "market_quality_ok": True, "paper_closed_trades": 50, "paper_open_count": 0},
        "market_quality": {"ok": True},
        "paper_analytics": {"closed_trades": 50},
        "backtest_report": {"trades": 50},
        "research_sweep": {"total_variants": 1},
        "journal_status": {"entries_count": 1},
        "ai_review_report": {"summary": "local review"},
        "latest_snapshot": {"ea": {"AllowLiveTrading": ea_live}},
        "recorded_candles": 1000,
        "forward_days": 10,
        "open_command_count": open_commands,
    }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    config = LiveReadinessConfig()
    evaluator = LiveReadinessEvaluator(config)

    low = evaluator.evaluate({})
    require(low.status == "BLOCKED", f"empty evidence should block, got {low.status}")
    require(low.live_arming_allowed is False, "allow_live_arming=false must prevent arming")
    require(low.live_execution_allowed is False, "allow_live_execution=false must prevent execution")

    ready = evaluator.evaluate(sample_inputs())
    require(ready.status == "READY_FOR_MANUAL_REVIEW", f"complete evidence should reach manual review only, got {ready.status}")
    require(ready.live_arming_allowed is False, "manual review report must not allow arming")
    require(ready.live_execution_allowed is False, "manual review report must not allow execution")
    require(ready.safety.get("mt5_commands_queued") is False, "safety must report no command queueing")
    require(ready.safety.get("ea_settings_modified") is False, "safety must report no EA settings modified")
    require(ready.safety.get("external_llm_used") is False, "safety must report no external LLM")
    require(ready.safety.get("strategy_config_mutated") is False, "safety must report no strategy config mutation")

    open_commands = evaluator.evaluate(sample_inputs(open_commands=1))
    require("open commands present" in open_commands.blocking_reasons, "open commands check did not block")

    ea_live = evaluator.evaluate(sample_inputs(ea_live=True))
    require("EA live trading is not confirmed disabled" in ea_live.blocking_reasons, "EA live disabled check did not block")

    with TemporaryDirectory() as tmp:
        store = LiveReadinessStore(tmp, config)
        checklist = store.manual_checklist()
        require(len(checklist.get("items") or []) >= 10, "manual checklist missing items")
        report = store.evaluate(sample_inputs())
        require((Path(tmp) / "live_readiness_report.json").exists(), "report file was not saved")
        require(report.safety.get("mt5_commands_queued") is False, "store evaluation queued commands")

    files = [
        *Path("aurix_live_readiness").glob("*.py"),
        Path("scripts/check_live_readiness.py"),
        Path("scripts/evaluate_live_readiness.py"),
        Path("scripts/show_live_readiness_checklist.py"),
        Path("scripts/watch_live_readiness.py"),
    ]
    for file in files:
        text = (ROOT / file).read_text(encoding="utf-8")
        require("commands/open-market" not in text, f"forbidden endpoint reference in {file}")

    print("OK: live readiness self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
