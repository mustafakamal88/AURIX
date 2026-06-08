from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from .models import PaperTrade


class PaperLedger:
    def __init__(self, data_dir: str | Path = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.trades_file = self.data_dir / "paper_trades.json"
        if not self.trades_file.exists():
            self.trades_file.write_text("[]", encoding="utf-8")

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _write_json(self, path: Path, value: Any) -> None:
        path.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")

    def list_trades(self) -> list[dict[str, Any]]:
        return self._read_json(self.trades_file, [])

    def list_open_trades(self) -> list[dict[str, Any]]:
        return [trade for trade in self.list_trades() if trade.get("status") == "OPEN"]

    def add_trade(self, trade: PaperTrade) -> PaperTrade:
        trades = self.list_trades()
        trades.append(trade.model_dump())
        self._write_json(self.trades_file, trades)
        return trade

    def save_trades(self, trades: list[dict[str, Any]]) -> None:
        self._write_json(self.trades_file, trades)

    def get_trade(self, trade_id: str) -> Optional[dict[str, Any]]:
        for trade in self.list_trades():
            if trade.get("id") == trade_id:
                return trade
        return None

    def reset(self) -> None:
        self._write_json(self.trades_file, [])
