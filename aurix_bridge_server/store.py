from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .models import Command, ExecutionResult, utc_now_iso


TERMINAL_COMMAND_STATUSES = {
    "EXECUTION_BLOCKED",
    "EXECUTION_FAILED",
    "EXECUTION_FILLED",
    "CANCELLED",
    "EXPIRED",
}

DEFAULT_COMMAND_EXPIRY_SECONDS = 30


class JsonStore:
    def __init__(self, data_dir: str | Path = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.commands_file = self.data_dir / "commands.json"
        self.snapshot_file = self.data_dir / "latest_snapshot.json"
        self.results_file = self.data_dir / "execution_results.json"
        self.snapshot_debug_file = self.data_dir / "latest_snapshot_debug.json"
        self.risk_decisions_file = self.data_dir / "risk_decisions.json"
        self.strategy_signals_file = self.data_dir / "strategy_signals.json"

        for file in [self.commands_file, self.results_file, self.risk_decisions_file, self.strategy_signals_file]:
            if not file.exists():
                file.write_text("[]", encoding="utf-8")

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _write_json(self, path: Path, value: Any) -> None:
        path.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")

    def save_snapshot(self, snapshot: dict[str, Any]) -> None:
        self._write_json(self.snapshot_file, snapshot)

    def save_snapshot_debug(self, snapshot: Any) -> None:
        self._write_json(self.snapshot_debug_file, snapshot)

    def latest_snapshot(self) -> Optional[dict[str, Any]]:
        return self._read_json(self.snapshot_file, None)

    def list_commands(self) -> list[dict[str, Any]]:
        commands = self._read_json(self.commands_file, [])
        return [self._normalize_command(cmd) for cmd in commands if isinstance(cmd, dict)]

    def save_commands(self, commands: list[dict[str, Any]]) -> None:
        self._write_json(self.commands_file, commands)

    def add_command(self, command: Command) -> Command:
        commands = self.list_commands()
        commands.append(self._normalize_command(command.model_dump()))
        self.save_commands(commands)
        return command

    def _normalize_command(self, cmd: dict[str, Any]) -> dict[str, Any]:
        status = cmd.get("status") or "QUEUED"
        if status == "DONE":
            status = "EXECUTION_FILLED"
        elif status == "FAILED":
            status = "EXECUTION_FAILED"

        cmd["status"] = status
        cmd.setdefault("risk_decision_id", None)
        cmd.setdefault("dispatched_at", None)
        cmd.setdefault("completed_at", None)
        cmd.setdefault("dispatch_count", 0)
        cmd.setdefault("last_error", None)
        cmd.setdefault("execution_result_id", None)
        return cmd

    def _parse_time(self, value: Any) -> Optional[datetime]:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    def expire_queued_commands(self, expiry_seconds: int = DEFAULT_COMMAND_EXPIRY_SECONDS) -> int:
        commands = self.list_commands()
        now = datetime.now(timezone.utc)
        expired = 0

        for cmd in commands:
            if cmd.get("status") != "QUEUED":
                continue
            created_at = self._parse_time(cmd.get("created_at"))
            if created_at is None:
                continue
            age_seconds = (now - created_at).total_seconds()
            if age_seconds > expiry_seconds:
                cmd["status"] = "EXPIRED"
                cmd["completed_at"] = utc_now_iso()
                cmd["last_error"] = f"Command expired after {expiry_seconds} seconds"
                expired += 1

        if expired:
            self.save_commands(commands)
        return expired

    def next_command_for_terminal(self, terminal_id: str) -> Optional[Command]:
        self.expire_queued_commands()
        commands = self.list_commands()
        chosen_index = None
        for i, cmd in enumerate(commands):
            if (
                cmd.get("terminal_id") == terminal_id
                and cmd.get("status") == "QUEUED"
                and int(cmd.get("dispatch_count") or 0) == 0
            ):
                chosen_index = i
                break

        if chosen_index is None:
            return None

        commands[chosen_index]["status"] = "DISPATCHED"
        commands[chosen_index]["dispatched_at"] = utc_now_iso()
        commands[chosen_index]["dispatch_count"] = int(commands[chosen_index].get("dispatch_count") or 0) + 1
        self.save_commands(commands)
        return Command(**commands[chosen_index])

    def cancel_command(self, command_id: str) -> bool:
        commands = self.list_commands()
        changed = False
        for cmd in commands:
            if cmd.get("id") == command_id and cmd.get("status") == "QUEUED":
                cmd["status"] = "CANCELLED"
                cmd["completed_at"] = utc_now_iso()
                changed = True
        self.save_commands(commands)
        return changed

    def get_command(self, command_id: str) -> Optional[dict[str, Any]]:
        self.expire_queued_commands()
        for cmd in self.list_commands():
            if cmd.get("id") == command_id:
                return cmd
        return None

    def list_open_commands(self) -> list[dict[str, Any]]:
        self.expire_queued_commands()
        return [cmd for cmd in self.list_commands() if cmd.get("status") not in TERMINAL_COMMAND_STATUSES]

    def set_command_risk_decision(self, command_id: str, risk_decision_id: str) -> None:
        commands = self.list_commands()
        for cmd in commands:
            if cmd.get("id") == command_id:
                cmd["risk_decision_id"] = risk_decision_id
                break
        self.save_commands(commands)

    def mark_result(self, result: ExecutionResult) -> None:
        results = self._read_json(self.results_file, [])
        results.append(result.model_dump())
        self._write_json(self.results_file, results)

        commands = self.list_commands()
        for cmd in commands:
            if cmd.get("id") == result.command_id:
                cmd["execution_result_id"] = result.id
                cmd["completed_at"] = utc_now_iso()
                cmd["last_error"] = "" if result.ok else result.message
                cmd["status"] = self._status_from_execution_result(result)
        self.save_commands(commands)

    def list_results(self) -> list[dict[str, Any]]:
        return self._read_json(self.results_file, [])

    def _status_from_execution_result(self, result: ExecutionResult) -> str:
        if result.ok and ((result.order or 0) > 0 or (result.deal or 0) > 0):
            return "EXECUTION_FILLED"

        message = result.message.lower()
        if not result.ok and ("safety gate" in message or "blocked" in message):
            return "EXECUTION_BLOCKED"

        return "EXECUTION_FAILED"

    def add_risk_decision(self, decision: dict[str, Any]) -> None:
        decisions = self.list_risk_decisions()
        decisions.append(decision)
        self._write_json(self.risk_decisions_file, decisions)

    def list_risk_decisions(self) -> list[dict[str, Any]]:
        return self._read_json(self.risk_decisions_file, [])

    def add_strategy_signal(self, signal: dict[str, Any]) -> None:
        signals = self.list_strategy_signals()
        signals.append(signal)
        self._write_json(self.strategy_signals_file, signals)

    def list_strategy_signals(self) -> list[dict[str, Any]]:
        return self._read_json(self.strategy_signals_file, [])

    def update_strategy_signal(self, signal_id: str, updates: dict[str, Any]) -> None:
        signals = self.list_strategy_signals()
        changed = False
        for signal in signals:
            if signal.get("id") == signal_id:
                signal.update(updates)
                changed = True
                break
        if changed:
            self._write_json(self.strategy_signals_file, signals)

    def reset_strategy_signals(self) -> None:
        self._write_json(self.strategy_signals_file, [])
