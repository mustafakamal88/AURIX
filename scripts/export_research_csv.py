from __future__ import annotations

import csv
import json
from pathlib import Path


def main() -> int:
    source = Path("data/research_parameter_sweep.json")
    output = Path("data/exports/research_parameter_sweep.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        run = json.loads(source.read_text(encoding="utf-8")) if source.exists() else {}
    except Exception:
        run = {}
    results = run.get("results") if isinstance(run, dict) else []
    results = [result for result in results if isinstance(result, dict)] if isinstance(results, list) else []
    fields = [
        "id",
        "stop_points",
        "take_profit_points",
        "lookback_range_candles",
        "max_spread_points",
        "candles_used",
        "trades",
        "wins",
        "losses",
        "win_rate",
        "total_r",
        "expectancy_r",
        "profit_factor",
        "max_consecutive_losses",
        "warnings",
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            params = result.get("params") or {}
            writer.writerow(
                {
                    "id": result.get("id"),
                    "stop_points": params.get("stop_points"),
                    "take_profit_points": params.get("take_profit_points"),
                    "lookback_range_candles": params.get("lookback_range_candles"),
                    "max_spread_points": params.get("max_spread_points"),
                    "candles_used": result.get("candles_used"),
                    "trades": result.get("trades"),
                    "wins": result.get("wins"),
                    "losses": result.get("losses"),
                    "win_rate": result.get("win_rate"),
                    "total_r": result.get("total_r"),
                    "expectancy_r": result.get("expectancy_r"),
                    "profit_factor": result.get("profit_factor"),
                    "max_consecutive_losses": result.get("max_consecutive_losses"),
                    "warnings": "; ".join(str(warning) for warning in result.get("warnings") or []),
                }
            )
    print(f"exported: {output} rows={len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
