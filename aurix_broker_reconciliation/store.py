from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aurix_common import write_json_atomic, write_text_atomic

from .config import BrokerReconciliationConfig
from .models import BrokerReconciliationReport, BrokerReconciliationSafety, utc_now_iso


class BrokerReconciliationStore:
    def __init__(self, data_dir: str | Path = "data", config: BrokerReconciliationConfig | None = None):
        self.data_dir = Path(data_dir)
        self.config = config or BrokerReconciliationConfig()
        self.reconciliation_dir = self.data_dir / "broker_reconciliation"
        self.reconciliation_dir.mkdir(parents=True, exist_ok=True)
        self.report_file = self.reconciliation_dir / "report.json"
        self.history_file = self.reconciliation_dir / "history.jsonl"
        self.status_file = self.reconciliation_dir / "status.json"
        self.history_file.touch(exist_ok=True)
        if not self.status_file.exists():
            self._write_status(None)

    def _write_json_atomic(self, path: Path, value: Any) -> None:
        write_json_atomic(path, value)

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def latest(self) -> dict[str, Any] | None:
        value = self._read_json(self.report_file, None)
        return value if isinstance(value, dict) else None

    def history(self, limit: int = 100) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if self.history_file.exists():
            for line in self.history_file.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                if isinstance(item, dict):
                    items.append(item)
        return items[-max(int(limit), 1):]

    def add_report(self, report: BrokerReconciliationReport) -> dict[str, Any]:
        dumped = report.model_dump(mode="json")
        self._write_json_atomic(self.report_file, dumped)
        if self.config.write_history:
            items = self.history(self.config.history_limit)
            items.append(dumped)
            items = items[-max(int(self.config.history_limit or 1), 1):]
            write_text_atomic(self.history_file, "".join(json.dumps(item, default=str) + "\n" for item in items))
        self._write_status(dumped)
        return dumped

    def status(self) -> dict[str, Any]:
        return self._write_status(self.latest())

    def _write_status(self, latest: dict[str, Any] | None) -> dict[str, Any]:
        expected = latest.get("aurix_expected_state") if latest else {}
        status = {
            "enabled": self.config.enabled,
            "symbol": self.config.symbol,
            "mode": self.config.mode,
            "latest_exists": latest is not None,
            "status": latest.get("status") if latest else None,
            "broker_position_count": len(latest.get("broker_positions") or []) if latest else 0,
            "broker_order_count": len(latest.get("broker_orders") or []) if latest else 0,
            "mismatch_count": len(latest.get("mismatches") or []) if latest else 0,
            "warning_count": len(latest.get("warnings") or []) if latest else 0,
            "order_requests_with_broker_order_id": expected.get("order_requests_with_broker_order_id") if isinstance(expected, dict) else 0,
            "live_execution_allowed": False,
            "command_queueing_allowed": False,
            "broker_order_created": False,
            "broker_order_modified": False,
            "broker_order_closed": False,
            "mt5_commands_queued": False,
            "paper_trade_created": False,
            "updated_at": utc_now_iso(),
            "paths": {
                "report": str(self.report_file),
                "history": str(self.history_file),
                "status": str(self.status_file),
            },
            "config": self.config.model_dump(),
            "safety": BrokerReconciliationSafety().model_dump(),
        }
        self._write_json_atomic(self.status_file, status)
        return status

    def reset(self) -> dict[str, Any]:
        if self.report_file.exists():
            self.report_file.unlink()
        self.history_file.write_text("", encoding="utf-8")
        return self._write_status(None)
