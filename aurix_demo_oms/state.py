from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def today_utc_prefix() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def count_today_requests(requests: list[dict[str, Any]]) -> int:
    today = today_utc_prefix()
    return sum(1 for item in requests if str(item.get("created_at") or "").startswith(today))


def count_open_oms_orders(requests: list[dict[str, Any]], symbol: str | None = None) -> int:
    active = {"READY_FOR_BROKER_EXECUTION"}
    count = 0
    for item in requests:
        if symbol and item.get("symbol") != symbol:
            continue
        if item.get("status") in active:
            count += 1
    return count
