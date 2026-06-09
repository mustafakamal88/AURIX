from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    data_dir = Path(os.getenv("AURIX_DATA_DIR", "data"))
    limit = int(os.getenv("AURIX_EVIDENCE_GROWTH_HISTORY_LIMIT", "20"))
    history_file = data_dir / "evidence_growth_history.jsonl"
    if not history_file.exists():
        print("No evidence growth history.")
        return 0
    entries = []
    for line in history_file.read_text(encoding="utf-8").splitlines():
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            entries.append(data)
    for entry in entries[-limit:]:
        print(
            " | ".join(
                [
                    f"generated_at={entry.get('generated_at')}",
                    f"status={entry.get('status')}",
                    f"overall_progress={entry.get('overall_progress')}",
                    f"closed={entry.get('closed_paper_trades')}",
                    f"candles={entry.get('recorded_candles')}",
                    f"days={entry.get('forward_tested_days')}",
                ]
            )
        )
    if not entries:
        print("No evidence growth history.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
