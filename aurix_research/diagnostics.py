from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import ResearchConfig
from .models import ResearchRun
from .parameter_sweep import ParameterSweepEngine, load_recorded_candles


class ResearchStore:
    def __init__(self, data_dir: str | Path = "data", config: ResearchConfig | None = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or ResearchConfig()
        self.research_file = self.data_dir / "research_parameter_sweep.json"
        self.source_candles_file = Path(self.config.source_candles_file)

    def status(self) -> dict[str, Any]:
        latest = self.latest()
        warning_count = len(latest.warnings) if latest else 0
        if latest:
            warning_count += sum(len(result.warnings) for result in latest.results)
        return {
            "enabled": self.config.enabled,
            "symbol": self.config.symbol,
            "source_candles_file": self.config.source_candles_file,
            "latest_exists": self.research_file.exists(),
            "warning_count": warning_count,
            "latest": latest.model_dump() if latest else None,
            "config": self.config.model_dump(),
            "safety": {
                "research_only": True,
                "no_mt5_execution": True,
                "commands_queued": False,
                "config_mutated": False,
                "external_llm_used": False,
            },
        }

    def load_candles(self) -> list[dict[str, Any]]:
        return load_recorded_candles(self.source_candles_file)

    def run_sweep(self) -> ResearchRun:
        run = ParameterSweepEngine(self.config).run(self.load_candles())
        self.save(run)
        return run

    def save(self, run: ResearchRun) -> ResearchRun:
        self.research_file.write_text(json.dumps(run.model_dump(), indent=2, default=str), encoding="utf-8")
        return run

    def latest(self) -> ResearchRun | None:
        data = self._read_dict(self.research_file)
        return ResearchRun(**data) if data else None

    def reset(self) -> None:
        self.research_file.write_text("{}", encoding="utf-8")

    def _read_dict(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}
