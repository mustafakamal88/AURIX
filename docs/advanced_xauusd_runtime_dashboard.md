# Advanced XAUUSD Runtime Control Dashboard

Part 34 adds a read-only control cockpit for the current AURIX runtime. It is built for visibility only: it aggregates persisted backend state into one summary so the operator can see what the decision engine, strategy agents, market feed, broker reconciliation, demo OMS, demo command queue, and safety locks currently report.

## Purpose

The dashboard answers one operational question: what is AURIX seeing right now, and why is it not trading?

It presents:

- the latest AURIX decision action, score, confidence, strategy, block, warning, autonomy level, and mode
- XAUUSDm bid, ask, spread, spread threshold, tick time, and candle time
- account balance, equity, free margin, margin level, and demo/real hint
- Fast RSI status, RSI values, extreme states, rejection reasons, latest bar, and trace availability
- strategy agent registry counts and latest signal summary
- broker reconciliation status, positions, orders, mismatches, warnings, and unexpected exposure flag
- demo OMS dry-run state and latest request status
- demo command queue dormant/dry-run state, preview/payload counts, and disabled queueing flags
- event bus counts, last sequence, last event type, runtime state time, and latest decision event
- safety locks that confirm execution, arming, queueing, broker orders, paper trade creation, and EA changes are disabled

## Read-Only Design

The endpoint is:

```text
GET /dashboard/runtime-summary
```

It reads latest JSON and JSONL runtime artifacts from `data/`. It does not call evaluation, execution, queue, OMS processing, broker reconciliation run, MT5 command, paper-trade, or external AI routes.

The browser dashboard calls only this GET endpoint. It does not call:

```text
POST /strategy-agents/evaluate
POST /decision-engine/evaluate
POST /demo-oms/process-latest-signal
POST /demo-command-queue/preview-latest
POST /demo-command-queue/dry-run-latest
POST /commands/open-market
```

## Why No Trade

The “Why No Trade?” panel is derived from the latest decision report and supporting safety/readiness artifacts. It highlights the primary block, secondary blocks, warnings, and the next expected operator action.

For example, if the latest decision is `BLOCKED_BY_SPREAD`, the panel shows the spread block first and recommends waiting for spread normalization and a valid Fast RSI signal.

## Safety Locks

The summary always includes explicit safety fields:

```text
read_only_dashboard=true
paper_trade_creation_allowed=false
order_request_creation_allowed=false
demo_command_queueing_allowed=false
mt5_command_queueing_allowed=false
demo_execution_allowed=false
live_execution_allowed=false
live_arming_allowed=false
real_account_execution_allowed=false
mt5_commands_queued=false
broker_order_created=false
broker_order_modified=false
broker_order_closed=false
paper_trade_created=false
ea_settings_modified=false
external_llm_used=false
strategy_config_mutated=false
```

These fields are dashboard guarantees, not execution permissions.

## Why It Does Not Execute

Part 34 is a cockpit, not a trading interface. It has no buttons, no arming control, no order creation, no command queueing, and no broker execution path. Live trading remains controlled only by the MT5 EA input and the existing backend safety rules.

## Visual Redesign Later

This part keeps the existing dashboard style simple and stable. The goal is backend clarity and safe runtime visibility. Visual redesign, motion, richer interactions, or execution controls belong in later parts after the read-only cockpit is proven.

## Part 35 Persistence Hardening

Part 35 fixes the runtime status persistence race observed when several read-only dashboard and operator endpoints are polled concurrently. Stores no longer share fixed temp files such as `status.json.tmp`; JSON and JSONL rewrites use unique temp names and atomic replacement.

The cockpit remains read-only. No trade, order, command queueing, live arming, broker execution, or EA setting permission is changed by this hardening.
