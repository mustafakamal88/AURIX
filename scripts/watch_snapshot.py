from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def value(data: dict[str, Any], key: str, default: Any = "n/a") -> Any:
    item = data.get(key)
    return default if item is None else item


def main() -> int:
    load_dotenv()
    data_dir = Path(os.getenv("AURIX_DATA_DIR", "data"))
    path = data_dir / "latest_snapshot.json"
    last_mtime = 0.0

    print(f"Watching {path}. Press Ctrl+C to stop.")

    while True:
        if not path.exists():
            print("No snapshot yet. Start the server, allow MT5 WebRequest, and attach the EA to XAUUSDm.")
            time.sleep(2)
            continue

        mtime = path.stat().st_mtime
        if mtime == last_mtime:
            time.sleep(1)
            continue

        last_mtime = mtime
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"Snapshot file is not valid JSON yet: {exc}")
            time.sleep(1)
            continue

        if not isinstance(snapshot, dict):
            print("Snapshot file JSON is not an object yet.")
            time.sleep(1)
            continue

        account = as_dict(snapshot.get("account"))
        tick = as_dict(snapshot.get("tick"))
        positions = as_list(snapshot.get("positions"))

        print(
            " | ".join(
                [
                    f"updated={value(snapshot, 'received_at')}",
                    f"equity={value(account, 'equity')}",
                    f"balance={value(account, 'balance')}",
                    f"symbol={value(tick, 'symbol')}",
                    f"bid={value(tick, 'bid')}",
                    f"ask={value(tick, 'ask')}",
                    f"spread_points={value(tick, 'spread_points')}",
                    f"positions={len(positions)}",
                ]
            )
        )


if __name__ == "__main__":
    raise SystemExit(main())
