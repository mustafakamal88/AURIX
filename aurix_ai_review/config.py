from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Union

import yaml
from pydantic import BaseModel


class AIReviewConfig(BaseModel):
    enabled: bool = True
    mode: Literal["LOCAL_TEMPLATE"] = "LOCAL_TEMPLATE"
    allow_external_llm: bool = False
    symbol: str = "XAUUSDm"
    include_journal: bool = True
    include_analytics: bool = True
    include_context: bool = True
    include_market_quality: bool = True
    max_journal_entries: int = 50
    max_signals: int = 50
    max_paper_trades: int = 50


def load_ai_review_config(path: Union[str, Path] = "config/ai_review.yaml") -> AIReviewConfig:
    config_path = Path(path)
    if not config_path.exists():
        return AIReviewConfig()
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return AIReviewConfig()
    return AIReviewConfig(**data)
