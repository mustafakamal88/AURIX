# Paper Trading Supervisor Loop

Part 9 adds a local paper-only supervisor loop for the AURIX Mac/Wine MT5 bridge.

The supervisor runs the existing safe pipeline:

1. Read the latest MT5 snapshot.
2. Build a market quality report.
3. Evaluate session and market-regime context.
4. Evaluate XAUUSD Paper Strategy V1 when quality gates pass.
5. Create a paper trade only from an actionable paper signal.
6. Update open paper trades against the latest bid/ask.
7. Save `data/supervisor_status.json`.

It does not call `/commands/open-market`, does not add commands to the EA queue, and does not change EA inputs.

## Config

Settings live in:

```text
config/supervisor.yaml
```

Default safety settings:

```yaml
enabled: true
mode: "PAPER"
symbol: "XAUUSDm"
loop_interval_seconds: 5
max_snapshot_age_seconds: 10
require_market_quality_ok: true
run_context: true
run_strategy: true
run_paper_trading: true
allow_command_queueing: false
```

`allow_command_queueing` must remain `false` for Part 9.

## API

```text
GET  /supervisor/status
POST /supervisor/run-once
POST /supervisor/reset
```

`POST /supervisor/run-once` saves and returns a `SupervisorStatus` object. If market quality is required and the latest snapshot is stale, missing, wrong-symbol, missing candles, or high-spread, the supervisor records the errors and skips strategy/paper entry creation for that loop.

Open paper trades are still updated when a snapshot is available.

## Scripts

Check status:

```bash
python3 scripts/check_supervisor.py
```

Run one supervisor pass:

```bash
python3 scripts/run_supervisor_once.py
```

Watch the loop locally:

```bash
python3 scripts/watch_supervisor.py
```

Override watch interval:

```bash
AURIX_SUPERVISOR_WATCH_SECONDS=2 python3 scripts/watch_supervisor.py
```

## Status File

Runtime status is written to:

```text
data/supervisor_status.json
```

This file is runtime state and should not be committed.

## Safety Boundary

- Paper/simulation only.
- No live execution.
- No EA command queueing.
- No AI reasoning.
- No learning engine.
- No live auto execution.
- EA `AllowLiveTrading=false` remains unchanged.
