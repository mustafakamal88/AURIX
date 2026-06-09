from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from aurix_bridge_server.models import utc_now_iso

from .config import OrchestratorConfig
from .models import OrchestratorStatus


Callback = Callable[[], dict[str, Any]]


class SessionOrchestrator:
    def __init__(
        self,
        data_dir: str | Path = "data",
        config: OrchestratorConfig | None = None,
        *,
        evaluate_context: Callback | None = None,
        daemon_run_once: Callback | None = None,
        daemon_stop: Callback | None = None,
        daemon_status: Callback | None = None,
        update_forward_test: Callback | None = None,
        evaluate_evidence: Callback | None = None,
        generate_analytics: Callback | None = None,
        generate_journal: Callback | None = None,
        generate_ai_review: Callback | None = None,
        operator_summary: Callback | None = None,
        command_count: Callable[[], int] | None = None,
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.status_file = self.data_dir / "orchestrator_status.json"
        self.config = config or OrchestratorConfig()
        self.evaluate_context = evaluate_context
        self.daemon_run_once = daemon_run_once
        self.daemon_stop = daemon_stop
        self.daemon_status = daemon_status
        self.update_forward_test = update_forward_test
        self.evaluate_evidence = evaluate_evidence
        self.generate_analytics = generate_analytics
        self.generate_journal = generate_journal
        self.generate_ai_review = generate_ai_review
        self.operator_summary = operator_summary
        self.command_count = command_count
        self._running = False

    def status(self) -> OrchestratorStatus:
        data = self._read_dict(self.status_file)
        if data:
            status = OrchestratorStatus(**data)
            status.running = self._running
            status.safety = self._safety()
            return status
        return self._base_status()

    def reset(self) -> OrchestratorStatus:
        self._running = False
        status = self._base_status()
        self._save_status(status)
        return status

    def mark_started(self) -> OrchestratorStatus:
        status = self.status()
        if self._running:
            return status
        now = utc_now_iso()
        status.running = True
        status.started_at = status.started_at or now
        status.stopped_at = None
        status.last_heartbeat_at = now
        status.safety = self._safety()
        self._running = True
        self._save_status(status)
        return status

    def mark_stopped(self) -> OrchestratorStatus:
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

    def run_once(self) -> OrchestratorStatus:
        previous = self.status()
        status = previous.model_copy(deep=True)
        status.enabled = self.config.enabled
        status.mode = self.config.mode
        status.symbol = self.config.symbol
        status.loop_count = previous.loop_count + 1
        status.running = self._running
        status.actions_taken = []
        status.warnings = []
        status.errors = []
        status.safety = self._safety()
        commands_before = self.command_count() if self.command_count else 0

        try:
            self._validate_safety(status)
            context = self._call(self.evaluate_context, "context")
            self._extend_errors(status, context)
            status.current_session = context.get("session_name")
            status.market_quality_ok = bool(context.get("data_quality_ok") and context.get("spread_ok"))
            status.session_allowed = bool(status.current_session in set(self.config.allowed_sessions))

            operator = self._call(self.operator_summary, "operator")
            self._extend_errors(status, operator)
            status.operator_ok = bool(operator.get("ok"))

            if status.session_allowed and self.config.run_daemon_during_allowed_sessions:
                daemon = self._call(self.daemon_run_once, "daemon")
                self._extend_errors(status, daemon)
                status.actions_taken.append("daemon_run_once")
            elif self.config.stop_daemon_when_session_closed:
                daemon = self._call(self.daemon_stop, "daemon_stop")
                self._extend_errors(status, daemon)
                status.actions_taken.append("daemon_stop")
            else:
                daemon = self._call(self.daemon_status, "daemon_status")
                self._extend_errors(status, daemon)

            self._apply_daemon(status, daemon)

            if self._should_run(status.loop_count, self.config.update_forward_test_every_loops):
                campaign = self._call(self.update_forward_test, "forward_test")
                self._extend_errors(status, campaign)
                status.forward_test_status = campaign.get("status")
                status.forward_test_progress = float(_as_dict(campaign.get("progress")).get("percent") or 0.0)
                status.actions_taken.append("forward_test_update")

            if self._should_run(status.loop_count, self.config.generate_analytics_every_loops):
                result = self._call(self.generate_analytics, "analytics")
                self._extend_errors(status, result)
                status.actions_taken.append("analytics_generate")

            if self._should_run(status.loop_count, self.config.generate_journal_every_loops):
                result = self._call(self.generate_journal, "journal")
                self._extend_errors(status, result)
                status.actions_taken.append("journal_generate")

            if self._should_run(status.loop_count, self.config.generate_ai_review_every_loops):
                result = self._call(self.generate_ai_review, "ai_review")
                self._extend_errors(status, result)
                status.actions_taken.append("ai_review_generate")

            if self._should_run(status.loop_count, self.config.evaluate_evidence_every_loops):
                evidence = self._call(self.evaluate_evidence, "evidence")
                self._extend_errors(status, evidence)
                status.evidence_status = evidence.get("status")
                status.evidence_live_ready = bool(evidence.get("live_ready"))
                status.actions_taken.append("evidence_evaluate")

            if self.command_count and self.command_count() != commands_before:
                status.errors.append("command queue changed during orchestrator cycle")
        except Exception as exc:
            status.errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            if not status.session_allowed:
                status.warnings.append("session not allowed")
            status.last_heartbeat_at = utc_now_iso()
            status.safety = self._safety()
            self._save_status(status)

        return status

    def _apply_daemon(self, status: OrchestratorStatus, daemon: dict[str, Any]) -> None:
        status.daemon_running = bool(daemon.get("running"))
        status.daemon_loop_count = int(daemon.get("loop_count") or 0)

    def _validate_safety(self, status: OrchestratorStatus) -> None:
        if not self.config.enabled:
            status.errors.append("orchestrator disabled")
        if self.config.mode != "PAPER":
            status.errors.append("orchestrator mode must be PAPER")
        if self.config.allow_command_queueing:
            status.errors.append("allow_command_queueing must remain false")
        if self.config.allow_live_execution:
            status.errors.append("allow_live_execution must remain false")
        if self.config.allow_external_llm:
            status.errors.append("allow_external_llm must remain false")
        if self.config.autostart_on_server_boot:
            status.errors.append("autostart_on_server_boot must remain false")

    def _call(self, callback: Callback | None, label: str) -> dict[str, Any]:
        if callback is None:
            return {}
        try:
            value = callback()
        except Exception as exc:
            return {"errors": [f"{label}: {type(exc).__name__}: {exc}"]}
        return value if isinstance(value, dict) else {}

    def _extend_errors(self, status: OrchestratorStatus, result: dict[str, Any]) -> None:
        status.errors.extend(str(error) for error in result.get("errors") or [])

    def _should_run(self, loop_count: int, every: int) -> bool:
        return every > 0 and loop_count % every == 0

    def _base_status(self) -> OrchestratorStatus:
        return OrchestratorStatus(enabled=self.config.enabled, mode=self.config.mode, symbol=self.config.symbol, safety=self._safety())

    def _safety(self) -> dict[str, Any]:
        return {
            "paper_only": True,
            "live_execution_allowed": False,
            "command_queueing_allowed": False,
            "external_llm_allowed": False,
            "autostart_on_server_boot": False,
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

    def _save_status(self, status: OrchestratorStatus) -> None:
        self.status_file.write_text(json.dumps(status.model_dump(), indent=2, default=str), encoding="utf-8")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
