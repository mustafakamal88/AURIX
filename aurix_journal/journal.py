from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import JournalConfig
from .models import JournalEntry


class JournalStore:
    def __init__(self, data_dir: str | Path = "data", config: JournalConfig | None = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or JournalConfig()
        self.entries_file = self.data_dir / "journal_entries.json"
        self.paper_trades_file = self.data_dir / "paper_trades.json"
        self.strategy_signals_file = self.data_dir / "strategy_signals.json"
        self.context_snapshots_file = self.data_dir / "context_snapshots.json"
        self.market_quality_file = self.data_dir / "market_quality.json"
        self.analytics_report_file = self.data_dir / "paper_performance_report.json"
        if not self.entries_file.exists():
            self.entries_file.write_text("[]", encoding="utf-8")

    def status(self) -> dict[str, Any]:
        entries = self.list_entries()
        latest = entries[-1] if entries else None
        return {
            "enabled": self.config.enabled,
            "symbol": self.config.symbol,
            "entries_count": len(entries),
            "latest_classification": latest.get("classification") if latest else None,
            "latest_entry": latest,
            "config": self.config.model_dump(),
        }

    def list_entries(self) -> list[dict[str, Any]]:
        return self._read_list(self.entries_file)

    def save_entries(self, entries: list[dict[str, Any]]) -> None:
        capped = entries[-self.config.max_entries :]
        self.entries_file.write_text(json.dumps(capped, indent=2, default=str), encoding="utf-8")

    def upsert_entries(self, new_entries: list[JournalEntry]) -> list[dict[str, Any]]:
        existing = self.list_entries()
        by_key = {(entry.get("entry_type"), entry.get("source_id")): entry for entry in existing}
        order = [(entry.get("entry_type"), entry.get("source_id")) for entry in existing]

        for entry in new_entries:
            dumped = entry.model_dump()
            key = (dumped.get("entry_type"), dumped.get("source_id"))
            if key not in by_key:
                order.append(key)
            else:
                dumped["id"] = by_key[key].get("id") or dumped["id"]
                dumped["created_at"] = by_key[key].get("created_at") or dumped["created_at"]
            by_key[key] = dumped

        saved = [by_key[key] for key in order if key in by_key]
        self.save_entries(saved)
        return [entry.model_dump() for entry in new_entries]

    def add_entry(self, entry: JournalEntry) -> dict[str, Any]:
        entries = self.list_entries()
        entries.append(entry.model_dump())
        self.save_entries(entries)
        return entry.model_dump()

    def reset(self) -> None:
        self.save_entries([])

    def read_inputs(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
        return (
            self._read_list(self.paper_trades_file),
            self._read_list(self.strategy_signals_file),
            self._read_list(self.context_snapshots_file),
            self._read_dict(self.market_quality_file),
            self._read_dict(self.analytics_report_file),
        )

    def _read_list(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []

    def _read_dict(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}
