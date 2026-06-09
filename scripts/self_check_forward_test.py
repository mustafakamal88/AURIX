from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_forward_test import ForwardTestConfig, ForwardTestStore


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def trade(day: int, status: str = "CLOSED_TP") -> dict:
    return {"id": f"t-{day}", "status": status, "opened_at": f"2026-01-{day:02d}T09:00:00+00:00"}


def context(day: int, session: str) -> dict:
    return {"id": f"c-{day}-{session}", "session_name": session, "created_at": f"2026-01-{day:02d}T09:00:00+00:00"}


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        config = ForwardTestConfig(target_days=2, target_closed_paper_trades=2, target_recorded_candles=3, minimum_sessions_covered=2)
        store = ForwardTestStore(root, config)

        started = store.start()
        if started.status != "ACTIVE":
            raise AssertionError(f"campaign start failed: {started}")
        if Path(root, "daemon_status.json").exists():
            raise AssertionError("campaign start should not start daemon or create daemon status")

        empty = store.update({"operator_summary": {"ok": False, "warnings": ["snapshot missing"]}})
        if empty.status != "ACTIVE" or not empty.blocking_reasons:
            raise AssertionError(f"empty data should block progress without crashing: {empty}")
        if empty.safety.get("paper_only") is not True or empty.safety.get("commands_queued") is not False:
            raise AssertionError(f"safety flags wrong: {empty.safety}")

        partial = store.update(
            {
                "paper_trades": [trade(1)],
                "contexts": [context(1, "LONDON")],
                "candles": [{}, {}],
                "daemon_status": {"loop_count": 1},
                "operator_summary": {"ok": True},
                "evidence_report": {"status": "BLOCKED"},
            }
        )
        if partial.progress.get("percent", 0) <= 0:
            raise AssertionError(f"progress should increase with partial data: {partial}")
        if partial.status == "COMPLETED":
            raise AssertionError(f"partial data must not complete campaign: {partial}")

        complete = store.update(
            {
                "paper_trades": [trade(1), trade(2)],
                "contexts": [context(1, "LONDON"), context(2, "NY_OPEN")],
                "candles": [{}, {}, {}],
                "daemon_status": {"loop_count": 2},
                "operator_summary": {"ok": True},
                "evidence_report": {"status": "ELIGIBLE_PAPER_ONLY"},
            }
        )
        if complete.status != "COMPLETED" or complete.progress.get("percent") != 100.0:
            raise AssertionError(f"complete targets should complete campaign: {complete}")
        if complete.safety.get("live_trading_allowed") is not False or complete.safety.get("no_mt5_execution") is not True:
            raise AssertionError(f"complete safety flags wrong: {complete.safety}")
        if (root / "commands.json").exists() and json.loads((root / "commands.json").read_text(encoding="utf-8")):
            raise AssertionError("forward test queued commands")

    print("OK: forward test self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
