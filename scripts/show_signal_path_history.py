from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    data_dir = Path(os.getenv("AURIX_DATA_DIR", "data"))
    limit = int(os.getenv("AURIX_SIGNAL_PATH_HISTORY_LIMIT", "20"))
    path = data_dir / "signal_path_certification_history.jsonl"
    if not path.exists():
        print("No signal path certification history.")
        return 0
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            entries.append(data)
    for entry in entries[-limit:]:
        print(" | ".join([
            f"generated_at={entry.get('generated_at')}",
            f"status={entry.get('status')}",
            f"trade_id={entry.get('trade_id')}",
            f"signal_id={entry.get('signal_id')}",
            f"strategy={entry.get('strategy')}",
            f"direction={entry.get('direction')}",
            f"trade_status={entry.get('trade_status')}",
            f"warnings={entry.get('warning_count')}",
            f"failed={entry.get('failed_count')}",
        ]))
    if not entries:
        print("No signal path certification history.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
