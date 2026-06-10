# Part 31: Broker Reconciliation Engine

Part 31 adds a read-only broker reconciliation layer before any future demo command queueing.

It compares AURIX expected dry-run state against MT5 bridge-reported broker state:

- account balance, equity, currency, login, and server when available
- broker positions
- broker orders
- broker trade history when available
- Event Bus runtime state
- Demo OMS dry-run order request records

The engine is reconciliation-only. It does not place trades, queue MT5 commands, create broker orders, modify broker orders, close broker orders, create paper trades, call external AI APIs, mutate strategy configuration, or change EA settings.

## Safety Defaults

Configuration lives in `config/broker_reconciliation.yaml`.

The safety flags remain off:

- `allow_broker_order_creation: false`
- `allow_broker_order_modification: false`
- `allow_broker_order_close: false`
- `allow_demo_execution: false`
- `allow_live_execution: false`
- `allow_live_arming: false`
- `allow_command_queueing: false`
- `allow_mt5_command_queueing: false`

Each report carries a safety section confirming no broker or MT5 command side effects occurred.

## Status Logic

`NO_BROKER_DATA` means no local MT5 snapshot/account data is available.

`BLOCKED` means a safety invariant is violated, such as broker execution enabled unexpectedly, command queueing enabled unexpectedly, or broker order mutation enabled.

`MISMATCH` means broker state conflicts with dry-run expectations, such as an unexpected `XAUUSDm` broker position/order or a Demo OMS dry-run request containing a broker order ID.

`WARNINGS` means non-critical data is missing, such as empty trade history or unavailable EA live-trading state.

`CLEAN` means broker state matches the current no-execution/no-position dry-run expectation.

## Commands

Check status:

```bash
python3 scripts/check_broker_reconciliation.py
```

Run reconciliation:

```bash
python3 scripts/run_broker_reconciliation.py
```

Show history:

```bash
python3 scripts/show_broker_reconciliation_history.py
```

Watch status:

```bash
python3 scripts/watch_broker_reconciliation.py
```

This layer is required before any later demo command queueing because AURIX must first prove that broker account, positions, orders, and history are readable and that unexpected exposure can be detected.
