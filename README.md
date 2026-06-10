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
Part 19 adds a session-aware paper orchestrator for coordinating paper evidence collection during allowed sessions.
Part 20 adds XAUUSD Paper Strategy V2 for research-backed paper testing.
Part 21 adds a read-only local dashboard/cockpit.
Part 22 adds long forward-test mode for explicit, non-autostarting paper evidence collection.
Part 23 adds a live execution readiness layer for deterministic manual-review assessment only.
Part 24 adds an evidence growth monitor for tracking progress toward future manual readiness review.
Part 25 adds signal path certification for proving paper signal pipeline integrity.
Part 26 adds paper risk decision persistence for simulated paper-risk auditability.
Part 27 adds the core event bus and runtime state engine.
Part 28 adds the strategy agent registry.
Part 29 adds the Fast RSI first-reversal scalper strategy agent.
Part 30 adds the demo OMS dry-run layer.
Part 31 adds broker reconciliation.
Part 32 adds the dormant demo command queue adapter.
Part 33 adds the AURIX decision engine and autonomy controller.
Part 34 adds an advanced read-only XAUUSD runtime control dashboard.
Part 35 hardens runtime persistence so concurrent status/dashboard polling cannot collide on fixed JSON temp files.
Part 36 adds runtime provenance, current-session counters, and evidence integrity checks.
The Windows Forex VPS deployment pack adds local Windows setup docs, PowerShell runtime scripts, and a preflight checker for running MT5, the EA, and AURIX on the same VPS.
The Railway Cloud Bridge deployment pack adds secure remote hosting support for the AURIX bridge/dashboard while MT5 and the EA remain on the Windows Forex VPS.

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

Open the read-only runtime cockpit:

