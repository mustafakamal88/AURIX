from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from aurix_bridge_server.models import utc_now_iso

from .config import LongForwardTestConfig
from .models import LongForwardDailyReport, LongForwardTestStatus
from .report import as_dict, build_daily_report


Callback = Callable[[], dict[str, Any]]


class LongForwardTestManager:
    def __init__(
        self,
        data_dir: str | Path = "data",
        config: LongForwardTestConfig | None = None,
        *,
        operator_status: Callback | None = None,
        operator_summary: Callback | None = None,
        orchestrator_status: Callback | None = None,
        orchestrator_start: Callback | None = None,
        orchestrator_stop: Callback | None = None,
        orchestrator_run_once: Callback | None = None,
        daemon_status: Callback | None = None,
        daemon_start: Callback | None = None,
        forward_test_status: Callback | None = None,
        update_forward_test: Callback | None = None,
        generate_analytics: Callback | None = None,
        analytics_summary: Callback | None = None,
        generate_journal: Callback | None = None,
        journal_status: Callback | None = None,
        generate_ai_review: Callback | None = None,
        ai_review_latest: Callback | None = None,
        evaluate_evidence: Callback | None = None,
        evidence_latest: Callback | None = None,
        market_quality: Callback | None = None,
        paper_status: Callback | None = None,
        paper_trades: Callback | None = None,
        command_count: Callable[[], int] | None = None,
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or LongForwardTestConfig()
        self.status_file = self.data_dir / "long_forward_test_status.json"
        self.daily_reports_file = self.data_dir / "long_forward_test_daily_reports.json"
        self.operator_status = operator_status
        self.operator_summary = operator_summary
        self.orchestrator_status = orchestrator_status
        self.orchestrator_start = orchestrator_start
        self.orchestrator_stop = orchestrator_stop
        self.orchestrator_run_once = orchestrator_run_once
        self.daemon_status = daemon_status
        self.daemon_start = daemon_start
        self.forward_test_status = forward_test_status
        self.update_forward_test = update_forward_test
        self.generate_analytics = generate_analytics
        self.analytics_summary = analytics_summary
        self.generate_journal = generate_journal
        self.journal_status = journal_status
        self.generate_ai_review = generate_ai_review
        self.ai_review_latest = ai_review_latest
        self.evaluate_evidence = evaluate_evidence
        self.evidence_latest = evidence_latest
        self.market_quality = market_quality
        self.paper_status = paper_status
        self.paper_trades = paper_trades
        self.command_count = command_count
        self._running = False
        self._started_orchestrator = False

    def status(self) -> LongForwardTestStatus:
        data = self._read_dict(self.status_file)
        if data:
            status = LongForwardTestStatus(**data)
            status.running = self._running
            status.safety = self._safety()
            self._refresh_runtime_status(status)
            self._save_status(status)
            return status
        status = self._base_status()
        self._refresh_runtime_status(status)
        return status

    def mark_started(self) -> LongForwardTestStatus:
        status = self.status()
        if self._running:
            return status
        now = utc_now_iso()
        self._running = True
        status.running = True
        status.started_at = status.started_at or now
        status.stopped_at = None
        status.last_heartbeat_at = now
        status.safety = self._safety()
        if self.config.auto_start_orchestrator:
            before = self._call(self.orchestrator_status, "orchestrator_status")
            result = self._call(self.orchestrator_start, "orchestrator_start")
            self._started_orchestrator = not bool(before.get("running"))
            status.errors.extend(str(error) for error in result.get("errors") or [])
            if bool(before.get("running")):
                status.warnings.append("orchestrator is still running independently")
        if self.config.auto_start_daemon:
            result = self._call(self.daemon_start, "daemon_start")
            status.errors.extend(str(error) for error in result.get("errors") or [])
        self._refresh_runtime_status(status)
        self._save_status(status)
        return status

    def mark_stopped(self) -> LongForwardTestStatus:
        status = self.status()
        self._running = False
        status.running = False
        status.stopped_at = utc_now_iso()
        status.last_heartbeat_at = status.stopped_at
        if self._started_orchestrator:
            result = self._call(self.orchestrator_stop, "orchestrator_stop")
            status.errors.extend(str(error) for error in result.get("errors") or [])
            self._started_orchestrator = False
        else:
            orchestrator = self._call(self.orchestrator_status, "orchestrator_status")
            if bool(orchestrator.get("running")):
                status.warnings.append("orchestrator is still running independently")
        self._refresh_runtime_status(status)
        status.safety = self._safety()
        self._save_status(status)
        return status

    def is_running(self) -> bool:
        return self._running

    def reset(self) -> LongForwardTestStatus:
        self._running = False
        self._started_orchestrator = False
        status = self._base_status()
        self.status_file.write_text(json.dumps(status.model_dump(), indent=2, default=str), encoding="utf-8")
        self.daily_reports_file.write_text("[]", encoding="utf-8")
        return status

    def run_once(self) -> LongForwardTestStatus:
        previous = self.status()
        status = previous.model_copy(deep=True)
        status.enabled = self.config.enabled
        status.mode = "PAPER"
        status.symbol = self.config.symbol
        status.loop_count = previous.loop_count + 1
        status.running = self._running
        status.warnings = []
        status.errors = []
        commands_before = self.command_count() if self.command_count else 0

        try:
            self._validate_safety(status)
            summary = self._call(self.operator_summary, "operator_summary")
            operator_status = self._call(self.operator_status, "operator_status")
            if self.config.auto_start_orchestrator and self._running:
                orchestrator = self._call(self.orchestrator_run_once, "orchestrator_run_once")
            else:
                orchestrator = self._call(self.orchestrator_status, "orchestrator_status")
            forward = self._call(self.update_forward_test, "forward_test_update")
            analytics = self._call(self.generate_analytics, "analytics_generate")
            journal = self._call(self.generate_journal, "journal_generate")
            evidence = self._call(self.evaluate_evidence, "evidence_evaluate")
            daemon = self._call(self.daemon_status, "daemon_status")
            paper = self._call(self.paper_status, "paper_status")

            status.current_session = summary.get("session") or orchestrator.get("current_session")
            status.session_allowed = bool(orchestrator.get("session_allowed") or summary.get("orchestrator_session_allowed"))
            status.orchestrator_running = bool(orchestrator.get("running"))
            status.orchestrator_loop_count = int(orchestrator.get("loop_count") or 0)
            status.daemon_running = bool(daemon.get("running"))
            status.forward_test_status = forward.get("status") or as_dict(forward.get("campaign")).get("status")
            progress = as_dict(forward.get("progress")) or as_dict(as_dict(forward.get("campaign")).get("progress"))
            status.forward_test_progress = float(progress.get("percent") or 0.0)
            campaign = as_dict(forward.get("campaign")) if forward.get("campaign") else forward
            status.recorded_candles = int(campaign.get("recorded_candles") or 0)
            status.paper_open_trades = int(paper.get("open_trades") or 0)
            status.paper_closed_trades = int(campaign.get("closed_paper_trades") or analytics.get("closed_trades") or 0)
            status.latest_expectancy_r = float(analytics.get("expectancy_r") or summary.get("paper_expectancy_r") or 0.0)
            status.evidence_status = evidence.get("status")
            status.evidence_live_ready = bool(evidence.get("live_ready"))
            status.operator_ok = bool(summary.get("ok"))
            status.warnings.extend(str(warning) for warning in summary.get("warnings") or [])
            status.warnings.extend(str(warning) for warning in evidence.get("warnings") or [])
            status.errors.extend(_errors_from_many(summary, operator_status, orchestrator, forward, analytics, journal, evidence, daemon, paper))
            if self.command_count and self.command_count() != commands_before:
                status.errors.append("command queue changed during long forward-test cycle")
        except Exception as exc:
            status.errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            status.last_heartbeat_at = utc_now_iso()
            status.safety = self._safety()
            self._save_status(status)
        return status

    def generate_daily_report(self) -> LongForwardDailyReport:
        report = build_daily_report(
            {
                "operator_status": self._call(self.operator_status, "operator_status"),
                "forward_test_status": self._call(self.forward_test_status, "forward_test_status"),
                "paper_trades": self._call(self.paper_trades, "paper_trades").get("items", []),
                "analytics_summary": self._call(self.analytics_summary, "analytics_summary"),
                "journal_status": self._call(self.journal_status, "journal_status"),
                "ai_review": self._call(self.ai_review_latest, "ai_review_latest"),
                "evidence_report": self._call(self.evidence_latest, "evidence_latest"),
                "market_quality": self._call(self.market_quality, "market_quality"),
            }
        )
        reports = self.list_daily_reports()
        reports.append(report.model_dump())
        self.daily_reports_file.write_text(json.dumps(reports, indent=2, default=str), encoding="utf-8")
        status = self.status()
        status.daily_report_generated_at = report.generated_at
        status.safety = self._safety()
        self._save_status(status)
        return report

    def list_daily_reports(self) -> list[dict[str, Any]]:
        data = self._read_list(self.daily_reports_file)
        return [item for item in data if isinstance(item, dict)]

    def _validate_safety(self, status: LongForwardTestStatus) -> None:
        if not self.config.enabled:
            status.errors.append("long forward-test disabled")
        if self.config.mode != "PAPER":
            status.errors.append("long forward-test mode must be PAPER")
        if self.config.allow_command_queueing:
            status.errors.append("allow_command_queueing must remain false")
        if self.config.allow_live_execution:
            status.errors.append("allow_live_execution must remain false")
        if self.config.allow_external_llm:
            status.errors.append("allow_external_llm must remain false")
        if self.config.autostart_on_server_boot:
            status.errors.append("autostart_on_server_boot must remain false")

    def _base_status(self) -> LongForwardTestStatus:
        return LongForwardTestStatus(enabled=self.config.enabled, mode="PAPER", symbol=self.config.symbol, safety=self._safety())

    def _refresh_runtime_status(self, status: LongForwardTestStatus) -> None:
        orchestrator = self._call(self.orchestrator_status, "orchestrator_status")
        daemon = self._call(self.daemon_status, "daemon_status")
        if orchestrator:
            status.orchestrator_running = bool(orchestrator.get("running"))
            status.orchestrator_loop_count = int(orchestrator.get("loop_count") or status.orchestrator_loop_count or 0)
            status.current_session = orchestrator.get("current_session") or status.current_session
            status.session_allowed = bool(orchestrator.get("session_allowed"))
            if status.orchestrator_running and not self._running and not self._started_orchestrator:
                if "orchestrator is still running independently" not in status.warnings:
                    status.warnings.append("orchestrator is still running independently")
        if daemon:
            status.daemon_running = bool(daemon.get("running"))

    def _safety(self) -> dict[str, Any]:
        return {
            "paper_only": True,
            "live_execution_allowed": False,
            "command_queueing_allowed": False,
            "external_llm_allowed": False,
            "autostart_on_server_boot": False,
            "mt5_commands_queued": False,
        }

    def _call(self, callback: Callback | None, label: str) -> dict[str, Any]:
        if callback is None:
            return {}
        try:
            value = callback()
        except Exception as exc:
            return {"errors": [f"{label}: {type(exc).__name__}: {exc}"]}
        if isinstance(value, list):
            return {"items": value}
        return value if isinstance(value, dict) else {}

    def _read_dict(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _read_list(self, path: Path) -> list[Any]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return data if isinstance(data, list) else []

    def _save_status(self, status: LongForwardTestStatus) -> None:
        self.status_file.write_text(json.dumps(status.model_dump(), indent=2, default=str), encoding="utf-8")


def _errors_from_many(*values: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for value in values:
        errors.extend(str(error) for error in value.get("errors") or [])
    return errors
