from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv


def main() -> int:
    parser = argparse.ArgumentParser(description="Cancel an AURIX command if it is still QUEUED.")
    parser.add_argument("command_id", help="Command ID to cancel")
    args = parser.parse_args()

    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    url = f"http://{host}:{port}/commands/{args.command_id}/cancel"

    req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"BLOCKED: {exc.read().decode('utf-8')}")
        return 1
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not cancel command at {url}: {exc}")
        return 1

    print(f"CANCELLED: command_id={data.get('command_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
