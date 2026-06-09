from __future__ import annotations

import json
import os
import urllib.request
from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    url = f"http://{os.getenv('AURIX_HOST', '127.0.0.1')}:{os.getenv('AURIX_PORT', '8765')}/demo-command-queue/preview-latest"
    req = urllib.request.Request(url, data=b"{}", method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    preview = data.get("preview") or {}
    validation = data.get("validation") or {}
    print(f"status: {data.get('status')}")
    print(f"preview_id: {preview.get('id')}")
    print(f"source_oms_request_id: {preview.get('source_oms_request_id')}")
    print(f"strategy: {preview.get('strategy_name')}")
    print(f"direction: {preview.get('direction')}")
    print(f"volume: {preview.get('volume')}")
    print(f"validation_status: {validation.get('status')}")
    print(f"rejection_reasons: {validation.get('rejection_reasons') or preview.get('rejection_reasons')}")
    print(f"warnings: {validation.get('warnings') or preview.get('warnings')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
