# Part 30: Demo-only OMS Execution Agent

Part 30 builds the demo-only OMS backbone between strategy-agent signals and future broker reconciliation.

The default mode is `DEMO_OMS_DRY_RUN`. In this mode the OMS can create deterministic order intents and dry-run order request events from approved `SIGNAL_EVENT` inputs, but it does not queue MT5 commands, create broker orders, create paper trades, execute demo orders, execute live orders, or change EA settings.

## Safety Defaults

Configuration lives in `config/demo_oms.yaml`.

The execution flags remain off:

- `allow_demo_execution: false`
- `allow_demo_command_queueing: false`
- `allow_live_arming: false`
- `allow_live_execution: false`
- `allow_real_account_execution: false`
- `allow_command_queueing: false`

Every OMS artifact carries safety flags confirming:

- `demo_oms_only: true`
- `dry_run_default: true`
- `mt5_commands_queued: false`
- `broker_order_created: false`
- `paper_trade_created: false`
- `ea_settings_modified: false`

## What The OMS Creates

The OMS reads the latest event-bus `SIGNAL_EVENT` and creates an `OmsOrderIntent`.

If validation passes, it creates an `OmsOrderRequest` with status `DRY_RUN_ONLY` and publishes an `ORDER_REQUEST_EVENT` to the event bus. The event updates `runtime_state.execution.latest_order_request`.

For Part 30:

- `mt5_command_id` is always `null`
- `broker_order_id` is always `null`
- no `ORDER_FILLED_EVENT` is published

## Validation

Validation checks config, mode, symbol, strategy allow-list, direction, entry, stop loss, take profit, volume, spread, daily OMS request count, open OMS request count, command queueing flags, execution flags, and EA live-trading state when reported.

Risk governor integration is validation-only. It does not create command objects, call `/commands/open-market`, queue commands, or mutate broker state. If market/account context is unavailable, validation blocks with `risk_governor_validation_unavailable`.

## API

Read status:

```bash
python3 scripts/check_demo_oms.py
```

Process latest signal into a dry-run OMS request:

```bash
python3 scripts/process_latest_signal_oms.py
```

Show intents and requests:

```bash
python3 scripts/show_demo_oms_intents.py
python3 scripts/show_demo_oms_requests.py
```

Watch status:

```bash
python3 scripts/watch_demo_oms.py
```

Self-check:

```bash
PYTHONPYCACHEPREFIX=.pycache python3 scripts/self_check_demo_oms.py
```

Actual demo command queueing is a later explicit step. Real account execution remains blocked.
