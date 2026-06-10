from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_persistence.durable_audit import DurableAuditError, DurableAuditStore


EXPECTED_TABLES = [
    "aurix_events",
    "strategy_evaluations",
    "decision_records",
    "trade_explanations",
    "command_audit",
    "broker_trade_results",
]


def _scheme(database_url: str | None) -> str:
    if not database_url:
        return "unknown"
    parsed = urlparse(database_url)
    return parsed.scheme if parsed.scheme in {"postgres", "postgresql"} else "unknown"


def _redact(value: Any, database_url: str | None) -> str:
    text = str(value)
    if database_url:
        text = text.replace(database_url, "[DATABASE_URL_REDACTED]")
        parsed = urlparse(database_url)
        if parsed.password:
            text = text.replace(parsed.password, "[PASSWORD_REDACTED]")
        if parsed.netloc:
            text = text.replace(parsed.netloc, "[HOST_REDACTED]")
    return text


def _query_one(store: DurableAuditStore, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    return store._query_one(sql, params)  # Existing read-only helper keeps connection handling centralized.


def _table_status(store: DurableAuditStore) -> tuple[list[str], list[str]]:
    placeholders = ",".join(["%s"] * len(EXPECTED_TABLES))
    row = _query_one(
        store,
        f"""
        select coalesce(array_agg(table_name), ARRAY[]::text[]) as tables
        from information_schema.tables
        where table_schema = 'public'
          and table_name in ({placeholders})
        """,
        tuple(EXPECTED_TABLES),
    )
    raw_tables = row.get("tables") if row else []
    found = sorted(str(item) for item in (raw_tables or []))
    missing = sorted(set(EXPECTED_TABLES) - set(found))
    return found, missing


def _last_write(store: DurableAuditStore) -> str | None:
    candidates = []
    for table in EXPECTED_TABLES:
        try:
            row = _query_one(store, f"select max(created_at) as last_write from {table}", ())
        except DurableAuditError:
            continue
        value = row.get("last_write") if row else None
        if value:
            candidates.append(str(value))
    return max(candidates) if candidates else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Railway durable audit DB/schema readiness without printing secrets.")
    parser.add_argument("--require-db", action="store_true", help="Fail when DATABASE_URL is missing.")
    parser.add_argument("--data-dir", default=os.getenv("AURIX_DATA_DIR", "data"))
    args = parser.parse_args()

    database_url = os.getenv("DATABASE_URL")
    present = bool(database_url)
    scheme = _scheme(database_url)
    result: dict[str, Any] = {
        "DATABASE_URL present": present,
        "scheme": scheme,
        "connection ok": False,
        "schema ready": False,
        "tables found": [],
        "tables missing": EXPECTED_TABLES,
        "last write timestamp": None,
        "last error redacted": None,
    }

    if not database_url:
        result["last error redacted"] = "DATABASE_URL missing; local JSON cache only"
        for key, value in result.items():
            print(f"{key}: {value}")
        if args.require_db:
            return 1
        print("local-only warning: DATABASE_URL is missing; durable Railway audit was not checked")
        return 0

    if scheme == "unknown":
        result["last error redacted"] = "DATABASE_URL scheme is not postgres/postgresql"
        for key, value in result.items():
            print(f"{key}: {value}")
        return 1

    try:
        store = DurableAuditStore(args.data_dir, database_url=database_url)
        store.init_schema()
        result["connection ok"] = True
        found, missing = _table_status(store)
        result["tables found"] = found
        result["tables missing"] = missing
        result["schema ready"] = not missing
        result["last write timestamp"] = _last_write(store)
    except Exception as exc:
        result["last error redacted"] = _redact(exc, database_url)

    for key, value in result.items():
        print(f"{key}: {value}")
    return 0 if result["connection ok"] and result["schema ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
