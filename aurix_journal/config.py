from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import yaml
from pydantic import BaseModel


class JournalConfig(BaseModel):
    enabled: bool = True
    symbol: str = "XAUUSDm"
    review_paper_trades: bool = True
    review_signals: bool = True
    include_context: bool = True
    include_market_quality: bool = True
    max_entries: int = 1000


def load_journal_config(path: Union[str, Path] = "config/journal.yaml") -> JournalConfig:
    config_path = Path(path)
    if not config_path.exists():
        return JournalConfig()
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return JournalConfig()
    return JournalConfig(**data)
