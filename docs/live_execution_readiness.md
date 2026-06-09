# Live Execution Readiness Layer

Part 23 adds a deterministic readiness and arming review layer for a future micro-live mode.

This layer is assessment-only. It does not enable live trading, queue MT5 commands, modify EA inputs, mutate strategy config, call external AI APIs, or implement micro-live execution.

## Files

```text
aurix_live_readiness/
config/live_readiness.yaml
data/live_readiness_report.json
```

## Endpoints

```text
GET  /live-readiness/status
GET  /live-readiness/latest
POST /live-readiness/evaluate
GET  /live-readiness/manual-checklist
POST /live-readiness/reset
```

`POST /live-readiness/evaluate` reads local reports and status only, saves `data/live_readiness_report.json`, and returns a `LiveReadinessReport`.

## Commands

Check current status:

```bash
python3 scripts/check_live_readiness.py
```

Evaluate readiness:

```bash
python3 scripts/evaluate_live_readiness.py
```

Show the manual checklist:

```bash
python3 scripts/show_live_readiness_checklist.py
```

Watch readiness:

```bash
python3 scripts/watch_live_readiness.py
```

## Statuses

- `BLOCKED`: required evidence or safety checks are missing or failing.
- `PAPER_ONLY`: enough checks pass to continue paper review, but blockers remain.
- `READY_FOR_MANUAL_REVIEW`: all deterministic readiness checks passed. This is not permission to trade.

Because `allow_live_arming=false` and `allow_live_execution=false`, reports always return:

```text
live_arming_allowed=false
live_execution_allowed=false
```

## Safety

The report safety block is fixed to readiness-only behavior:

```text
readiness_only=true
live_execution_allowed=false
live_arming_allowed=false
mt5_commands_queued=false
ea_settings_modified=false
external_llm_used=false
strategy_config_mutated=false
```

Micro-live mode is not built in Part 23.
