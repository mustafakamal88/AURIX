from __future__ import annotations

from datetime import datetime, time
from typing import Any, Optional
from zoneinfo import ZoneInfo

from .config import ContextConfig


def parse_snapshot_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed


def parse_hhmm(value: str) -> time:
    hour, minute = value.split(":", 1)
    return time(int(hour), int(minute))


def classify_session(snapshot_updated_at: Any, config: ContextConfig) -> tuple[str, bool, bool]:
    zone = ZoneInfo(config.timezone)
    dt = parse_snapshot_time(snapshot_updated_at) or datetime.now(zone)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=zone)
    local_time = dt.astimezone(zone).time()

    for name, window in config.sessions.items():
        start = parse_hhmm(window.start)
        end = parse_hhmm(window.end)
        if start <= local_time < end:
            return name, True, True

    return "CLOSED", False, False
