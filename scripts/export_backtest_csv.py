from __future__ import annotations

import csv
import json
from pathlib import Path


def main() -> int:
    source = Path("data/backtest_trades.json")
    output = Path("data/exports/backtest_trades.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        output.write_text("", encoding="utf-8")
        print(f"exported: {output} rows=0")
        return 0
    try:
        trades = json.loads(source.read_text(encoding="utf-8"))
    except Exception:
        trades = []
    trades = [trade for trade in trades if isinstance(trade, dict)] if isinstance(trades, list) else []
    fields = [
        "id",
        "symbol",
        "direction",
        "entry_time",
        "entry_price",
        "stop_loss",
        "take_profit",
        "exit_time",
        "exit_price",
        "status",
        "pnl_points",
        "r_multiple",
        "setup_name",
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for trade in trades:
            writer.writerow({field: trade.get(field) for field in fields})
    print(f"exported: {output} rows={len(trades)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
