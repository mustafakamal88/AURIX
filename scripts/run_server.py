import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

host = os.getenv("AURIX_HOST", "127.0.0.1")
port = int(os.getenv("AURIX_PORT", "8765"))
reload = os.getenv("AURIX_RELOAD", "false").lower() in {"1", "true", "yes"}

uvicorn.run("aurix_bridge_server.main:app", host=host, port=port, reload=reload)
