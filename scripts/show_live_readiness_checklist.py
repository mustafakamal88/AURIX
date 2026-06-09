from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    url = f"http://{host}:{port}/live-readiness/manual-checklist"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read live readiness checklist at {url}: {exc}")
        return 1
    print("AURIX Live Readiness Manual Checklist")
    for index, item in enumerate(data.get("items") or [], start=1):
        print(f"{index}. {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
