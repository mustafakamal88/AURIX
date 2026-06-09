from __future__ import annotations

from typing import Any


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def latest(items: list[dict[str, Any]]) -> dict[str, Any]:
    return items[-1] if items else {}


def find_by_id(items: list[dict[str, Any]], item_id: Any) -> dict[str, Any]:
    for item in items:
        if item.get("id") == item_id:
            return item
    return {}


def find_key(value: Any, names: set[str]) -> Any:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).replace("_", "").lower() in names:
                return item
        for item in value.values():
            found = find_key(item, names)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = find_key(item, names)
            if found is not None:
                return found
    return None
