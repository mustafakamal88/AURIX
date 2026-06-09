from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aurix_common import write_json_atomic, write_text_atomic

from .config import DemoOmsConfig
from .models import DemoOmsSafety, DemoOmsStatus, OmsAuditRecord, OmsOrderIntent, OmsOrderRequest, utc_now_iso


class DemoOmsStore:
    def __init__(self, data_dir: str | Path = "data", config: DemoOmsConfig | None = None):
        self.data_dir = Path(data_dir)
        self.config = config or DemoOmsConfig()
        self.oms_dir = self.data_dir / "demo_oms"
        self.oms_dir.mkdir(parents=True, exist_ok=True)
        self.status_file = self.oms_dir / "status.json"
        self.intents_file = self.oms_dir / "order_intents.json"
        self.requests_file = self.oms_dir / "order_requests.json"
        self.history_file = self.oms_dir / "history.jsonl"
        if not self.intents_file.exists():
            self._write_json_atomic(self.intents_file, [])
        if not self.requests_file.exists():
            self._write_json_atomic(self.requests_file, [])
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

    def load_order_intents(self) -> list[dict[str, Any]]:
        value = self._read_json(self.intents_file, [])
        return value if isinstance(value, list) else []

    def load_order_requests(self) -> list[dict[str, Any]]:
        value = self._read_json(self.requests_file, [])
        return value if isinstance(value, list) else []

    def history(self, limit: int = 100) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for line in self.history_file.read_text(encoding="utf-8").splitlines() if self.history_file.exists() else []:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                items.append(item)
        return items[-max(int(limit), 1):]

    def add_intent(self, intent: OmsOrderIntent) -> dict[str, Any]:
        items = self.load_order_intents()
        items.append(intent.model_dump(mode="json"))
        items = items[-max(int(self.config.history_limit or 1), 1):]
        self._write_json_atomic(self.intents_file, items)
        self.add_audit("ORDER_INTENT_CREATED", intent_id=intent.id, status=intent.status.value)
        self._write_status()
        return intent.model_dump(mode="json")

    def update_intent(self, intent: OmsOrderIntent) -> dict[str, Any]:
        items = self.load_order_intents()
        dumped = intent.model_dump(mode="json")
        replaced = False
        for index, item in enumerate(items):
            if item.get("id") == intent.id:
                items[index] = dumped
                replaced = True
                break
        if not replaced:
            items.append(dumped)
        self._write_json_atomic(self.intents_file, items[-max(int(self.config.history_limit or 1), 1):])
        self._write_status()
        return dumped

    def add_request(self, request: OmsOrderRequest) -> dict[str, Any]:
        items = self.load_order_requests()
        items.append(request.model_dump(mode="json"))
        items = items[-max(int(self.config.history_limit or 1), 1):]
        self._write_json_atomic(self.requests_file, items)
        self.add_audit("ORDER_REQUEST_DRY_RUN", intent_id=request.intent_id, request_id=request.id, status=request.status)
        self._write_status()
        return request.model_dump(mode="json")

    def add_audit(self, action: str, intent_id: str | None = None, request_id: str | None = None, status: str | None = None, detail: dict[str, Any] | None = None) -> None:
        if not self.config.write_history:
            return
        record = OmsAuditRecord(action=action, intent_id=intent_id, request_id=request_id, status=status, detail=detail or {})
        items = self.history(self.config.history_limit)
        items.append(record.model_dump(mode="json"))
        items = items[-max(int(self.config.history_limit or 1), 1):]
        write_text_atomic(self.history_file, "".join(json.dumps(item, default=str) + "\n" for item in items))

    def status(self) -> dict[str, Any]:
        return self._write_status()

    def _write_status(self) -> dict[str, Any]:
        intents = self.load_order_intents()
        requests = self.load_order_requests()
        status = DemoOmsStatus(
            enabled=self.config.enabled,
            symbol=self.config.symbol,
            mode=self.config.mode,
            order_intent_count=len(intents),
            order_request_count=len(requests),
            latest_intent_status=intents[-1].get("status") if intents else None,
            latest_request_status=requests[-1].get("status") if requests else None,
            demo_execution_allowed=False,
            live_execution_allowed=False,
            command_queueing_allowed=False,
            demo_command_queueing_allowed=False,
            broker_order_created=False,
            mt5_commands_queued=False,
            paper_trade_created=False,
            updated_at=utc_now_iso(),
            safety=DemoOmsSafety(),
        ).model_dump(mode="json")
        status["config"] = self.config.model_dump()
        status["paths"] = {
            "status": str(self.status_file),
            "order_intents": str(self.intents_file),
            "order_requests": str(self.requests_file),
            "history": str(self.history_file),
        }
        self._write_json_atomic(self.status_file, status)
        return status

    def reset(self) -> dict[str, Any]:
        self._write_json_atomic(self.intents_file, [])
        self._write_json_atomic(self.requests_file, [])
        self.history_file.write_text("", encoding="utf-8")
        return self._write_status()