```text
http://127.0.0.1:8765/dashboard
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
3. Keep `AURIX_BROKER_EXECUTION=false`.

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

The EA still blocks execution unless `AURIX_BROKER_EXECUTION=true` is manually enabled in EA inputs.

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

## Part 34 Runtime Dashboard

The advanced XAUUSD runtime dashboard is a read-only Broker Execution Cockpit. It shows Railway and EA `AURIX_BROKER_EXECUTION` state, execution match/mismatch, latest command gate reason, AURIX queue state, spread gate, risk model, selected strategy/signal, quick validation, readiness/evidence status, account/market state, paper metrics, forward-test status, and safety locks.

Open it with the server running:

```text
http://127.0.0.1:8765/dashboard
```

Check the dashboard runtime summary from the CLI:

```bash
python3 scripts/check_dashboard_runtime.py
```

Watch the dashboard runtime state every 5 seconds:

```bash
python3 scripts/watch_dashboard_runtime.py
```

The main cards mean:

- `AURIX Decision`: latest action such as `WAIT`, `TRADE_LONG`, `TRADE_SHORT`, `BLOCKED_BY_SPREAD`, `BLOCKED_BY_NO_SIGNAL`, or `SYSTEM_NOT_READY`.
- `Market / XAUUSDm Feed`: bid, ask, spread, max spread threshold, and feed timestamps.
- `Account`: currency, balance, equity, free margin, margin level, and demo/real hint.
- `Fast RSI Strategy`: latest Fast RSI state, direction, RSI values, extremes, rejection reasons, bar, and trace availability.
- `Strategy Agents`: registered/enabled counts, latest statuses, latest signal, and disabled creation flags.
- `Broker Reconciliation`: broker positions/orders, mismatches, warnings, and unexpected exposure.
- `Execution Control State`: Railway and EA broker execution state, match/mismatch, terminal, symbol, positions, latest command state, and primary block.
- `AURIX Gates`: queue state, spread gate, engine max spread, risk model, selected strategy, and latest signal status.
- `Validation / Readiness`: quick validation, evidence, readiness, arming, execution, and block counts.
- `Event Bus / Runtime State`: event count, sequence, last event, runtime state timestamp, and latest decision event.
- `Safety Locks`: confirms broker execution, arming, command queueing, broker order creation, MT5 queueing, paper trade creation, and order request creation are disabled.
- `Why No Trade?`: primary block, secondary blocks, warnings, and recommended next action from the latest decision context.

The dashboard is read-only by design. It does not evaluate strategies, evaluate the decision engine, process OMS requests, preview or dry-run queue payloads, queue MT5 commands, create paper trades, create order requests, change EA settings, mutate strategy config, or place/modify/close broker orders. For Railway, open `/dashboard` and log in with `AURIX_DASHBOARD_PASSWORD`; do not put `AURIX_API_KEY` in the browser URL.

For this XAUUSDm Exness setup, the default internal engine spread threshold is 270 points. The dashboard/operator cockpit should display `Engine Max Spread: 270 points`. Spread control remains an internal AURIX engine/broker configuration value; do not expose it through Railway environment variables or MT5 EA inputs.

## Part 35 Runtime Persistence Hardening

Part 35 fixes a concurrent JSON status write race where multiple read-only status endpoints could try to replace the same fixed temp file, such as `status.json.tmp`, at the same time. Runtime stores now use unique temp file names plus atomic replacement for JSON and JSONL persistence.

Stress test the read-only runtime/status endpoints:

```bash
python3 scripts/stress_runtime_status_endpoints.py
```

This hardening only improves backend persistence stability. It does not enable live trading, demo command queueing, broker order creation, MT5 command queueing, paper trade creation, order request creation, or EA setting changes.

## Part 36 Runtime Provenance and Evidence Integrity

Part 36 separates lifetime/cumulative records from activity created by the current server process. The server now exposes a runtime session id, process id, start time, uptime, startup baseline counters, lifetime counters, current-session deltas, and a safety assertion that answers whether this server run created any paper trade, order request, OMS request, MT5 command, or broker action.

Check runtime provenance:

```bash
python3 scripts/check_runtime_provenance.py
```

Check evidence integrity:

```bash
python3 scripts/check_evidence_integrity.py
```

The evidence integrity endpoint is:

```text
GET /evidence-integrity/status
```

It checks core evidence files, stale atomic temp files, corrupt JSON files, and basic count consistency. This layer is observability only. The dashboard remains read-only, and no live trading, demo command queueing, broker order creation, MT5 command queueing, paper trade creation, order request creation, or EA setting permission is changed.

## Windows Forex VPS Deployment

The recommended deployment for 24/5 MT5 + EA + AURIX runtime is a Windows Forex VPS running Exness MT5, `AurixBridgeEA`, and the local Python bridge on the same machine.

Full setup guide:

```text
docs/windows_forex_vps_setup.md
```

Deployment checklist:

```text
docs/windows_forex_vps_checklist.md
```

Manual start command on the VPS:

```powershell
cd C:\AURIX
.\scripts\windows\start_aurix_server.ps1
```

Dashboard URL inside the VPS:

```text
http://127.0.0.1:8765/dashboard
```

Server health check:

```powershell
cd C:\AURIX
.\scripts\windows\check_aurix_server.ps1
```

Preflight check:

```powershell
cd C:\AURIX
python scripts\check_windows_vps_preflight.py
```

Install startup task:

```powershell
cd C:\AURIX
.\scripts\windows\install_aurix_startup_task.ps1
```

This deployment pack is packaging only. Demo execution, live execution, broker order creation, MT5 command queueing, paper trade creation, order request creation, and EA setting changes remain disabled until a later explicit safety-gated part.

## Railway Cloud Bridge Deployment

The hybrid deployment runs the AURIX FastAPI bridge, runtime dashboard, decision engine, provenance, and evidence integrity layer on Railway. The Windows Forex VPS runs only Exness MT5 plus `AurixBridgeEA`.

Railway setup guide:

```text
docs/railway_cloud_bridge_setup.md
```

MT5 hybrid setup guide:

```text
docs/railway_mt5_hybrid_setup.md
```

Railway start command:

```bash
python scripts/run_server.py
```

Required Railway volume mount:

```text
/data
```

Dashboard URL pattern:

```text
https://your-app.up.railway.app/dashboard
```

The browser dashboard authenticates through `/dashboard/login` using `AURIX_DASHBOARD_PASSWORD` and a signed HttpOnly cookie. `AURIX_API_KEY` remains for EA and API clients. If it was previously exposed in a dashboard URL, rotate it.

Remote health check:

```bash
python3 scripts/check_railway_remote_health.py \
  --base-url https://your-app.up.railway.app \
  --api-key YOUR_AURIX_API_KEY
