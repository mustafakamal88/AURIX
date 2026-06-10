from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aurix_common.persistence import write_json_atomic

from .models import QuickValidationReport


class QuickValidationStore:
    def __init__(self, data_dir: str | Path = "data"):
        self.data_dir = Path(data_dir)
        self.path = self.data_dir / "quick_validation_report.json"

    def latest(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    def save(self, report: QuickValidationReport) -> QuickValidationReport:
        write_json_atomic(self.path, report.model_dump(mode="json"))
        return report

    def reset(self) -> None:
        if self.path.exists():
            self.path.unlink()
