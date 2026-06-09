from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv


def post_json(url: str) -> dict:
    req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def describe_result(label: str, result: dict | None) -> None:
    if not result:
        print(f"{label}: none")
        return
    print(
        f"{label}: expectancy_r={result.get('expectancy_r')} "
        f"total_r={result.get('total_r')} "
        f"profit_factor={result.get('profit_factor')} "
        f"trades={result.get('trades')} "
        f"params={result.get('params')}"
    )


def main() -> int:
    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    url = f"http://{host}:{port}/research/run-sweep"
    try:
        run = post_json(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not run parameter sweep at {url}: {exc}")
        return 1
    print("AURIX Research Parameter Sweep")
    print(f"candles_used: {run.get('candles_used')}")
    print(f"total_variants: {run.get('total_variants')}")
    describe_result("best_by_total_r", run.get("best_by_total_r"))
    describe_result("best_by_expectancy", run.get("best_by_expectancy"))
    describe_result("best_by_profit_factor", run.get("best_by_profit_factor"))
    warnings = list(run.get("warnings") or [])
    for result in run.get("results") or []:
        warnings.extend(result.get("warnings") or [])
    print(f"warnings: {'; '.join(str(warning) for warning in warnings) if warnings else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
