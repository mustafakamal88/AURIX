from __future__ import annotations

import os
import webbrowser

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    url = f"http://{host}:{port}/dashboard"
    print(url)
    webbrowser.open(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
