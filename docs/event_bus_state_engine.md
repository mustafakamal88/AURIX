# Part 27: Core Event Bus / State Engine

Part 27 adds the deterministic runtime backbone for AURIX.

The event bus stores normalized events in an append-only JSONL log. It is infrastructure only: publishing an event never queues MT5 commands, never creates paper trades, never sends broker orders, never changes EA settings, and never calls external AI APIs.

## Purpose

The event bus gives Strategy Agent, Risk Governor, OMS, Journal, Dashboard, and alerting layers one common event format for market, account, strategy, risk, order, execution, journal, and safety observations.

Supported event schemas include order and execution event types such as `ORDER_REQUEST_EVENT` and `ORDER_FILLED_EVENT`, but Part 27 only defines and projects them. It does not use those events to execute anything.

## Storage

Event bus files live under:

```text
data/event_bus/events.jsonl
data/event_bus/status.json
data/event_bus/state_snapshot.json
data/event_bus/state_history.jsonl
```

`events.jsonl` is append-only within the configured history limit. `state_snapshot.json` is the latest deterministic projection of the log. `state_history.jsonl` keeps compact recent projections.

## State Engine

The state engine projects the latest `AurixRuntimeState` from events:

- tick events update `market.latest_tick`
- candle events update `market.latest_candle`
- account events update `account`
- position and order events update `positions` and `orders`
- context/session events update `context` and `session`
- signal and risk events update `strategy` and `risk`
- paper events update paper observation counts only
- journal, AI review, alert, heartbeat, and safety events update their matching state sections

## Safety

Every event carries hard false execution safety flags:

```text
live_execution_allowed=false
live_arming_allowed=false
command_queueing_allowed=false
mt5_commands_queued=false
broker_order_created=false
ea_settings_modified=false
external_llm_used=false
strategy_config_mutated=false
```

Part 27 adds no live execution, no paper trade creation, no command queueing, no strategy mutation, and no dashboard trading controls.

## Commands

Check status:

```bash
python3 scripts/check_event_bus.py
```

Collect read-only observation events from current local state:

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

Watch the event bus:

```bash
python3 scripts/watch_event_bus.py
```
