from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import BacktestConfig
from .models import BacktestReport, BacktestTrade


class BacktestStore:
    def __init__(self, data_dir: str | Path = "data", config: BacktestConfig | None = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or BacktestConfig()
        self.report_file = self.data_dir / "backtest_report.json"
        self.trades_file = self.data_dir / "backtest_trades.json"
        self.source_candles_file = Path(self.config.source_candles_file)

    def status(self) -> dict[str, Any]:
        report = self.latest_report()
        trades = self.list_trades()
        return {
            "enabled": self.config.enabled,
            "symbol": self.config.symbol,
            "timeframe": self.config.timeframe,
            "source_candles_file": self.config.source_candles_file,
            "report_exists": self.report_file.exists(),
            "trades_count": len(trades),
            "latest": report.model_dump() if report else None,
            "config": self.config.model_dump(),
        }

    def load_candles(self) -> list[dict[str, Any]]:
        return self._read_list(self.source_candles_file)

    def save(self, report: BacktestReport, trades: list[BacktestTrade]) -> BacktestReport:
        self.report_file.write_text(json.dumps(report.model_dump(), indent=2, default=str), encoding="utf-8")
        self.trades_file.write_text(json.dumps([trade.model_dump() for trade in trades], indent=2, default=str), encoding="utf-8")
        return report

    def latest_report(self) -> BacktestReport | None:
        data = self._read_dict(self.report_file)
        return BacktestReport(**data) if data else None

    def list_trades(self) -> list[dict[str, Any]]:
        return self._read_list(self.trades_file)

    def reset(self) -> None:
        self.report_file.write_text("{}", encoding="utf-8")
        self.trades_file.write_text("[]", encoding="utf-8")

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
