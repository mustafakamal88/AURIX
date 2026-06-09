from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    data_dir = Path(os.getenv("AURIX_DATA_DIR", "data"))
    limit = int(os.getenv("AURIX_PAPER_RISK_DECISION_LIMIT", "20"))
    path = data_dir / "paper_risk_decisions.json"
    if not path.exists():
        print("No paper risk decisions.")
        return 0
    try:
        decisions = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAIL: could not parse {path}: {exc}")
        return 1
    if not isinstance(decisions, list) or not decisions:
        print("No paper risk decisions.")
        return 0
    for decision in [item for item in decisions if isinstance(item, dict)][-limit:]:
        print(
            " | ".join(
                [
                    f"created_at={decision.get('created_at')}",
                    f"decision_id={decision.get('id')}",
                    f"signal_id={decision.get('signal_id')}",
                    f"trade_id={decision.get('trade_id')}",
                    f"strategy={decision.get('strategy_name')}",
                    f"direction={decision.get('direction')}",
                    f"risk_status={decision.get('risk_status')}",
                    f"volume={decision.get('volume')}",
                ]
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
