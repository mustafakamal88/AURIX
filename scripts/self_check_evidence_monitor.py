from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aurix_evidence_monitor import EvidenceGrowthMonitor, EvidenceMonitorConfig, EvidenceMonitorStore


def inputs(
    *,
    closed: int = 0,
    candles: int = 0,
    days: int = 0,
    evidence_status: str = "BLOCKED",
    open_commands: int = 0,
    open_paper: int = 0,
    market_ok: bool = True,
    operator_ok: bool = True,
    unsafe_readiness: bool = False,
) -> dict:
    live_readiness = {
        "status": "BLOCKED",
        "live_arming_allowed": False,
        "live_execution_allowed": False,
        "safety": {
            "live_arming_allowed": False,
            "live_execution_allowed": False,
            "mt5_commands_queued": False,
            "ea_settings_modified": False,
            "strategy_config_mutated": False,
        },
    }
    if unsafe_readiness:
        live_readiness["live_execution_allowed"] = True
        live_readiness["safety"]["live_execution_allowed"] = True
    return {
        "live_readiness_report": live_readiness,
        "evidence_gate_report": {"status": evidence_status},
        "forward_test_status": {"campaign": {"status": "COMPLETED", "closed_paper_trades": closed, "recorded_candles": candles, "days_observed": days}},
        "long_forward_test_status": {"running": False, "recorded_candles": candles, "days_observed": days},
        "paper_analytics": {"closed_trades": closed},
        "paper_status": {"closed_trades": closed, "open_trades": open_paper},
        "market_recorder_status": {"candle_count": candles},
        "operator_status": {"commands": {"open_count": open_commands, "open": [{}] * open_commands}, "journal": {"entries_count": 1}},
        "operator_summary": {"ok": operator_ok, "market_quality_ok": market_ok, "paper_closed_trades": closed, "paper_open_count": open_paper},
        "market_quality": {"ok": market_ok},
        "journal_status": {"entries_count": 1},
        "recorded_candles": candles,
        "forward_days": days,
        "open_command_count": open_commands,
    }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    config = EvidenceMonitorConfig()
    monitor = EvidenceGrowthMonitor(config)

    empty = monitor.evaluate({})
    require(empty.status in {"NO_DATA", "COLLECTING"}, f"empty evidence should not be ready, got {empty.status}")
    require(empty.status != "READY_FOR_READINESS_REVIEW", "empty evidence returned ready")

    low = monitor.evaluate(inputs(closed=5, candles=100, days=1, evidence_status="BLOCKED"))
    require(low.status in {"COLLECTING", "IMPROVING"}, f"low evidence should collect/improve, got {low.status}")
    require(low.status != "READY_FOR_READINESS_REVIEW", "low evidence returned ready")

    ready = monitor.evaluate(inputs(closed=50, candles=1000, days=10, evidence_status="ELIGIBLE_PAPER_ONLY"))
    require(ready.status == "READY_FOR_READINESS_REVIEW", f"complete evidence did not reach review, got {ready.status}")

    open_commands = monitor.evaluate(inputs(closed=50, candles=1000, days=10, evidence_status="ELIGIBLE_PAPER_ONLY", open_commands=1))
    require(open_commands.status == "BLOCKED", "open commands must force BLOCKED")
    require("open commands present" in open_commands.blocking_reasons, "open command blocking reason missing")

    unsafe = monitor.evaluate(inputs(closed=50, candles=1000, days=10, evidence_status="ELIGIBLE_PAPER_ONLY", unsafe_readiness=True))
    require(unsafe.status == "BLOCKED", "unsafe live readiness flags must force BLOCKED")
    require("live readiness safety flags are unsafe" in unsafe.blocking_reasons, "unsafe readiness blocking reason missing")

    require(config.allow_live_arming is False, "allow_live_arming=false must remain enforced")
    require(config.allow_live_execution is False, "allow_live_execution=false must remain enforced")
    require(ready.safety.get("monitor_only") is True, "monitor_only safety flag wrong")
    require(ready.safety.get("live_arming_allowed") is False, "live arming safety flag wrong")
    require(ready.safety.get("live_execution_allowed") is False, "live execution safety flag wrong")
    require(ready.safety.get("mt5_commands_queued") is False, "command queueing safety flag wrong")
    require(ready.safety.get("readiness_config_modified") is False, "readiness config safety flag wrong")

    with TemporaryDirectory() as tmp:
        store = EvidenceMonitorStore(tmp, config)
        report = store.evaluate(inputs(closed=50, candles=1000, days=10, evidence_status="ELIGIBLE_PAPER_ONLY"))
        require(report.status == "READY_FOR_READINESS_REVIEW", "store evaluation failed")
        require((Path(tmp) / "evidence_growth_report.json").exists(), "latest report missing")
        require(len(store.history()) == 1, "history append failed")
        store.evaluate(inputs(closed=50, candles=1000, days=10, evidence_status="ELIGIBLE_PAPER_ONLY"))
        require(len(store.history()) == 2, "second history append failed")
        store.reset()
        require(store.latest() is None, "reset did not clear latest")
        require(store.history() == [], "reset did not clear history")

    files = [*Path("aurix_evidence_monitor").glob("*.py")]
    for file in files:
        text = (ROOT / file).read_text(encoding="utf-8")
        require("commands/open-market" not in text, f"forbidden endpoint reference in {file}")
        require("add_command" not in text, f"command queueing reference in {file}")

    print("OK: evidence monitor self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
