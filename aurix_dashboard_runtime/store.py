from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RuntimeDashboardStore:
    def __init__(self, data_dir: str | Path = "data"):
        self.data_dir = Path(data_dir)

    def read_json(self, relative_path: str, default: Any = None) -> Any:
        path = self.data_dir / relative_path
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def read_jsonl(self, relative_path: str, limit: int = 20) -> list[dict[str, Any]]:
        path = self.data_dir / relative_path
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                rows.append(item)
        return rows[-max(int(limit), 1):]

    def latest_snapshot(self) -> dict[str, Any] | None:
        value = self.read_json("latest_snapshot.json")
        return value if isinstance(value, dict) else None
