import json
from pathlib import Path

path = Path("data/latest_snapshot.json")
if not path.exists():
    print("No snapshot yet. Start server, attach EA to MT5 chart, and wait a few seconds.")
else:
    print(json.dumps(json.loads(path.read_text()), indent=2))
