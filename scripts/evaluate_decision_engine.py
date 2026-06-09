from __future__ import annotations

import json
import os
import urllib.request
from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    url = f"http://{os.getenv('AURIX_HOST', '127.0.0.1')}:{os.getenv('AURIX_PORT', '8765')}/decision-engine/evaluate"
    req = urllib.request.Request(url, data=b"{}", method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    print(f"action: {data.get('action')}")
    print(f"direction: {data.get('direction')}")
    print(f"status: {data.get('status')}")
    print(f"confidence: {data.get('confidence')}")
    print(f"score: {(data.get('score') or {}).get('total')}")
    print(f"strategy: {data.get('strategy')}")
    print(f"signal_id: {data.get('signal_id')}")
    print(f"setup_reason: {data.get('setup_reason')}")
    print(f"decision_reasons: {data.get('decision_reasons')}")
    print(f"blocking_reasons: {data.get('blocking_reasons')}")
    print(f"warnings: {data.get('warnings')}")
    print(f"recommendations: {data.get('recommendations')}")
    print(f"event_id: {data.get('event_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
