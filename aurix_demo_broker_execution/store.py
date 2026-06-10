from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional, Union
from uuid import uuid4

from aurix_common.persistence import write_json_atomic


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


class DemoBrokerExecutionStore:
    def __init__(self, data_dir: Union[str, Path] = "data"):
        self.root = Path(data_dir) / "demo_broker_execution"
        self.root.mkdir(parents=True, exist_ok=True)
        self.commands_file = self.root / "commands.json"
        self.status_file = self.root / "status.json"
        self.results_file = self.root / "execution_results.json"
        self.baseline_file = self.root / "daily_baseline.json"
        for path, default in [(self.commands_file, []), (self.results_file, [])]:
            if not path.exists():
                write_json_atomic(path, default)

    def list_commands(self) -> list[dict[str, Any]]:
        value = _read_json(self.commands_file, [])
        return value if isinstance(value, list) else []

    def save_commands(self, commands: list[dict[str, Any]]) -> None:
        write_json_atomic(self.commands_file, commands)

    def latest_command(self) -> dict[str, Any]:
        commands = self.list_commands()
        return commands[-1] if commands else {}

    def pending_for_terminal(self, terminal_id: str) -> Optional[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        changed = False
        selected = None
        commands = self.list_commands()
        for command in commands:
            if command.get("status") == "PENDING":
                expires = _parse_time(command.get("expires_at"))
                if expires and expires < now:
                    command["status"] = "EXPIRED"
                    changed = True
                    continue
                if command.get("terminal_id") == terminal_id and selected is None:
                    selected = command
        if changed:
            self.save_commands(commands)
        return selected

    def add_command(self, command: dict[str, Any]) -> dict[str, Any]:
        commands = self.list_commands()
        commands.append(command)
        self.save_commands(commands)
        return command

    def mark_delivered(self, command_id: str) -> Optional[dict[str, Any]]:
        commands = self.list_commands()
        selected = None
        for command in commands:
            if command.get("command_id") == command_id and command.get("status") == "PENDING":
                command["status"] = "DELIVERED"
                command["delivered_at"] = utc_now_iso()
                selected = command
                break
        self.save_commands(commands)
        return selected

    def has_duplicate_pending(self, signal_id: Optional[str]) -> bool:
        if not signal_id:
            return False
        return any(cmd.get("signal_id") == signal_id and cmd.get("status") in {"PENDING", "DELIVERED"} for cmd in self.list_commands())

    def create_command(self, *, terminal_id: str, side: str, symbol: str, volume: float, stop_loss: float, take_profit: float, strategy_id: str, signal_id: str, runtime_session_id: str, provenance: dict[str, Any], safety_checks_snapshot: dict[str, Any], ttl_seconds: int, magic_number: int) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        command_id = uuid4().hex
        command = {
            "command_id": command_id,
            "terminal_id": terminal_id,
            "mode": "DEMO_BROKER",
            "action": "OPEN_MARKET",
            "symbol": symbol,
            "side": side,
            "volume": volume,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "magic_number": magic_number,
            "strategy_id": strategy_id,
            "signal_id": signal_id,
            "runtime_session_id": runtime_session_id,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=ttl_seconds)).isoformat(),
            "status": "PENDING",
            "provenance": provenance,
            "safety_checks_snapshot": safety_checks_snapshot,
        }
        return self.add_command(command)

    def append_execution_result(self, result: dict[str, Any]) -> dict[str, Any]:
        results = _read_json(self.results_file, [])
        if not isinstance(results, list):
            results = []
        results.append(result)
        write_json_atomic(self.results_file, results)
        command_id = result.get("command_id")
        if command_id:
            commands = self.list_commands()
            for command in commands:
                if command.get("command_id") == command_id:
                    command["status"] = str(result.get("status") or ("FILLED" if result.get("ok") else "ERROR"))
                    command["completed_at"] = utc_now_iso()
                    command["execution_result"] = result
            self.save_commands(commands)
        return result

    def latest_execution_result(self) -> dict[str, Any]:
        results = _read_json(self.results_file, [])
        return results[-1] if isinstance(results, list) and results else {}

    def get_or_create_daily_baseline(self, *, balance: Optional[float], equity: Optional[float]) -> dict[str, Any]:
        today = datetime.now(timezone.utc).date().isoformat()
        value = _read_json(self.baseline_file, {})
        if isinstance(value, dict) and value.get("date") == today:
            return value
        value = {"date": today, "start_balance": balance, "start_equity": equity, "created_at": utc_now_iso()}
        write_json_atomic(self.baseline_file, value)
        return value

    def write_status(self, status: dict[str, Any]) -> dict[str, Any]:
        write_json_atomic(self.status_file, status)
        return status

    def latest_status(self) -> dict[str, Any]:
        value = _read_json(self.status_file, {})
        return value if isinstance(value, dict) else {}


def _parse_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
