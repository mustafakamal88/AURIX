from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import PaperRiskAuditConfig
from .models import PaperRiskDecision


SAFETY = {
    "paper_audit_only": True,
    "live_execution_allowed": False,
    "live_arming_allowed": False,
    "command_queueing_allowed": False,
    "mt5_commands_queued": False,
    "broker_order_created": False,
    "ea_settings_modified": False,
    "external_llm_used": False,
    "strategy_config_mutated": False,
}


class PaperRiskAuditStore:
    def __init__(self, data_dir: str | Path = "data", config: PaperRiskAuditConfig | None = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or PaperRiskAuditConfig()
        self.decisions_file = self.data_dir / "paper_risk_decisions.json"
        self.history_file = self.data_dir / "paper_risk_decisions_history.jsonl"
        if not self.decisions_file.exists():
            self.decisions_file.write_text("[]", encoding="utf-8")

    def status(self) -> dict[str, Any]:
        decisions = self.list_decisions()
        latest = decisions[-1] if decisions else None
        return {
            "enabled": self.config.enabled,
            "symbol": self.config.symbol,
            "mode": self.config.mode,
            "latest_exists": latest is not None,
            "decision_count": len(decisions),
            "latest": latest,
            "history_exists": self.history_file.exists() and bool(self.history_file.read_text(encoding="utf-8").strip()),
            "config": self.config.model_dump(),
            "safety": SAFETY.copy(),
        }

    def list_decisions(self) -> list[dict[str, Any]]:
        return self._read_list(self.decisions_file)

    def latest(self) -> dict[str, Any] | None:
        decisions = self.list_decisions()
        return decisions[-1] if decisions else None

    def add_decision(self, decision: PaperRiskDecision | dict[str, Any]) -> dict[str, Any]:
        data = decision.model_dump() if isinstance(decision, PaperRiskDecision) else PaperRiskDecision(**decision).model_dump()
        decisions = [item for item in self.list_decisions() if item.get("id") != data.get("id")]
        decisions.append(data)
        self.decisions_file.write_text(json.dumps(decisions, indent=2, default=str), encoding="utf-8")
        if self.config.write_history:
            self.append_history(data)
        return data

    def append_history(self, decision: dict[str, Any]) -> None:
        items = self.history()
        items.append(
            {
                "created_at": decision.get("created_at"),
                "decision_id": decision.get("id"),
                "signal_id": decision.get("signal_id"),
                "trade_id": decision.get("trade_id"),
                "strategy": decision.get("strategy_name"),
                "direction": decision.get("direction"),
                "risk_status": decision.get("risk_status"),
                "volume": decision.get("volume"),
            }
        )
        items = items[-max(int(self.config.history_limit or 1), 1):]
        self.history_file.write_text("".join(json.dumps(item, default=str) + "\n" for item in items), encoding="utf-8")

    def history(self, limit: int | None = None) -> list[dict[str, Any]]:
        if not self.history_file.exists():
            return []
        items: list[dict[str, Any]] = []
        for line in self.history_file.read_text(encoding="utf-8").splitlines():
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                items.append(data)
        return items[-limit:] if limit else items

    def reset(self) -> None:
        self.decisions_file.write_text("[]", encoding="utf-8")
        self.history_file.write_text("", encoding="utf-8")

    def _read_list(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []
