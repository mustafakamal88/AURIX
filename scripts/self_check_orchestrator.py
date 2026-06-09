from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_orchestrator import OrchestratorConfig, SessionOrchestrator


def build_orchestrator(tmpdir: str, session: str, calls: dict[str, int]) -> SessionOrchestrator:
    def context() -> dict:
        calls["context"] += 1
        return {
            "session_name": session,
            "data_quality_ok": True,
            "spread_ok": True,
        }

    def daemon_run() -> dict:
        calls["daemon_run"] += 1
        return {"running": False, "loop_count": calls["daemon_run"], "errors": []}

    def daemon_stop() -> dict:
        calls["daemon_stop"] += 1
        return {"running": False, "loop_count": calls["daemon_run"], "errors": []}

    def forward() -> dict:
        calls["forward"] += 1
        return {"status": "ACTIVE", "progress": {"percent": 10.0}}

    def evidence() -> dict:
        calls["evidence"] += 1
        return {"status": "BLOCKED", "live_ready": False}

    def operator() -> dict:
        calls["operator"] += 1
        return {"ok": True}

    def command_count() -> int:
        return calls["commands"]

    return SessionOrchestrator(
        tmpdir,
        OrchestratorConfig(
            interval_seconds=0.1,
            update_forward_test_every_loops=1,
            evaluate_evidence_every_loops=1,
            generate_analytics_every_loops=100,
            generate_journal_every_loops=100,
            generate_ai_review_every_loops=100,
            autostart_on_server_boot=False,
        ),
        evaluate_context=context,
        daemon_run_once=daemon_run,
        daemon_stop=daemon_stop,
        daemon_status=daemon_stop,
        update_forward_test=forward,
        evaluate_evidence=evidence,
        operator_summary=operator,
        command_count=command_count,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        calls = {"context": 0, "daemon_run": 0, "daemon_stop": 0, "forward": 0, "evidence": 0, "operator": 0, "commands": 0}
        closed = build_orchestrator(tmpdir, "CLOSED", calls)
        status = closed.run_once()
        if status.current_session != "CLOSED" or status.session_allowed:
            raise AssertionError(f"closed session classification wrong: {status}")
        if calls["daemon_stop"] != 1 or calls["daemon_run"] != 0:
            raise AssertionError(f"closed session should stop daemon only: calls={calls}")
        if calls["forward"] != 1:
            raise AssertionError(f"forward-test update should be called: calls={calls}")
        if status.safety.get("live_execution_allowed") is not False or status.safety.get("command_queueing_allowed") is not False:
            raise AssertionError(f"safety flags wrong: {status.safety}")
        if status.safety.get("autostart_on_server_boot") is not False:
            raise AssertionError(f"autostart safety flag wrong: {status.safety}")
        if Path(tmpdir, "orchestrator_status.json").exists() is not True:
            raise AssertionError("orchestrator status file was not saved")

        calls = {"context": 0, "daemon_run": 0, "daemon_stop": 0, "forward": 0, "evidence": 0, "operator": 0, "commands": 0}
        allowed = build_orchestrator(tmpdir, "LONDON", calls)
        status = allowed.run_once()
        if not status.session_allowed or calls["daemon_run"] != 1:
            raise AssertionError(f"allowed session should run paper daemon path: status={status} calls={calls}")
        if calls["forward"] != 1:
            raise AssertionError(f"allowed session should update forward test: calls={calls}")
        if status.errors:
            raise AssertionError(f"allowed run should not error: {status}")

        started = allowed.mark_started()
        duplicate = allowed.mark_started()
        if not duplicate.running or started.started_at != duplicate.started_at:
            raise AssertionError(f"duplicate start not idempotent: first={started} second={duplicate}")
        stopped = allowed.mark_stopped()
        if stopped.running:
            raise AssertionError(f"stop should be safe: {stopped}")

        saved = json.loads(Path(tmpdir, "orchestrator_status.json").read_text(encoding="utf-8"))
        if saved.get("safety", {}).get("mt5_commands_queued") is not False:
            raise AssertionError(f"saved safety wrong: {saved}")

    print("OK: orchestrator self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
