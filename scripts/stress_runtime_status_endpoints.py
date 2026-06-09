from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


load_dotenv()

BASE_URL = os.getenv("AURIX_BASE_URL") or f"http://{os.getenv('AURIX_HOST', '127.0.0.1')}:{os.getenv('AURIX_PORT', '8765')}"
ITERATIONS = int(os.getenv("AURIX_STRESS_ITERATIONS", "50"))
WORKERS = int(os.getenv("AURIX_STRESS_WORKERS", "12"))
ENDPOINTS = [
    "/event-bus/status",
    "/operator/status",
    "/operator/summary",
    "/dashboard/runtime-summary",
    "/demo-command-queue/status",
    "/strategy-agents/status",
    "/broker-reconciliation/status",
]


def fetch(endpoint: str) -> tuple[str, int, str]:
    url = f"{BASE_URL}{endpoint}"
    request = Request(url, method="GET")
    try:
        with urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
            json.loads(body)
            return endpoint, response.status, ""
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return endpoint, exc.code, detail[:300]
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        return endpoint, 0, str(exc)


def main() -> int:
    failures: list[tuple[str, int, str]] = []
    calls = [endpoint for _ in range(ITERATIONS) for endpoint in ENDPOINTS]
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = [executor.submit(fetch, endpoint) for endpoint in calls]
        for future in as_completed(futures):
            endpoint, status, error = future.result()
            if status >= 500 or status == 0:
                failures.append((endpoint, status, error))

    print(f"base_url: {BASE_URL}")
    print(f"iterations: {ITERATIONS}")
    print(f"endpoints: {len(ENDPOINTS)}")
    print(f"requests: {len(calls)}")
    print(f"failures: {len(failures)}")
    if failures:
        for endpoint, status, error in failures[:20]:
            print(f"FAIL {endpoint} status={status} error={error}", file=sys.stderr)
        return 1
    print("OK: runtime status endpoint stress test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
