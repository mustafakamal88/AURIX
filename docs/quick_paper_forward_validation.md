# Quick Paper Forward Validation

Quick validation is a paper-forward proof harness. It checks that runtime, market, context, strategy, paper, analytics, evidence, readiness, broker gate, operator, and dashboard safety surfaces are coherent before any demo broker execution is considered.

It does not enable broker execution, does not queue MT5 commands, does not call `/commands/open-market`, does not require EA execution, does not call external AI APIs, and does not mutate strategy config.

## API

```text
GET  /quick-validation/status
GET  /quick-validation/latest
POST /quick-validation/run
POST /quick-validation/reset
```

The latest report is stored at:

```text
data/quick_validation_report.json
```

## Scripts

Run once against a local server:

```bash
python3 scripts/run_quick_validation.py
```

Check latest status:

```bash
python3 scripts/check_quick_validation.py
```

Watch periodically:

```bash
python3 scripts/watch_quick_validation.py
```

## Safety

Every report includes:

```text
paper_only=true
broker_execution_enabled=false
mt5_commands_queued=false
open_market_called=false
ea_execution_required=false
external_llm_used=false
strategy_config_mutated=false
```

`AURIX_BROKER_EXECUTION=false` must remain the default in Railway and in the EA until a separate explicit broker-execution part.

