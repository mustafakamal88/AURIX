from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional

from aurix_bridge_server.models import utc_now_iso

from .config import DaemonConfig
from .models import DaemonStatus


Callback = Callable[[], dict[str, Any]]


class PaperDaemonRunner:
    def __init__(
        self,
        data_dir: str | Path = "data",
        config: DaemonConfig | None = None,
        *,
        supervisor_run_once: Callback | None = None,
        generate_analytics: Callback | None = None,
        update_journal: Callback | None = None,
        generate_ai_review: Callback | None = None,
        evaluate_evidence: Callback | None = None,
        command_count: Callable[[], int] | None = None,
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.status_file = self.data_dir / "daemon_status.json"
        self.config = config or DaemonConfig()
        self.supervisor_run_once = supervisor_run_once
        self.generate_analytics = generate_analytics
        self.update_journal = update_journal
        self.generate_ai_review = generate_ai_review
        self.evaluate_evidence = evaluate_evidence
        self.command_count = command_count
        self._running = False

    def status(self) -> DaemonStatus:
        data = self._read_dict(self.status_file)
        if data:
            status = DaemonStatus(**data)
            status.running = self._running
            status.safety = self._safety()
            return status
        return self._base_status()

    def reset(self) -> DaemonStatus:
        self._running = False
        status = self._base_status()
        self._save_status(status)
        return status

    def mark_started(self) -> DaemonStatus:
        status = self.status()
        if self._running:
            return status
        now = utc_now_iso()
        status.enabled = self.config.enabled
        status.mode = self.config.mode
        status.running = True
        status.started_at = status.started_at or now
        status.stopped_at = None
        status.last_heartbeat_at = now
        status.safety = self._safety()
        self._running = True
        self._save_status(status)
        return status

    def mark_stopped(self) -> DaemonStatus:
        status = self.status()
        self._running = False
        status.running = False
        status.stopped_at = utc_now_iso()
        status.last_heartbeat_at = status.stopped_at
        status.safety = self._safety()
        self._save_status(status)
        return status

    def is_running(self) -> bool:
        return self._running

    def run_once(self) -> DaemonStatus:
        previous = self.status()
        status = previous.model_copy(deep=True)
        status.enabled = self.config.enabled
        status.mode = self.config.mode
        status.loop_count = previous.loop_count + 1
        status.errors = []
        status.running = self._running
        status.safety = self._safety()
        commands_before = self.command_count() if self.command_count is not None else 0

        try:
            self._validate_safety(status)
            supervisor_status = self._call(self.supervisor_run_once, "supervisor")
            if supervisor_status:
                status.last_snapshot_updated_at = supervisor_status.get("last_snapshot_updated_at")
                status.market_quality_ok = bool(supervisor_status.get("market_quality_ok"))
                status.last_context_id = supervisor_status.get("context_id")
                status.last_signal_id = supervisor_status.get("strategy_signal_id")
                status.last_paper_created = bool(supervisor_status.get("paper_created"))
                status.open_paper_trades = int(supervisor_status.get("paper_open_count") or 0)
                status.errors.extend(str(error) for error in supervisor_status.get("errors") or [])

            if self._should_run(status.loop_count, self.config.run_analytics_every_loops):
                analytics = self._call(self.generate_analytics, "analytics")
                self._extend_errors(status, analytics)
                if analytics:
                    status.last_analytics_generated_at = analytics.get("generated_at") or utc_now_iso()

            if self._should_run(status.loop_count, self.config.run_journal_every_loops):
                journal = self._call(self.update_journal, "journal")
                self._extend_errors(status, journal)
                if journal:
                    status.last_journal_updated_at = utc_now_iso()

            if self._should_run(status.loop_count, self.config.run_ai_review_every_loops):
                review = self._call(self.generate_ai_review, "ai_review")
                self._extend_errors(status, review)
                if review:
                    status.last_ai_review_id = review.get("id")

            if self._should_run(status.loop_count, self.config.run_evidence_every_loops):
                evidence = self._call(self.evaluate_evidence, "evidence")
                self._extend_errors(status, evidence)
                if evidence:
                    status.last_evidence_status = evidence.get("status")

            if self.command_count is not None and self.command_count() != commands_before:
                status.errors.append("command queue changed during daemon cycle")
        except Exception as exc:
            status.errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            status.last_heartbeat_at = utc_now_iso()
            status.safety = self._safety()
            self._save_status(status)

        return status

    def _validate_safety(self, status: DaemonStatus) -> None:
        if not self.config.enabled:
            status.errors.append("daemon disabled")
        if self.config.mode != "PAPER":
            status.errors.append("daemon mode must be PAPER")
        if self.config.allow_command_queueing:
            status.errors.append("allow_command_queueing must remain false")
        if self.config.allow_live_execution:
            status.errors.append("allow_live_execution must remain false")
        if self.config.allow_external_llm:
            status.errors.append("allow_external_llm must remain false")

    def _call(self, callback: Callback | None, label: str) -> dict[str, Any]:
        if callback is None:
            return {}
        try:
            value = callback()
        except Exception as exc:
            return {"errors": [f"{label}: {type(exc).__name__}: {exc}"]}
        return value if isinstance(value, dict) else {}

    def _extend_errors(self, status: DaemonStatus, result: dict[str, Any]) -> None:
        status.errors.extend(str(error) for error in result.get("errors") or [])

    def _should_run(self, loop_count: int, every: int) -> bool:
        return every > 0 and loop_count % every == 0

    def _base_status(self) -> DaemonStatus:
        return DaemonStatus(enabled=self.config.enabled, mode=self.config.mode, safety=self._safety())

    def _safety(self) -> dict[str, Any]:
        return {
            "paper_only": True,
            "live_execution_allowed": False,
            "command_queueing_allowed": False,
            "external_llm_allowed": False,
            "mt5_commands_queued": False,
        }

    def _read_dict(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _save_status(self, status: DaemonStatus) -> None:
        self.status_file.write_text(json.dumps(status.model_dump(), indent=2, default=str), encoding="utf-8")
