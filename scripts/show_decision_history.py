from __future__ import annotations

import argparse
import json
import os
import urllib.request
from dotenv import load_dotenv


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    load_dotenv()
    url = f"http://{os.getenv('AURIX_HOST', '127.0.0.1')}:{os.getenv('AURIX_PORT', '8765')}/decision-engine/history?limit={args.limit}"
    with urllib.request.urlopen(url, timeout=5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    for item in data.get("items") or []:
        print(f"{item.get('generated_at')} {item.get('action')} {item.get('direction')} {item.get('status')} {item.get('confidence')} {(item.get('score') or {}).get('total')} {item.get('strategy')} blocking_count={len(item.get('blocking_reasons') or [])} warning_count={len(item.get('warnings') or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
