# Part 28: Strategy Agent Registry / Adapter Layer

Part 28 adds the event-driven Strategy Agent framework for AURIX.

This layer registers strategy agents, evaluates enabled agents in observation mode, adapts existing strategy outputs into normalized results, and publishes strategy evaluation and signal observations to the Part 27 Event Bus.

It does not create paper trades, order requests, MT5 commands, demo orders, live orders, or EA setting changes.

## Registered Agents

Part 28 registers read-only adapters for existing local strategy outputs:

- `xauusd_paper_v1_adapter`
- `xauusd_paper_v2_adapter`

The adapters read latest stored strategy signals from local state. They do not run or mutate strategy logic.

## Event Publishing

Every evaluation may publish:

```text
STRATEGY_EVALUATION_EVENT
```

When a valid signal exists, the evaluator also publishes:

```text
SIGNAL_EVENT
```

Published signal events always carry `command_id: null`.

## Storage

Strategy-agent state lives under:

```text
data/strategy_agents/status.json
data/strategy_agents/latest_evaluations.json
data/strategy_agents/history.jsonl
```

## Safety

Part 28 is `STRATEGY_OBSERVATION_ONLY`.

Safety flags remain false:

```text
paper_trade_creation_allowed=false
order_request_creation_allowed=false
demo_execution_allowed=false
live_execution_allowed=false
live_arming_allowed=false
command_queueing_allowed=false
mt5_commands_queued=false
broker_order_created=false
ea_settings_modified=false
external_llm_used=false
strategy_config_mutated=false
```

## Commands

Check strategy agents:

```bash
python3 scripts/check_strategy_agents.py
```

Evaluate enabled strategy agents:

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

Part 28 prepares the architecture for Part 29, where the Fast RSI First-Reversal Scalper can be added as a proper Strategy Agent.

## Fast RSI Agent

Part 29 adds `fast_rsi_first_reversal_v1`, a native Python Strategy Agent for `XAUUSDm`.

It evaluates M1 candle data in observation mode, persists RSI extreme-state memory, and publishes normalized strategy evaluation events. If a valid setup exists, it publishes a signal event with `command_id: null`.

It remains signal-only. It does not create paper trades, order requests, MT5 commands, demo orders, or live orders.
