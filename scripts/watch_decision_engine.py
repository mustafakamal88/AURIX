from __future__ import annotations

import json
import os
import time
import urllib.request
from datetime import datetime
from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    url = f"http://{os.getenv('AURIX_HOST', '127.0.0.1')}:{os.getenv('AURIX_PORT', '8765')}/decision-engine/status"
    try:
        while True:
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            print(f"time={datetime.now().isoformat(timespec='seconds')} action={data.get('latest_action')} direction={data.get('latest_direction')} score={data.get('score')} confidence={data.get('confidence')} strategy={data.get('strategy')} top_blocking_reason={data.get('top_blocking_reason')} top_warning={data.get('top_warning')} demo_execution_allowed={data.get('demo_execution_allowed')} live_execution_allowed={data.get('live_execution_allowed')} command_queueing_allowed={data.get('command_queueing_allowed')}")
            time.sleep(5)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
