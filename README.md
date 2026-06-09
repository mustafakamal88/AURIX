# AURIX Mac/Wine MT5 Bridge

Part 1 is the MT5 bridge layer for a macOS Python server talking to MetaTrader 5 running through Wine.
Part 2 adds a deterministic Risk Governor in front of command queueing.
Part 3 adds command lifecycle tracking from queue creation to final execution result.
Part 4 adds a shadow-only deterministic strategy engine that logs paper signals without queueing orders.
Part 5 adds a paper trade ledger that simulates signal outcomes without queueing MT5 commands.
Part 6 records live market data and quality metrics for future replay, backtesting, and review.
Part 7 classifies session and market-regime context without queueing or execution.
Part 8 adds XAUUSD Paper Strategy V1 for paper-only liquidity sweep/reclaim testing.
Part 9 adds a paper-only supervisor loop that runs the local quality, context, strategy, and paper ledger pipeline.
Part 10 adds a read-only operator console and system health summary.
Part 11 adds deterministic paper performance analytics.
Part 12 adds deterministic paper trade and strategy signal journaling.
Part 13 adds a safe offline-first AI-style review layer using local templates by default.
Part 14 adds an offline backtest/replay engine for recorded M1 candles.
Part 15 adds local backtest diagnostics and parameter sweeps over recorded candles.
Part 16 adds a deterministic evidence gate that can only return paper-only readiness while live readiness is disabled by config.
Part 17 adds a paper-only daemon that can run the local paper pipeline in the background after explicit start.
Part 18 adds a paper forward-test campaign manager for tracking multi-day evidence collection.

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

Evaluate XAUUSD Paper V1 once:

```bash
python3 scripts/evaluate_xauusd_paper_v1_once.py
```

Watch XAUUSD Paper V1:

```bash
python3 scripts/watch_xauusd_paper_v1.py
```

Check paper supervisor status:

```bash
python3 scripts/check_supervisor.py
```

Run the paper supervisor once:

```bash
python3 scripts/run_supervisor_once.py
```

Watch the paper supervisor loop:

```bash
python3 scripts/watch_supervisor.py
```

Check the operator console:

```bash
python3 scripts/operator_status.py
```

Watch the operator summary:

```bash
python3 scripts/watch_operator.py
```

Check paper analytics:

```bash
python3 scripts/check_analytics.py
```

Generate paper performance report:

```bash
python3 scripts/generate_paper_report.py
```

Watch paper analytics:

```bash
python3 scripts/watch_analytics.py
```

Check journal status:

```bash
python3 scripts/check_journal.py
```

Review paper trades:

```bash
python3 scripts/review_paper_trades.py
```

Review strategy signals:

```bash
python3 scripts/review_signals.py
```

Generate daily journal summary:

```bash
python3 scripts/generate_daily_journal.py
```

Watch journal reviews:

```bash
python3 scripts/watch_journal.py
```

Check AI review status:

```bash
python3 scripts/check_ai_review.py
```

Generate AI review report:

```bash
python3 scripts/generate_ai_review.py
```

Watch AI review reports:

```bash
python3 scripts/watch_ai_review.py
```

Check backtest status:

```bash
python3 scripts/check_backtest.py
```

Run backtest:

```bash
python3 scripts/run_backtest.py
```

Export backtest CSV:

```bash
python3 scripts/export_backtest_csv.py
```

Check research status:

```bash
python3 scripts/check_research.py
```

Run parameter sweep:

```bash
python3 scripts/run_parameter_sweep.py
```

Export research CSV:

```bash
python3 scripts/export_research_csv.py
```

Check evidence status:

```bash
python3 scripts/check_evidence.py
```

Evaluate evidence gate:

```bash
python3 scripts/evaluate_evidence_gate.py
```

Check paper daemon:

```bash
python3 scripts/check_daemon.py
```

Run daemon once:

```bash
python3 scripts/run_daemon_once.py
```

Start or stop daemon:

```bash
python3 scripts/start_daemon.py
python3 scripts/stop_daemon.py
```

Start or update forward test campaign:

```bash
python3 scripts/start_forward_test.py
python3 scripts/update_forward_test.py
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
GET  /supervisor/status
GET  /operator/status
GET  /operator/summary
GET  /analytics/paper
GET  /analytics/paper/summary
GET  /journal/status
GET  /journal/entries
GET  /ai-review/status
GET  /ai-review/reports
GET  /ai-review/latest
GET  /backtest/status
GET  /backtest/report
GET  /backtest/trades
GET  /research/status
GET  /research/latest
GET  /evidence/status
GET  /evidence/latest
GET  /daemon/status
GET  /forward-test/status

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
POST /strategy/evaluate-paper-v1
POST /paper/evaluate-paper-v1
POST /supervisor/run-once
POST /supervisor/reset
POST /analytics/paper/generate
POST /journal/review-paper-trades
POST /journal/review-signals
POST /journal/generate-daily-summary
POST /journal/reset
POST /ai-review/generate
POST /ai-review/reset
POST /backtest/run
POST /backtest/reset
POST /research/run-sweep
POST /research/reset
POST /evidence/evaluate
POST /evidence/reset
POST /daemon/run-once
POST /daemon/start
POST /daemon/stop
POST /daemon/reset
POST /forward-test/start
POST /forward-test/update
POST /forward-test/pause
POST /forward-test/reset
```

## Safety

