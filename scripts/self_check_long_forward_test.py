from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aurix_long_run import LongForwardTestConfig, LongForwardTestManager


def main() -> int:
    command_count = 0
    starts = 0
    stops = 0
    orchestrator_running = False

    def operator_summary() -> dict:
        return {"ok": True, "session": "LONDON", "paper_expectancy_r": 0.1, "warnings": []}

    def operator_status() -> dict:
        return {"safety": {"paper_only": True}, "market": {"quality": {"ok": True, "candles_count": 50}}}

    def orchestrator_start() -> dict:
        nonlocal orchestrator_running, starts
        starts += 1
        orchestrator_running = True
        return {"running": True, "loop_count": 0}

    def orchestrator_stop() -> dict:
        nonlocal orchestrator_running, stops
        stops += 1
        orchestrator_running = False
        return {"running": False}

    def orchestrator_run_once() -> dict:
        return {"running": True, "loop_count": 1, "current_session": "LONDON", "session_allowed": True}

    def forward_status() -> dict:
        return {"campaign": {"status": "ACTIVE", "sessions_observed": ["LONDON"], "recorded_candles": 50, "closed_paper_trades": 1, "progress": {"percent": 10}}}

    def update_forward() -> dict:
        return {"status": "ACTIVE", "recorded_candles": 50, "closed_paper_trades": 1, "progress": {"percent": 10}}

    def analytics() -> dict:
        return {"closed_trades": 1, "wins": 1, "losses": 0, "win_rate": 1.0, "total_r": 1.5, "expectancy_r": 1.5}

    def evidence() -> dict:
        return {"status": "BLOCKED", "live_ready": False, "blocking_reasons": ["sample size low"], "warnings": ["low evidence"]}

    with tempfile.TemporaryDirectory(dir="/private/tmp") as tmp:
        config = LongForwardTestConfig()
        manager = LongForwardTestManager(
            tmp,
            config,
            operator_status=operator_status,
            operator_summary=operator_summary,
            orchestrator_status=lambda: {"running": orchestrator_running, "loop_count": 1 if orchestrator_running else 0, "current_session": "LONDON", "session_allowed": orchestrator_running},
            orchestrator_start=orchestrator_start,
            orchestrator_stop=orchestrator_stop,
            orchestrator_run_once=orchestrator_run_once,
            daemon_status=lambda: {"running": False},
            forward_test_status=forward_status,
            update_forward_test=update_forward,
            generate_analytics=analytics,
            analytics_summary=analytics,
            generate_journal=lambda: {"entries": 1},
            journal_status=lambda: {"entries_count": 1},
            generate_ai_review=lambda: {"summary": "local template review"},
            ai_review_latest=lambda: {"summary": "local template review"},
            evaluate_evidence=evidence,
            evidence_latest=evidence,
            market_quality=lambda: {"ok": True, "candles_count": 50},
            paper_status=lambda: {"open_trades": 0, "closed_trades": 1},
            paper_trades=lambda: [{"status": "CLOSED_TP"}],
            command_count=lambda: command_count,
        )

        first = manager.run_once()
        assert first.loop_count == 1
        assert (Path(tmp) / "long_forward_test_status.json").exists()

        started = manager.mark_started()
        started_again = manager.mark_started()
        assert started.running and started_again.running
        assert starts == 1
        assert orchestrator_running is True

        stopped = manager.mark_stopped()
        assert not stopped.running
        assert stops == 1
        assert orchestrator_running is False
        assert stopped.orchestrator_running is False
        assert manager.status().orchestrator_running is False

        report = manager.generate_daily_report()
        assert report.date
        assert (Path(tmp) / "long_forward_test_daily_reports.json").exists()

        safety = manager.status().safety
        assert safety["paper_only"] is True
        assert safety["live_execution_allowed"] is False
        assert safety["command_queueing_allowed"] is False
        assert safety["external_llm_allowed"] is False
        assert safety["live_execution_allowed"] is False
        assert safety["autostart_on_server_boot"] is False
        assert safety["mt5_commands_queued"] is False
        assert config.autostart_on_server_boot is False
        assert command_count == 0

    scan_files = [
        *Path("aurix_long_run").glob("*.py"),
        Path("scripts/check_long_forward_test.py"),
        Path("scripts/run_long_forward_test_once.py"),
        Path("scripts/start_long_forward_test.py"),
        Path("scripts/stop_long_forward_test.py"),
        Path("scripts/watch_long_forward_test.py"),
        Path("scripts/generate_long_forward_daily_report.py"),
    ]
    for file in scan_files:
        text = file.read_text(encoding="utf-8")
        assert "/commands/open-market" not in text, f"forbidden endpoint reference in {file}"

    print("OK: long forward-test self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
