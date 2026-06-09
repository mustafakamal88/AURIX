from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import DecisionEngineConfig
from .models import AurixDecisionReport, AurixDecisionSafety, utc_now_iso


class DecisionEngineStore:
    def __init__(self, data_dir: str | Path = "data", config: DecisionEngineConfig | None = None):
        self.data_dir = Path(data_dir)
        self.config = config or DecisionEngineConfig()
        self.engine_dir = self.data_dir / "decision_engine"
        self.engine_dir.mkdir(parents=True, exist_ok=True)
        self.report_file = self.engine_dir / "report.json"
        self.status_file = self.engine_dir / "status.json"
        self.history_file = self.engine_dir / "history.jsonl"
        self.history_file.touch(exist_ok=True)
        if not self.status_file.exists():
            self._write_status(None)

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

    def latest(self) -> dict[str, Any] | None:
        value = self._read_json(self.report_file, None)
        return value if isinstance(value, dict) else None

    def history(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = []
        for line in self.history_file.read_text(encoding="utf-8").splitlines() if self.history_file.exists() else []:
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                rows.append(item)
        return rows[-max(int(limit), 1):]

    def add_report(self, report: AurixDecisionReport) -> dict[str, Any]:
        dumped = report.model_dump(mode="json")
        self._write_json_atomic(self.report_file, dumped)
        if self.config.write_history:
            rows = self.history(self.config.history_limit)
            rows.append(dumped)
            rows = rows[-max(int(self.config.history_limit), 1):]
            tmp = self.history_file.with_suffix(".jsonl.tmp")
            tmp.write_text("".join(json.dumps(item, default=str) + "\n" for item in rows), encoding="utf-8")
            tmp.replace(self.history_file)
        self._write_status(dumped)
        return dumped

    def status(self) -> dict[str, Any]:
        return self._write_status(self.latest())

    def _write_status(self, latest: dict[str, Any] | None) -> dict[str, Any]:
        status = {
            "enabled": self.config.enabled,
            "symbol": self.config.symbol,
            "mode": self.config.mode,
            "autonomy_level": self.config.autonomy_level,
            "latest_exists": latest is not None,
            "latest_action": latest.get("action") if latest else None,
            "latest_direction": latest.get("direction") if latest else None,
            "latest_status": latest.get("status") if latest else None,
            "confidence": latest.get("confidence") if latest else 0.0,
            "score": (latest.get("score") or {}).get("total") if latest else 0.0,
            "strategy": latest.get("strategy") if latest else None,
            "setup_reason": latest.get("setup_reason") if latest else None,
            "blocking_reason_count": len(latest.get("blocking_reasons") or []) if latest else 0,
            "warning_count": len(latest.get("warnings") or []) if latest else 0,
            "top_blocking_reason": ((latest.get("blocking_reasons") or [{}])[0].get("message") if latest else None),
            "top_warning": ((latest.get("warnings") or [None])[0] if latest else None),
            "demo_execution_allowed": False,
            "live_execution_allowed": False,
            "command_queueing_allowed": False,
            "mt5_commands_queued": False,
            "broker_order_created": False,
            "updated_at": utc_now_iso(),
            "safety": AurixDecisionSafety().model_dump(),
            "config": self.config.model_dump(),
        }
        self._write_json_atomic(self.status_file, status)
        return status

    def reset(self) -> dict[str, Any]:
        if self.report_file.exists():
            self.report_file.unlink()
        self.history_file.write_text("", encoding="utf-8")
        return self._write_status(None)
