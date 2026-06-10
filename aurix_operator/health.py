from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def age_seconds(value: Any) -> Optional[float]:
    parsed = parse_time(value)
    if parsed is None:
        return None
    return (datetime.now(timezone.utc) - parsed).total_seconds()


def read_ea_broker_execution(snapshot: Optional[dict[str, Any]]) -> Optional[bool]:
    raw = as_dict(snapshot.get("raw")) if snapshot else {}
    value = raw.get("broker_execution_enabled")
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return None
