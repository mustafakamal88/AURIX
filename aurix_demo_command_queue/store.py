from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aurix_common import write_json_atomic, write_text_atomic

from .config import DemoCommandQueueConfig
from .models import DemoCommandAuditRecord, DemoCommandPreview, DemoCommandQueueSafety, DemoCommandQueueStatus, DemoMt5CommandPayload, utc_now_iso


class DemoCommandQueueStore:
    def __init__(self, data_dir: str | Path = "data", config: DemoCommandQueueConfig | None = None):
        self.data_dir = Path(data_dir)
        self.config = config or DemoCommandQueueConfig()
        self.queue_dir = self.data_dir / "demo_command_queue"
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.status_file = self.queue_dir / "status.json"
        self.previews_file = self.queue_dir / "previews.json"
        self.payloads_file = self.queue_dir / "payloads.json"
        self.history_file = self.queue_dir / "history.jsonl"
        for path in [self.previews_file, self.payloads_file]:
            if not path.exists():
                self._write_json_atomic(path, [])
        self.history_file.touch(exist_ok=True)
        if not self.status_file.exists():
            self._write_status()

    def _write_json_atomic(self, path: Path, value: Any) -> None:
        write_json_atomic(path, value)

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def load_previews(self) -> list[dict[str, Any]]:
        value = self._read_json(self.previews_file, [])
        return value if isinstance(value, list) else []

    def load_payloads(self) -> list[dict[str, Any]]:
        value = self._read_json(self.payloads_file, [])
        return value if isinstance(value, list) else []

    def history(self, limit: int = 100) -> list[dict[str, Any]]:
        items = []
        for line in self.history_file.read_text(encoding="utf-8").splitlines() if self.history_file.exists() else []:
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                items.append(item)
        return items[-max(int(limit), 1):]

    def add_preview(self, preview: DemoCommandPreview) -> dict[str, Any]:
        items = self.load_previews()
        items.append(preview.model_dump(mode="json"))
        self._write_json_atomic(self.previews_file, items[-self.config.history_limit :])
        self.add_audit("PREVIEW_CREATED", preview_id=preview.id, status=preview.status)
        self._write_status()
        return preview.model_dump(mode="json")

    def update_preview(self, preview: DemoCommandPreview) -> dict[str, Any]:
        items = self.load_previews()
        dumped = preview.model_dump(mode="json")
        for i, item in enumerate(items):
            if item.get("id") == preview.id:
                items[i] = dumped
                break
        else:
            items.append(dumped)
        self._write_json_atomic(self.previews_file, items[-self.config.history_limit :])
        self._write_status()
        return dumped

    def add_payload(self, payload: DemoMt5CommandPayload) -> dict[str, Any]:
        items = self.load_payloads()
        items.append(payload.model_dump(mode="json"))
        self._write_json_atomic(self.payloads_file, items[-self.config.history_limit :])
        self.add_audit("PAYLOAD_BUILT", preview_id=payload.preview_id, payload_id=payload.id, status=payload.status)
        self._write_status()
        return payload.model_dump(mode="json")

    def add_audit(self, action: str, preview_id: str | None = None, payload_id: str | None = None, status: str | None = None) -> None:
        if not self.config.write_history:
            return
        items = self.history(self.config.history_limit)
        items.append(DemoCommandAuditRecord(action=action, preview_id=preview_id, payload_id=payload_id, status=status).model_dump(mode="json"))
        write_text_atomic(self.history_file, "".join(json.dumps(item, default=str) + "\n" for item in items[-self.config.history_limit :]))

    def status(self) -> dict[str, Any]:
        return self._write_status()

    def _write_status(self) -> dict[str, Any]:
        previews = self.load_previews()
        payloads = self.load_payloads()
        status = DemoCommandQueueStatus(
            enabled=self.config.enabled,
            symbol=self.config.symbol,
            mode=self.config.mode,
            preview_count=len(previews),
            payload_count=len(payloads),
            latest_preview_status=previews[-1].get("status") if previews else None,
            latest_payload_status=payloads[-1].get("status") if payloads else None,
            demo_execution_allowed=False,
            live_execution_allowed=False,
            broker_order_created=False,
            mt5_commands_queued=False,
            updated_at=utc_now_iso(),
            safety=DemoCommandQueueSafety(),
        ).model_dump(mode="json")
        status["config"] = self.config.model_dump()
        status["paths"] = {"status": str(self.status_file), "previews": str(self.previews_file), "payloads": str(self.payloads_file), "history": str(self.history_file)}
        self._write_json_atomic(self.status_file, status)
        return status

    def reset(self) -> dict[str, Any]:
        self._write_json_atomic(self.previews_file, [])
        self._write_json_atomic(self.payloads_file, [])
        self.history_file.write_text("", encoding="utf-8")
        return self._write_status()
