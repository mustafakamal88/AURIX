from __future__ import annotations

import os
import webbrowser

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    url = f"http://{host}:{port}/dashboard"
    api_key = os.getenv("AURIX_API_KEY")
    open_url = f"{url}?api_key={api_key}" if api_key else url
    print(url)
    webbrowser.open(open_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
