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
    url = f"http://{host}:{port}/commands/open"

    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            commands = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not list open commands at {url}: {exc}")
        return 1

    if not commands:
        print("No open commands.")
        return 0

    for command in commands:
        print(
            " | ".join(
                [
                    f"id={command.get('id')}",
                    f"status={command.get('status')}",
                    f"type={command.get('type')}",
                    f"symbol={command.get('symbol')}",
                    f"direction={command.get('direction')}",
                    f"volume={command.get('volume')}",
                    f"dispatch_count={command.get('dispatch_count')}",
                ]
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
