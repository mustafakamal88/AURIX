from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import EventBusConfig
from .models import AurixEvent, EventSafety, utc_now_iso
from .projector import project_events
from .state import initial_runtime_state


class EventBusStore:
    def __init__(self, data_dir: str | Path = "data", config: EventBusConfig | None = None):
        self.data_dir = Path(data_dir)
        self.config = config or EventBusConfig()
        self.event_dir = self.data_dir / "event_bus"
        self.event_dir.mkdir(parents=True, exist_ok=True)
        self.events_file = self.event_dir / "events.jsonl"
        self.status_file = self.event_dir / "status.json"
        self.state_snapshot_file = self.event_dir / "state_snapshot.json"
        self.state_history_file = self.event_dir / "state_history.jsonl"
        self.events_file.touch(exist_ok=True)
        if not self.status_file.exists():
            self._write_json_atomic(self.status_file, self._build_status([]))
        if not self.state_snapshot_file.exists():
            self._write_json_atomic(self.state_snapshot_file, initial_runtime_state(self.config.symbol, self.config.mode).model_dump())

    def _write_json_atomic(self, path: Path, value: Any) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")
        tmp.replace(path)

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _read_events(self) -> list[AurixEvent]:
        events: list[AurixEvent] = []
        if not self.events_file.exists():
            return events
        for line in self.events_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                events.append(AurixEvent(**data))
            except Exception:
                continue
        return events

    def _write_events(self, events: list[AurixEvent]) -> None:
        lines = [json.dumps(event.model_dump(mode="json"), default=str) + "\n" for event in events]
        tmp = self.events_file.with_suffix(".jsonl.tmp")
        tmp.write_text("".join(lines), encoding="utf-8")
        tmp.replace(self.events_file)

    def _build_status(self, events: list[AurixEvent]) -> dict[str, Any]:
        latest = events[-1] if events else None
        return {
            "enabled": self.config.enabled,
            "symbol": self.config.symbol,
            "mode": self.config.mode,
            "latest_exists": latest is not None,
            "event_count": len(events),
            "last_sequence": latest.sequence if latest else 0,
            "last_event_id": latest.event_id if latest else None,
            "last_event_type": latest.event_type.value if latest else None,
            "updated_at": utc_now_iso(),
            "events_path": str(self.events_file),
            "state_snapshot_path": str(self.state_snapshot_file),
            "state_exists": self.state_snapshot_file.exists(),
            "config": self.config.model_dump(),
            "safety": EventSafety().model_dump(),
        }

    def append_event(self, event: AurixEvent) -> AurixEvent:
        events = self._read_events()
        event.sequence = (events[-1].sequence if events else 0) + 1
        validated = AurixEvent(**event.model_dump())
        events.append(validated)
        limit = max(int(self.config.event_history_limit or 1), 1)
        if len(events) > limit:
            events = events[-limit:]
        self._write_events(events)
        self._write_json_atomic(self.status_file, self._build_status(events))
        self._write_state_snapshot(events)
        return validated

    def _write_state_snapshot(self, events: list[AurixEvent]) -> None:
        state = project_events(events, self.config.symbol, self.config.mode)
        if self.config.write_state_snapshot:
            self._write_json_atomic(self.state_snapshot_file, state.model_dump())
        history = self.state_history()
        history.append(state.model_dump())
        history = history[-max(int(self.config.state_history_limit or 1), 1):]
        tmp = self.state_history_file.with_suffix(".jsonl.tmp")
        tmp.write_text("".join(json.dumps(item, default=str) + "\n" for item in history), encoding="utf-8")
        tmp.replace(self.state_history_file)

    def recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        return [event.model_dump(mode="json") for event in self._read_events()[-max(int(limit), 1):]]

    def events_by_type(self, event_type: str, limit: int = 20) -> list[dict[str, Any]]:
        matched = [event for event in self._read_events() if event.event_type.value == event_type]
        return [event.model_dump(mode="json") for event in matched[-max(int(limit), 1):]]

    def events_by_correlation_id(self, correlation_id: str) -> list[dict[str, Any]]:
        return [event.model_dump(mode="json") for event in self._read_events() if event.correlation_id == correlation_id]

    def status(self) -> dict[str, Any]:
        events = self._read_events()
        status = self._build_status(events)
        self._write_json_atomic(self.status_file, status)
        return status

    def state_snapshot(self) -> dict[str, Any]:
        data = self._read_json(self.state_snapshot_file, None)
        if isinstance(data, dict):
            return data
        state = project_events(self._read_events(), self.config.symbol, self.config.mode)
        self._write_json_atomic(self.state_snapshot_file, state.model_dump())
        return state.model_dump()

    def state_history(self) -> list[dict[str, Any]]:
        if not self.state_history_file.exists():
            return []
        items: list[dict[str, Any]] = []
        for line in self.state_history_file.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                items.append(item)
        return items

    def reset(self) -> dict[str, Any]:
        self.events_file.write_text("", encoding="utf-8")
        self.state_history_file.write_text("", encoding="utf-8")
        state = initial_runtime_state(self.config.symbol, self.config.mode)
        self._write_json_atomic(self.state_snapshot_file, state.model_dump())
        status = self._build_status([])
        self._write_json_atomic(self.status_file, status)
        return status
