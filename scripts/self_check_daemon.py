from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_daemon import DaemonConfig, PaperDaemonRunner


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        calls = {"supervisor": 0, "analytics": 0, "journal": 0, "ai": 0, "evidence": 0, "commands": 0}

        def supervisor() -> dict:
            calls["supervisor"] += 1
            return {
                "last_snapshot_updated_at": "2026-01-01T00:00:00+00:00",
                "market_quality_ok": True,
                "context_id": "ctx-1",
                "strategy_signal_id": "sig-1",
                "paper_created": False,
                "paper_open_count": 0,
                "errors": [],
            }

        def analytics() -> dict:
            calls["analytics"] += 1
            return {"generated_at": "2026-01-01T00:01:00+00:00"}

        def journal() -> dict:
            calls["journal"] += 1
            return {"updated_at": "2026-01-01T00:01:00+00:00"}

        def ai_review() -> dict:
            calls["ai"] += 1
            return {"id": "ai-1"}

        def evidence() -> dict:
            calls["evidence"] += 1
            return {"status": "BLOCKED"}

        def command_count() -> int:
            return calls["commands"]

        runner = PaperDaemonRunner(
            tmpdir,
            DaemonConfig(
                interval_seconds=0.1,
                run_analytics_every_loops=1,
                run_journal_every_loops=1,
                run_ai_review_every_loops=1,
                run_evidence_every_loops=1,
                allow_command_queueing=False,
                allow_live_execution=False,
                allow_external_llm=False,
            ),
            supervisor_run_once=supervisor,
            generate_analytics=analytics,
            update_journal=journal,
            generate_ai_review=ai_review,
            evaluate_evidence=evidence,
            command_count=command_count,
        )

        status = runner.run_once()
        if status.loop_count != 1 or status.last_signal_id != "sig-1":
            raise AssertionError(f"run-once status wrong: {status}")
        if not Path(tmpdir, "daemon_status.json").exists():
            raise AssertionError("daemon status file was not saved")
        saved = json.loads(Path(tmpdir, "daemon_status.json").read_text(encoding="utf-8"))
        if saved.get("loop_count") != 1:
            raise AssertionError(f"saved status mismatch: {saved}")
        if runner.status().safety.get("live_execution_allowed") is not False:
            raise AssertionError(f"live execution safety flag wrong: {runner.status().safety}")
        if runner.status().safety.get("command_queueing_allowed") is not False:
            raise AssertionError(f"command queueing safety flag wrong: {runner.status().safety}")
        if runner.status().safety.get("external_llm_allowed") is not False:
            raise AssertionError(f"external LLM safety flag wrong: {runner.status().safety}")
        if calls["commands"] != 0:
            raise AssertionError("daemon touched command queue")

        started = runner.mark_started()
        duplicate = runner.mark_started()
        if not started.running or not duplicate.running or started.started_at != duplicate.started_at:
            raise AssertionError(f"duplicate start not idempotent: first={started} second={duplicate}")
        stopped = runner.mark_stopped()
        if stopped.running:
            raise AssertionError(f"stop should mark daemon stopped: {stopped}")
        stopped_again = runner.mark_stopped()
        if stopped_again.running:
            raise AssertionError(f"duplicate stop should stay stopped: {stopped_again}")

    print("OK: daemon self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
