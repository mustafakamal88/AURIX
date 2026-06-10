import json
import urllib.request

payload = {
    "terminal_id": "AURIX-MAC-001",
    "symbol": "XAUUSDm",
    "direction": "BUY",
    "volume": 0.01,
    "sl": None,
    "tp": None,
    "comment": "AURIX-DRY-COMMAND",
    "live_confirm": "I_ACCEPT_LIVE_RISK"
}

req = urllib.request.Request(
    "http://127.0.0.1:8765/commands/open-market",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

with urllib.request.urlopen(req) as resp:
    print(resp.read().decode("utf-8"))
    print("Safety note: EA execution remains blocked unless AURIX_BROKER_EXECUTION=true is manually enabled in EA inputs.")
