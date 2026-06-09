from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


load_dotenv()
BASE_URL = os.getenv("AURIX_BASE_URL") or f"http://{os.getenv('AURIX_HOST', '127.0.0.1')}:{os.getenv('AURIX_PORT', '8765')}"


def main() -> int:
    request = Request(f"{BASE_URL}/evidence-integrity/status", method="GET")
    try:
        with urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot load evidence integrity from {BASE_URL}: {exc}", file=sys.stderr)
        return 1

    print(f"status: {data.get('status')}")
    print(f"paper_ledger: {(data.get('paper_ledger') or {}).get('status')}")
    print(f"journal_ledger: {(data.get('journal_ledger') or {}).get('status')}")
    print(f"evidence_monitor: {(data.get('evidence_monitor') or {}).get('status')}")
    print(f"live_readiness: {(data.get('live_readiness') or {}).get('status')}")
    print(f"signal_certification: {(data.get('signal_certification') or {}).get('status')}")
    print(f"stale_temp_file_count: {data.get('stale_temp_file_count')}")
    print(f"corrupt_json_file_count: {data.get('corrupt_json_file_count')}")
    print(f"notes: {'; '.join(data.get('notes') or [])}")
    if data.get("status") == "ERROR" or data.get("corrupt_json_file_count"):
        print("ERROR: evidence integrity failed.", file=sys.stderr)
        return 1
    print("OK: evidence integrity check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
