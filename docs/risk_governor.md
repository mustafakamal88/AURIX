# AURIX Risk Governor

Part 2 adds a deterministic risk-control layer between the Python command API and the MT5 command queue.

```text
POST /commands/open-market
  -> build command object
  -> Risk Governor checks latest snapshot and risk config
  -> persist risk decision
  -> queue command only if approved
  -> EA still enforces AURIX_BROKER_EXECUTION=false by default
```

The Risk Governor does not build strategy logic, AI reasoning, or autonomous execution. It only approves or blocks commands.

## Config

Risk settings live in:

```text
config/risk.yaml
```

Current defaults:

- enabled: true
- max_volume: 0.01
- max_open_positions: 1
- max_spread_points: 350
- require_stop_loss: false
- require_take_profit: false
- max_daily_loss_amount: 1.0
- max_daily_loss_percent: 2.0
- max_trades_per_day: 3
- allowed_symbols: XAUUSDm
- allowed_directions: BUY, SELL
- live_trading_allowed: false

## Checks

The governor blocks when:

- latest account snapshot is missing
- tick data is missing
- spread is missing
- symbol is not allowed
- direction is not allowed
- requested volume exceeds max volume
- open positions have reached the configured cap
- spread exceeds the configured cap
- stop loss is required but missing
- take profit is required but missing
- live execution is requested while live trading is disabled and the command is not marked as test/dry/simulation
- daily loss amount or percent is reached
- approved trades today reaches the configured cap

## Endpoints

```text
GET /risk/status
GET /risk/decisions
```

Risk decisions are stored locally in:

```text
data/risk_decisions.json
```

## Commands

Check status:

```bash
python3 scripts/check_risk.py
```

Queue a dry test command through risk:

```bash
python3 scripts/queue_test_command_with_risk.py
```

Approved output includes:

```text
APPROVED: Risk Governor allowed the test command and it was queued.
```

Blocked output includes:

```text
BLOCKED: Risk Governor rejected the test command.
```

The EA remains safe by default. Do not set `AURIX_BROKER_EXECUTION=true` during Part 2 bridge/risk testing.
