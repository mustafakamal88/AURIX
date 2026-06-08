# AURIX Mac/Wine MT5 Bridge

Part 1 is only the MT5 bridge layer for a macOS Python server talking to MetaTrader 5 running through Wine.

Do not use the official Python `MetaTrader5` package for this setup. Native macOS Python cannot directly call the Wine-hosted MT5 terminal.

```text
Python FastAPI server on macOS
  <-> MQL5 Expert Advisor inside MT5/Wine
  <-> Exness MT5 account
```

## Setup

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 scripts/run_server.py
```

Open:

```text
http://127.0.0.1:8765/docs
```

## MT5/Wine EA Setup

Copy:

```text
mql5/Experts/AurixBridgeEA.mq5
```

to the MT5 Experts folder:

```text
File -> Open Data Folder -> MQL5 -> Experts
```

Then:

1. Compile `AurixBridgeEA.mq5` in MetaEditor.
2. Attach the EA to an `XAUUSDm` M15 chart.
3. Keep `AllowLiveTrading=false`.
4. Confirm `MaxVolume=0.01`.

## MT5 WebRequest Allow List

In MT5:

```text
Tools -> Options -> Expert Advisors
```

Enable:

```text
Allow WebRequest for listed URL
```

Add:

```text
http://127.0.0.1:8765
```

## Local Checks

Check that the server is running:

```bash
python3 scripts/check_server.py
```

Watch the latest EA snapshot:

```bash
python3 scripts/watch_snapshot.py
```

Queue a safe test command:

```bash
python3 scripts/queue_test_command.py
```

The command includes `live_confirm="I_ACCEPT_LIVE_RISK"`, but the EA still blocks execution unless `AllowLiveTrading=true` is manually enabled in EA inputs.

## API Endpoints

```text
GET  /health
POST /mt5/snapshot
POST /mt5/snapshot-debug
POST /mt5/execution-result
GET  /mt5/command?terminal_id=AURIX-MAC-001

GET  /state/latest
GET  /state/account
GET  /state/positions
GET  /state/orders
GET  /state/deals
GET  /commands
GET  /results

POST /commands/open-market
POST /commands/close-position
POST /commands/kill-switch
POST /commands/cancel/{command_id}
```

## Safety

- No live trading is enabled by default.
- Commands are queued on the Python server.
- The EA blocks execution unless `AllowLiveTrading=true` is manually enabled.
- The EA also requires `live_confirm="I_ACCEPT_LIVE_RISK"` on each live command.
- `MaxVolume` defaults to `0.01`.
- A future Risk Governor must be built and tested before real trading.

## Troubleshooting

No snapshot received:

- Confirm the server is running with `python3 scripts/check_server.py`.
- Confirm the EA is attached to `XAUUSDm` M15.
- Check the MT5 Experts tab for AURIX WebRequest errors.

WebRequest not allowed:

- Add `http://127.0.0.1:8765` to the MT5 WebRequest allow list.
- The URL must match exactly and must not include `/docs` or a trailing path.

Wrong symbol name:

- Exness often uses suffixed symbols.
- This project defaults to `XAUUSDm`; confirm the chart and EA `TradeSymbol` input both use `XAUUSDm`.

Server not running:

- Run `python3 scripts/run_server.py`.
- Open `http://127.0.0.1:8765/docs`.

Port already in use:

- Stop the old server process, or set a different `AURIX_PORT` in `.env`.
- If you change the port, update the EA `ServerBaseUrl` and the MT5 WebRequest allow-list URL.

Optional reload mode:

- Set `AURIX_RELOAD=true` in `.env` only if your local shell supports uvicorn file watching.
- Leave it off for normal MT5 bridge use.

EA attached but not polling:

- Confirm `TimerSeconds` is greater than zero.
- Confirm Algo Trading is enabled for the terminal and the chart.
- Check that `TerminalId` in EA inputs is `AURIX-MAC-001`.
- Check the MT5 Experts tab for HTTP GET errors against `/mt5/command`.

## Next

Part 2 can add a Risk Governor after the bridge is stable. Do not add strategy logic, auto-trading, or AI reasoning in Part 1.