- No live trading is enabled by default.
- Commands are queued on the Python server.
- `POST /commands/open-market` must pass the Risk Governor before it is queued.
- The EA blocks execution unless `AllowLiveTrading=true` is manually enabled.
- The EA also requires `live_confirm="I_ACCEPT_LIVE_RISK"` on each live command.
- `MaxVolume` defaults to `0.01`.
- The Risk Governor does not replace the EA safety gate.
- The Part 9 supervisor is paper-only and has `allow_command_queueing=false`.
- The Part 10 operator console is read-only and does not queue commands.
- The Part 11 analytics layer is report-only and does not queue commands.
- The Part 12 journal engine is review-only and does not queue commands.
- The Part 13 AI review layer uses local templates by default and does not call external AI APIs.
- The Part 14 backtest engine is replay-only and does not queue commands.
- The Part 15 research sweep is backtest-only and does not queue commands or mutate strategy config.
- The Part 16 evidence gate is readiness-only, does not queue commands, and cannot return `live_ready=true` while `allow_live_readiness=false`.
- The Part 17 daemon is paper-only, does not queue commands, and does not autostart on server boot.
- The Part 18 forward-test campaign is tracking-only, does not queue commands, and does not start the daemon automatically.

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

## Part 8: XAUUSD Paper Strategy V1

Strategy settings live in:

```text
config/strategy_xauusd_paper_v1.yaml
```

The strategy uses context, recorded M1 candles, spread filtering, session filtering, and a deterministic range sweep/reclaim setup. It stores strategy signals and can create paper trades only. It never queues MT5 commands.

More detail:

```text
docs/xauusd_paper_strategy_v1.md
```

## Part 9: Paper Trading Supervisor Loop

Supervisor settings live in:

```text
config/supervisor.yaml
```

Runtime status is stored in:

```text
data/supervisor_status.json
```

The supervisor checks the latest snapshot, validates market quality, evaluates context, evaluates XAUUSD Paper Strategy V1, creates paper trades only from actionable paper signals, and updates open paper trades. It never calls `/commands/open-market` and never queues MT5 commands.

More detail:

```text
docs/supervisor_loop.md
```

## Part 10: Operator Console + System Health

The operator console combines bridge, snapshot, account, market, context, risk, strategy, paper trading, supervisor, command, execution, and safety status into one read-only view.

```bash
python3 scripts/operator_status.py
python3 scripts/watch_operator.py
```

More detail:

```text
docs/operator_console.md
```

## Part 11: Paper Performance Analytics

Paper analytics reads the paper ledger, strategy signals, context snapshots, and market quality runtime files, then writes:

```text
data/paper_performance_report.json
```

Generate and inspect the report:

```bash
python3 scripts/generate_paper_report.py
python3 scripts/check_analytics.py
```

More detail:

```text
docs/paper_performance_analytics.md
```

## Part 12: Trade Review / Journal Engine

Journal settings live in:

```text
config/journal.yaml
```

Journal entries are stored in:

```text
data/journal_entries.json
```

Generate deterministic reviews:

```bash
python3 scripts/review_paper_trades.py
python3 scripts/review_signals.py
python3 scripts/generate_daily_journal.py
```

More detail:

```text
docs/journal_engine.md
```

## Part 13: AI Review Agent

AI review settings live in:

```text
config/ai_review.yaml
```

Reports are stored in:

```text
data/ai_review_reports.json
```

Generate the local template review:

```bash
python3 scripts/generate_ai_review.py
```

External LLM use is disabled by default with `allow_external_llm: false`.

More detail:

```text
docs/ai_review_agent.md
```

## Part 14: Backtest / Replay Engine

Backtest settings live in:

```text
config/backtest.yaml
```

Run and export:

```bash
python3 scripts/run_backtest.py
python3 scripts/export_backtest_csv.py
```

More detail:

```text
docs/backtest_replay_engine.md
```

## Part 15: Backtest Diagnostics / Parameter Sweep

Research settings live in:

```text
config/research.yaml
```

Run and export:

```bash
python3 scripts/run_parameter_sweep.py
python3 scripts/export_research_csv.py
```

More detail:

```text
docs/backtest_research_parameter_sweep.md
```

## Part 16: Evidence Gate / Live Readiness Guard

Evidence gate settings live in:

```text
config/evidence_gate.yaml
```

Evaluate:

```bash
python3 scripts/evaluate_evidence_gate.py
```

More detail:

```text
docs/evidence_gate.md
```

## Part 17: Paper Daemon / Background Runner

Daemon settings live in:

```text
config/daemon.yaml
```

Run once or start/stop:

```bash
python3 scripts/run_daemon_once.py
python3 scripts/start_daemon.py
python3 scripts/stop_daemon.py
```

More detail:

```text
docs/paper_daemon.md
```

## Part 18: Forward Test Campaign Manager

Forward-test settings live in:

```text
config/forward_test.yaml
```

Start and update:

```bash
python3 scripts/start_forward_test.py
python3 scripts/update_forward_test.py
```

More detail:

```text
docs/forward_test_campaign.md
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

Part 19 can add additional reporting or research tooling after bridge, Risk Governor, lifecycle, shadow signal plumbing, paper trading, market recording, context classification, XAUUSD Paper V1, the paper supervisor loop, operator console, paper analytics, journal engine, local AI review, backtest replay, research sweeps, evidence gating, the paper daemon, and forward-test campaign tracking are stable. Do not enable live trading until every layer has been reviewed and tested.
