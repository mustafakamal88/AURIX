from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from .models import Command, ExecutionResult


class JsonStore:
    def __init__(self, data_dir: str | Path = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.commands_file = self.data_dir / "commands.json"
        self.snapshot_file = self.data_dir / "latest_snapshot.json"
        self.results_file = self.data_dir / "execution_results.json"
        self.snapshot_debug_file = self.data_dir / "latest_snapshot_debug.json"
        self.risk_decisions_file = self.data_dir / "risk_decisions.json"

        for file in [self.commands_file, self.results_file, self.risk_decisions_file]:
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
        return self._read_json(self.commands_file, [])

    def save_commands(self, commands: list[dict[str, Any]]) -> None:
        self._write_json(self.commands_file, commands)

    def add_command(self, command: Command) -> Command:
        commands = self.list_commands()
        commands.append(command.model_dump())
        self.save_commands(commands)
        return command

    def next_command_for_terminal(self, terminal_id: str) -> Optional[Command]:
        commands = self.list_commands()
        chosen_index = None
        for i, cmd in enumerate(commands):
            if cmd.get("terminal_id") == terminal_id and cmd.get("status") == "QUEUED":
                chosen_index = i
                break

        if chosen_index is None:
            return None

        commands[chosen_index]["status"] = "DISPATCHED"
        self.save_commands(commands)
        return Command(**commands[chosen_index])

    def cancel_command(self, command_id: str) -> bool:
        commands = self.list_commands()
        changed = False
        for cmd in commands:
            if cmd.get("id") == command_id and cmd.get("status") in {"QUEUED", "DISPATCHED"}:
                cmd["status"] = "CANCELLED"
                changed = True
        self.save_commands(commands)
        return changed

    def mark_result(self, result: ExecutionResult) -> None:
        results = self._read_json(self.results_file, [])
        results.append(result.model_dump())
        self._write_json(self.results_file, results)

        commands = self.list_commands()
        for cmd in commands:
            if cmd.get("id") == result.command_id:
                cmd["status"] = "DONE" if result.ok else "FAILED"
        self.save_commands(commands)

    def list_results(self) -> list[dict[str, Any]]:
        return self._read_json(self.results_file, [])

    def add_risk_decision(self, decision: dict[str, Any]) -> None:
        decisions = self.list_risk_decisions()
        decisions.append(decision)
        self._write_json(self.risk_decisions_file, decisions)

    def list_risk_decisions(self) -> list[dict[str, Any]]:
        return self._read_json(self.risk_decisions_file, [])
