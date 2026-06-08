from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import PaperPerformanceReport


class PaperPerformanceStore:
    def __init__(self, data_dir: str | Path = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.trades_file = self.data_dir / "paper_trades.json"
        self.signals_file = self.data_dir / "strategy_signals.json"
        self.context_file = self.data_dir / "context_snapshots.json"
        self.market_quality_file = self.data_dir / "market_quality.json"
        self.report_file = self.data_dir / "paper_performance_report.json"

    def read_inputs(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        return (
            self._read_list(self.trades_file),
            self._read_list(self.signals_file),
            self._read_list(self.context_file),
            self._read_dict(self.market_quality_file),
        )

    def latest(self) -> PaperPerformanceReport:
        data = self._read_dict(self.report_file)
        if data:
            return PaperPerformanceReport(**data)
        return PaperPerformanceReport(warnings=["paper performance report has not been generated yet"])

    def save(self, report: PaperPerformanceReport) -> PaperPerformanceReport:
        self.report_file.write_text(json.dumps(report.model_dump(), indent=2, default=str), encoding="utf-8")
        return report

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