```

Required broker execution switch stays false unless explicitly enabled:

```env
AURIX_BROKER_EXECUTION=false
```

Remote access requires `AURIX_API_KEY` when `AURIX_RUNTIME_PROFILE=RAILWAY_CLOUD_BRIDGE`. This pack does not enable broker execution, broker order creation, MT5 command queueing, paper trade creation, order request creation, or EA setting changes.

## Part 38 Demo Broker Execution

Part 38 adds deterministic demo-account broker execution gates for Railway + MT5 EA. Defaults remain disabled.

Required Railway variable to enable broker execution:

```env
AURIX_BROKER_EXECUTION=true
```

Spread, queue behavior, strategy selection, and risk defaults are internal AURIX engine config, not Railway operator variables.

Required EA inputs:

```text
BridgeBaseUrl=https://web-production-bc7d4.up.railway.app
ApiKey=YOUR_AURIX_API_KEY
TerminalId=AURIX-VPS-001
TradeSymbol=XAUUSDm
AURIX_BROKER_EXECUTION=false
MagicNumber=880001
```

Stop broker execution by setting `AURIX_BROKER_EXECUTION=false` in Railway and in the EA.

Real-money live execution remains unsupported and disabled.

## Quick Paper Forward Validation

Run the paper-only safety/proof harness before considering broker execution:

```bash
python3 scripts/run_quick_validation.py
```

Check the latest saved report:

```bash
python3 scripts/check_quick_validation.py
```

The report is stored at `data/quick_validation_report.json` and is also visible through `/quick-validation/status`, `/quick-validation/latest`, and the read-only dashboard runtime summary. This harness does not call `/commands/open-market`, does not queue MT5 commands, does not use external AI, and keeps `AURIX_BROKER_EXECUTION=false`.

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

Run or start orchestrator:

```bash
python3 scripts/run_orchestrator_once.py
python3 scripts/start_orchestrator.py
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
GET  /paper-risk-audit/status
GET  /paper-risk-audit/latest
GET  /paper-risk-audit/history
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
GET  /orchestrator/status
GET  /long-forward-test/status
GET  /live-readiness/status
GET  /live-readiness/latest
GET  /live-readiness/manual-checklist
GET  /evidence-monitor/status
GET  /evidence-monitor/latest
GET  /evidence-monitor/history
GET  /signal-certifier/status
GET  /signal-certifier/latest
GET  /signal-certifier/history

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
POST /paper-risk-audit/reset
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
POST /orchestrator/run-once
POST /orchestrator/start
POST /orchestrator/stop
POST /orchestrator/reset
POST /long-forward-test/run-once
POST /long-forward-test/start
POST /long-forward-test/stop
POST /long-forward-test/daily-report
POST /long-forward-test/reset
POST /live-readiness/evaluate
POST /live-readiness/reset
POST /evidence-monitor/evaluate
POST /evidence-monitor/reset
POST /signal-certifier/certify
POST /signal-certifier/reset
```

## Safety

- No live trading is enabled by default.
- Commands are queued on the Python server.
- `POST /commands/open-market` must pass the Risk Governor before it is queued.
- The EA blocks execution unless `AURIX_BROKER_EXECUTION=true` is manually enabled.
- AURIX owns risk, lot sizing, spread gates, queue gates, and strategy approval.
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
- The Part 19 orchestrator is paper-only, does not queue commands, and does not autostart on server boot.
- The Part 21 dashboard is read-only and does not queue commands or mutate config.
- The Part 22 long forward-test mode is paper-only, does not autostart on server boot, and does not queue commands.
- The Part 23 live readiness layer is assessment-only, does not queue commands, does not change EA settings, and keeps arming/execution disabled by config.
- The Part 24 evidence growth monitor is monitor-only, does not queue commands, and only feeds future manual readiness review.
- The Part 25 signal path certifier is observability-only, does not queue commands, and does not place demo or live broker orders.
- The Part 26 paper risk audit is paper-only observability, does not queue commands, and links simulated risk decisions to paper signals/trades.

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

## Part 19: Session-Aware Paper Orchestrator

Orchestrator settings live in:

```text
config/orchestrator.yaml
```

Run once or start/stop:

```bash
python3 scripts/run_orchestrator_once.py
python3 scripts/start_orchestrator.py
python3 scripts/stop_orchestrator.py
```

More detail:

```text
docs/session_orchestrator.md
```

## Part 20: XAUUSD Paper Strategy V2

V2 settings live in:

```text
config/strategy_xauusd_paper_v2.yaml
```

Run the server:

```bash
python3 scripts/run_server.py
```

Evaluate V2 once or watch it:

```bash
python3 scripts/evaluate_xauusd_paper_v2_once.py
python3 scripts/watch_xauusd_paper_v2.py
```

Backtest V2 and compare V1 vs V2:

```bash
python3 scripts/run_backtest.py
python3 scripts/run_backtest_v2.py
python3 scripts/compare_backtest_v1_v2.py
```

V2 is paper/research only. It does not call `/commands/open-market`, does not queue MT5 commands, and all V2 signals keep `command_id=null`. Current evidence has low sample size, so V2 must not be treated as profitable or live-ready.

More detail:

```text
docs/xauusd_paper_strategy_v2.md
```

## Part 21: Local Dashboard / Cockpit

Run the server and open the read-only dashboard:

```bash
python3 scripts/run_server.py
python3 scripts/open_dashboard.py
```

Direct URL:

```text
http://127.0.0.1:8765/dashboard
```

The dashboard is monitoring only. It does not call `/commands/open-market`, does not queue MT5 commands, does not start or stop the daemon/orchestrator, and does not mutate strategy or live trading config.

More detail:

```text
docs/dashboard.md
```

## Part 22: Long Forward-Test Mode

Long forward-test settings live in:

```text
config/long_forward_test.yaml
```

Run the server:

```bash
python3 scripts/run_server.py
```

Start, watch, stop, and report:

```bash
python3 scripts/start_long_forward_test.py
python3 scripts/watch_long_forward_test.py
python3 scripts/stop_long_forward_test.py
python3 scripts/generate_long_forward_daily_report.py
```

Run one cycle without starting the background loop:

```bash
python3 scripts/run_long_forward_test_once.py
```

Long forward-test mode is paper-only. It does not autostart on server boot, does not call trading execution endpoints, does not queue MT5 commands, does not call external AI APIs, and does not mutate live or strategy config.

More detail:

```text
docs/long_forward_test_mode.md
```

## Part 23: Live Execution Readiness Layer

Live readiness settings live in:

```text
config/live_readiness.yaml
```

Run the server:

```bash
python3 scripts/run_server.py
```

Check the latest readiness status:

```bash
python3 scripts/check_live_readiness.py
```

Evaluate readiness and save `data/live_readiness_report.json`:

```bash
python3 scripts/evaluate_live_readiness.py
```

Show the manual checklist:

```bash
python3 scripts/show_live_readiness_checklist.py
```

Live readiness is assessment-only. It does not enable live trading, does not queue MT5 commands, does not modify EA settings, does not mutate strategy config, and does not call external AI APIs. Because `allow_live_arming=false` and `allow_live_execution=false`, the highest status is `READY_FOR_MANUAL_REVIEW`; micro-live mode is not built yet.

More detail:

```text
docs/live_execution_readiness.md
```

## Part 24: Evidence Growth / Forward-Test Completion Monitor

Evidence monitor settings live in:

```text
config/evidence_monitor.yaml
```

Run the server:

```bash
python3 scripts/run_server.py
```

Check evidence growth:

```bash
python3 scripts/check_evidence_growth.py
```

Evaluate evidence growth and save `data/evidence_growth_report.json`:

```bash
python3 scripts/evaluate_evidence_growth.py
```

Watch evidence growth:

```bash
python3 scripts/watch_evidence_growth.py
```

Show evidence growth history:

```bash
python3 scripts/show_evidence_growth_history.py
```

Evidence growth is monitoring only. It does not enable live trading, arm live trading, queue MT5 commands, modify EA settings, mutate strategy config, or modify Part 23 readiness config. `READY_FOR_READINESS_REVIEW` only feeds a future manual readiness review; it is not permission for live trading.

More detail:

```text
docs/evidence_growth_monitor.md
```

## Part 25: End-to-End Signal Path Certification

Signal certifier settings live in:

```text
config/signal_certifier.yaml
```

Run the server:

```bash
python3 scripts/run_server.py
```

Check signal path certification:

```bash
python3 scripts/check_signal_path.py
```

Certify the latest configured paper trade/signal:

```bash
python3 scripts/certify_signal_path.py
```

Watch certification:

```bash
python3 scripts/watch_signal_path.py
```

Show certification history:

```bash
python3 scripts/show_signal_path_history.py
```

Signal path certification is observability only. It does not enable live trading, arm live trading, queue MT5 commands, place broker orders, modify EA settings, or change readiness/evidence configs. It only proves whether the paper signal path worked.

New V1 paper signals include `decision_trace` with decision-time OHLC and rule checks for deterministic certification. Legacy signals from before Part 25.1 may lack that trace; the certifier treats missing legacy trace as an observability warning and skips V1 rule predicates instead of reconstructing from latest candles.

More detail:

```text
docs/signal_path_certification.md
```

## Part 26: Paper Risk Decision Persistence / Audit Ledger

Paper risk audit settings live in:

```text
config/paper_risk_audit.yaml
```

Check paper risk audit:

```bash
python3 scripts/check_paper_risk_audit.py
```

Show paper risk decisions:

```bash
python3 scripts/show_paper_risk_decisions.py
```

Part 26 improves signal certification by persisting the paper engine's simulated risk decision and linking it to the signal and paper trade. It does not enable live trading, queue MT5 commands, call broker execution endpoints, or place demo/live broker orders. Legacy trades before Part 26 may still lack persisted paper risk decisions.

More detail:

```text
docs/paper_risk_audit.md
```

## Part 27: Core Event Bus / State Engine

Part 27 adds the new backend backbone:

```text
MT5 Bridge
-> Event Bus / State Engine
-> Strategy Agent Layer
-> Risk Governor
-> Execution / OMS Agent
-> Journal + Learning Agent
-> Dashboard / Alerts
```

The event bus is infrastructure only. It records normalized observation events and projects a runtime state snapshot. It does not enable trading, does not queue MT5 commands, does not create paper trades, does not place demo/live broker orders, and does not change EA settings.

Config lives in:

```text
config/event_bus.yaml
```

Check event bus:

```bash
python3 scripts/check_event_bus.py
```

Collect current local state as observation events:

```bash
python3 scripts/collect_event_bus_snapshot.py
```

Show recent events:

```bash
python3 scripts/show_event_bus_recent.py
```

Show projected runtime state:

```bash
python3 scripts/show_runtime_state.py
```

Watch event bus:

```bash
python3 scripts/watch_event_bus.py
```

More detail:

```text
docs/event_bus_state_engine.md
```

## Part 28: Strategy Agent Registry / Adapter Layer

Part 28 adds the event-driven strategy-agent framework after the Part 27 Event Bus / State Engine.

It registers read-only adapters for existing V1/V2 strategy outputs and publishes normalized `STRATEGY_EVALUATION_EVENT` and `SIGNAL_EVENT` observations to the event bus. It does not enable trading, create paper trades, create order requests, queue MT5 commands, or execute demo/live broker orders.

Config lives in:

```text
config/strategy_agents.yaml
```

Check strategy agents:

```bash
python3 scripts/check_strategy_agents.py
```

Evaluate strategy agents:

```bash
python3 scripts/evaluate_strategy_agents.py
```

Show strategy-agent history:

```bash
python3 scripts/show_strategy_agent_history.py
```

Watch strategy agents:

```bash
python3 scripts/watch_strategy_agents.py
```

More detail:

```text
docs/strategy_agent_registry.md
```

## Part 29: Fast RSI First-Reversal Scalper Strategy Agent

Part 29 adds `fast_rsi_first_reversal_v1` as a native Python Strategy Agent after the Part 28 registry.

It evaluates local/event-bus market data, persists RSI extreme-state memory, and publishes `STRATEGY_EVALUATION_EVENT` plus `SIGNAL_EVENT` observations to the event bus. It does not enable trading, create paper trades, create order requests, queue MT5 commands, or execute demo/live broker orders.

Evaluate all strategy agents:

```bash
python3 scripts/evaluate_strategy_agents.py
```

Check Fast RSI agent:

```bash
python3 scripts/check_fast_rsi_agent.py
```

Show strategy-agent history:

```bash
python3 scripts/show_strategy_agent_history.py
```

More detail:

```text
docs/fast_rsi_first_reversal_strategy.md
```

## Part 30: Demo-only OMS Execution Agent

Part 30 adds the dry-run OMS backbone after strategy-agent signals. It converts approved event-bus `SIGNAL_EVENT`s into deterministic OMS order intents and dry-run order request events.

It does not place trades yet. It does not queue MT5 commands, create broker orders, create paper trades, change EA settings, or enable live/demo execution. `mt5_command_id` and `broker_order_id` remain `null` for Part 30.

Config lives in:

```text
config/demo_oms.yaml
```

Check Demo OMS:

```bash
python3 scripts/check_demo_oms.py
```

Process the latest signal into an OMS dry-run request:

```bash
python3 scripts/process_latest_signal_oms.py
```

Show OMS intents and requests:

```bash
python3 scripts/show_demo_oms_intents.py
python3 scripts/show_demo_oms_requests.py
```

Self-check:

```bash
PYTHONPYCACHEPREFIX=.pycache python3 scripts/self_check_demo_oms.py
```

Part 30 prepares the system for broker reconciliation and a future explicit demo-execution step by adding OMS validation, state, audit history, and `ORDER_REQUEST_EVENT` projection into the event bus. Actual demo command queueing is intentionally left disabled.

More detail:

```text
docs/demo_oms_execution_agent.md
```

## Part 31: Broker Reconciliation Engine

Part 31 adds a read-only broker reconciliation layer. It compares AURIX expected dry-run state, Event Bus state, Demo OMS order requests, and MT5 bridge-reported broker state.

It detects unexpected broker positions/orders, impossible OMS execution state, missing broker data, and safety drift. It does not place trades, queue MT5 commands, modify or close broker orders, create paper trades, or change EA settings.

Config lives in:

```text
config/broker_reconciliation.yaml
```

Check broker reconciliation:

```bash
python3 scripts/check_broker_reconciliation.py
```

Run reconciliation:

```bash
python3 scripts/run_broker_reconciliation.py
```

Show reconciliation history:

```bash
python3 scripts/show_broker_reconciliation_history.py
```

Watch reconciliation:

```bash
python3 scripts/watch_broker_reconciliation.py
```

This comes before demo command queueing because AURIX must first prove broker account, positions, orders, and trade history are readable and that unexpected broker exposure is detected.

More detail:

```text
docs/broker_reconciliation_engine.md
```

## Part 32: Demo Command Queue Adapter

Part 32 adds a dry-run adapter that can convert a validated Demo OMS request into an MT5 command payload preview. It still does not place trades.

Default config keeps manual demo arming and MT5 command queueing off, so previews and payloads are stored as audit artifacts only. The adapter requires clean broker reconciliation before building a payload.

Config lives in:

```text
config/demo_command_queue.yaml
```

Check demo command queue:

```bash
python3 scripts/check_demo_command_queue.py
```

Preview latest command:

```bash
python3 scripts/preview_latest_demo_command.py
```

Dry-run latest command payload:

```bash
python3 scripts/dry_run_latest_demo_command.py
```

Show previews and payloads:

```bash
python3 scripts/show_demo_command_previews.py
python3 scripts/show_demo_command_payloads.py
```

Part 32 still does not call `/commands/open-market`, write to the MT5 command queue, create broker orders, or change EA settings. Before actual demo command queueing, manual demo arming and queue flags must be explicitly enabled in a later reviewed step.

More detail:

```text
docs/demo_command_queue_adapter.md
```

## Part 33: AURIX Decision Engine / Autonomy Controller

Part 33 adds the central decision layer after Event Bus, Strategy Agents, Demo OMS, Broker Reconciliation, and Demo Command Queue safety.

It reads current local state and emits one deterministic AURIX decision such as `WAIT`, `TRADE_LONG`, `TRADE_SHORT`, or a blocked state. `TRADE_LONG` and `TRADE_SHORT` are advisory decision candidates only; Part 33 does not enable trading, create order requests, queue MT5 commands, create broker orders, or change EA settings.

Config lives in:

```text
config/decision_engine.yaml
```

Check decision engine:

```bash
python3 scripts/check_decision_engine.py
```

Evaluate decision:

```bash
python3 scripts/evaluate_decision_engine.py
```

Show and watch decisions:

```bash
python3 scripts/show_decision_history.py
python3 scripts/watch_decision_engine.py
```

More detail:

```text
docs/decision_engine_autonomy_controller.md
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

Future work can define a separately reviewed micro-live implementation after the readiness and evidence growth layers have been reviewed. Do not enable live trading until every safety layer has been intentionally changed, tested, and manually approved.
