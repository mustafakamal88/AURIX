# AURIX Mac/Wine MT5 Bridge

Part 1 is the MT5 bridge layer for a macOS Python server talking to MetaTrader 5 running through Wine.
Part 2 adds a deterministic Risk Governor in front of command queueing.
Part 3 adds command lifecycle tracking from queue creation to final execution result.
Part 4 adds a shadow-only deterministic strategy engine that logs paper signals without queueing orders.
Part 5 adds a paper trade ledger that simulates signal outcomes without queueing MT5 commands.
Part 6 records live market data and quality metrics for future replay, backtesting, and review.
Part 7 classifies session and market-regime context without queueing or execution.

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

Check Risk Governor status:

```bash
python3 scripts/check_risk.py
```

Queue a dry test command through the Risk Governor:

```bash
python3 scripts/queue_test_command_with_risk.py
```

Check command lifecycle:

```bash
python3 scripts/check_command_lifecycle.py
```

List open commands:

```bash
python3 scripts/list_open_commands.py
```

Cancel a queued command:

```bash
python3 scripts/cancel_command.py COMMAND_ID
```

Check shadow strategy status:

```bash
python3 scripts/check_strategy.py
```

Evaluate the shadow strategy once:

```bash
python3 scripts/evaluate_strategy_once.py
```

Watch shadow strategy signals:

```bash
python3 scripts/watch_strategy.py
```

Check paper trading status:

```bash
python3 scripts/check_paper.py
```

Evaluate one signal through the paper ledger:

```bash
python3 scripts/evaluate_paper_once.py
```

Update paper trades once:

```bash
python3 scripts/update_paper_once.py
```

Watch paper trades:

```bash
python3 scripts/watch_paper.py
```

Check market data status:

```bash
python3 scripts/check_market.py
```

Watch market quality:

```bash
python3 scripts/watch_market.py
```

Export market data CSV files:

```bash
python3 scripts/export_market_csv.py
```

Check context status:

```bash
python3 scripts/check_context.py
```

Evaluate context once:

```bash
python3 scripts/evaluate_context_once.py
```

Watch context:

```bash
python3 scripts/watch_context.py
```

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
GET  /commands/open
GET  /commands/{command_id}
GET  /results
GET  /execution/results
GET  /risk/status
GET  /risk/decisions
GET  /strategy/status
GET  /strategy/signals
GET  /paper/status
GET  /paper/trades
GET  /paper/open
GET  /market/status
GET  /market/ticks
GET  /market/candles
GET  /market/quality
GET  /context/status
GET  /context/latest
GET  /context/history

POST /commands/open-market
POST /commands/close-position
POST /commands/kill-switch
POST /commands/{command_id}/cancel
POST /commands/cancel/{command_id}
POST /strategy/evaluate
POST /strategy/reset-signals
POST /paper/evaluate-signal
POST /paper/update
POST /paper/close/{paper_trade_id}
POST /paper/reset
POST /market/reset
POST /context/evaluate
POST /context/reset
```

## Safety

- No live trading is enabled by default.
- Commands are queued on the Python server.
- `POST /commands/open-market` must pass the Risk Governor before it is queued.
- The EA blocks execution unless `AllowLiveTrading=true` is manually enabled.
- The EA also requires `live_confirm="I_ACCEPT_LIVE_RISK"` on each live command.
- `MaxVolume` defaults to `0.01`.
- The Risk Governor does not replace the EA safety gate.

## Part 2: Risk Governor

Risk settings live in:

```text
config/risk.yaml
```

Risk decisions are stored in:

```text
data/risk_decisions.json
```

The governor checks latest snapshot availability, symbol, direction, max volume, open position count, spread, optional SL/TP requirements, daily loss limits, daily trade count, and live execution gating. It is deterministic and does not contain strategy logic or AI reasoning.

More detail:

```text
docs/risk_governor.md
```

## Part 3: Order Lifecycle

Commands now track:

```text
QUEUED -> DISPATCHED -> EXECUTION_BLOCKED / EXECUTION_FAILED / EXECUTION_FILLED
```

They can also become:

```text
CANCELLED
EXPIRED
```

Default command expiry is 30 seconds. Expired commands are not dispatched. Commands are dispatched once only; there is no automatic retry in Part 3.

More detail:

```text
docs/order_lifecycle.md
```

## Part 4: Shadow Strategy Engine

Strategy settings live in:

```text
config/strategy_xauusd_shadow_v1.yaml
```

Signals are stored in:

```text
data/strategy_signals.json
```

The V1 strategy reads the latest snapshot, checks `XAUUSDm` M1 candles and spread, and emits shadow-only `BUY`, `SELL`, or no-signal records. It never queues commands and never executes trades.

More detail:

```text
docs/shadow_strategy_engine.md
```

## Part 5: Paper Trading

Paper trading settings live in:

```text
config/paper_trading.yaml
```

Paper trades are stored in:

```text
data/paper_trades.json
```

The paper engine evaluates shadow signals, runs a simulated risk check, creates virtual trades, and closes them when live snapshots hit SL or TP. It never calls `/commands/open-market` and never queues anything for MT5.

More detail:

```text
docs/paper_trading.md
```

## Part 6: Market Data Recorder

Market data settings live in:

```text
config/market_data.yaml
```

Market data is stored in:

```text
data/market_ticks.json
data/market_candles_m1.json
data/market_quality.json
```

The recorder runs after every successful MT5 snapshot. It appends ticks, deduplicates M1 candles by timestamp, caps stored records, and updates a quality report. It never queues commands and never executes trades.

More detail:

```text
docs/market_data_recorder.md
```

## Part 7: Context Engine

Context settings live in:

```text
config/context.yaml
```

Context snapshots are stored in:

```text
data/context_snapshots.json
```

The context engine classifies the current session, spread state, data quality, range, directional bias, volatility expansion, chop, and breakout/breakdown regimes. It never queues commands and never executes trades.

More detail:

```text
docs/context_engine.md
```

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

Part 8 can add reporting or replay tooling after bridge, Risk Governor, lifecycle, shadow signal plumbing, paper trading, market recording, and context classification are stable. Do not enable live trading until every layer has been reviewed and tested.
