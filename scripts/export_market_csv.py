from __future__ import annotations

import csv
import json
from pathlib import Path


def read_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = sorted({key for row in rows for key in row.keys()})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    data_dir = Path("data")
    export_dir = data_dir / "exports"
    tick_rows = read_json(data_dir / "market_ticks.json")
    candle_rows = read_json(data_dir / "market_candles_m1.json")
    ticks_path = export_dir / "market_ticks.csv"
    candles_path = export_dir / "market_candles_m1.csv"
    write_csv(ticks_path, tick_rows)
    write_csv(candles_path, candle_rows)
    print(f"exported {len(tick_rows)} ticks to {ticks_path}")
    print(f"exported {len(candle_rows)} candles to {candles_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
