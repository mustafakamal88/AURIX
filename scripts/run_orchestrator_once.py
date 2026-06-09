from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv


def post_json(url: str) -> dict:
    req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    url = f"http://{host}:{port}/orchestrator/run-once"
    try:
        status = post_json(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not run orchestrator once at {url}: {exc}")
        return 1
    print("AURIX Orchestrator Run")
    print(f"session: {status.get('current_session')}")
    print(f"session_allowed: {status.get('session_allowed')}")
    print(f"daemon_running: {status.get('daemon_running')}")
    print(f"forward_test_progress: {status.get('forward_test_progress')}")
    print(f"evidence_status: {status.get('evidence_status')}")
    print(f"actions: {'; '.join(str(action) for action in status.get('actions_taken') or []) or 'none'}")
    print(f"errors: {'; '.join(str(error) for error in status.get('errors') or []) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
