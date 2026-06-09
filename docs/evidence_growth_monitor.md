# Evidence Growth Monitor

Part 24 adds a deterministic monitor for evidence growth and forward-test completion.

This is monitoring only. It does not enable live trading, arm live trading, queue MT5 commands, modify EA settings, mutate strategy config, modify Part 23 readiness config, call external AI APIs, or implement micro-live execution.

## Files

```text
aurix_evidence_monitor/
config/evidence_monitor.yaml
data/evidence_growth_report.json
data/evidence_growth_history.jsonl
```

## Endpoints

```text
GET  /evidence-monitor/status
GET  /evidence-monitor/latest
POST /evidence-monitor/evaluate
GET  /evidence-monitor/history
POST /evidence-monitor/reset
```

`POST /evidence-monitor/evaluate` reads local reports and status only, saves `data/evidence_growth_report.json`, appends `data/evidence_growth_history.jsonl` when enabled, and returns an `EvidenceGrowthReport`.

## Commands

Check current status:

```bash
python3 scripts/check_evidence_growth.py
```

Evaluate evidence growth:

```bash
python3 scripts/evaluate_evidence_growth.py
```

Watch evidence growth:

```bash
python3 scripts/watch_evidence_growth.py
```

Show recent history:

```bash
python3 scripts/show_evidence_growth_history.py
```

## Progress

Overall progress is deterministic and capped between `0.0` and `1.0`.

Weights:

- Closed paper trades: 30%
- Recorded candles: 20%
- Forward-tested days: 20%
- Evidence gate status: 15%
- Command cleanliness: 5%
- Market quality: 5%
- Operator status: 5%

## Statuses

- `NO_DATA`: no useful local evidence exists.
- `COLLECTING`: evidence exists, but progress is below 50%.
- `IMPROVING`: progress is at least 50%, but requirements are still missing.
- `READY_FOR_READINESS_REVIEW`: monitor targets are met and Part 23 remains safety-limited.
- `BLOCKED`: open commands, unsafe readiness flags, or monitor safety config violations are present.

`READY_FOR_READINESS_REVIEW` does not mean live trading is allowed. It only means the evidence monitor can feed a future manual Part 23 readiness review.

## Safety

The report safety block is fixed to monitor-only behavior:

```text
monitor_only=true
live_execution_allowed=false
live_arming_allowed=false
mt5_commands_queued=false
ea_settings_modified=false
external_llm_used=false
strategy_config_mutated=false
readiness_config_modified=false
```

Micro-live mode is still not built.
