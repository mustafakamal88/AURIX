import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

runtime_profile = os.getenv("AURIX_RUNTIME_PROFILE", "LOCAL_DEV").upper()
default_host = "0.0.0.0" if runtime_profile == "RAILWAY_CLOUD_BRIDGE" else "127.0.0.1"
host = os.getenv("AURIX_HOST") or default_host
port_value = os.getenv("PORT") if runtime_profile == "RAILWAY_CLOUD_BRIDGE" else None
port_value = port_value or os.getenv("AURIX_PORT", "8765")
if port_value == "${PORT}":
    port_value = os.getenv("PORT", "8765")
port = int(port_value)
reload = os.getenv("AURIX_RELOAD", "false").lower() in {"1", "true", "yes"}

uvicorn.run("aurix_bridge_server.main:app", host=host, port=port, reload=reload)
