# Part 33: AURIX Decision Engine / Autonomy Controller

Part 33 adds the central AURIX self-decision layer.

It reads Event Bus runtime state, Strategy Agent outputs, Fast RSI signals, Demo OMS status, Broker Reconciliation, Demo Command Queue safety, account state, market state, session context, and risk status. It emits one deterministic AURIX decision and publishes decision events.

It does not create paper trades, order requests, MT5 commands, broker orders, broker modifications, broker closes, EA setting changes, or external AI calls.

## Autonomy Levels

- `OBSERVE_ONLY`: never returns `TRADE_LONG` or `TRADE_SHORT`.
- `ADVISORY_ONLY`: may return `TRADE_LONG` or `TRADE_SHORT` as advisory candidates only.
- `DEMO_DRY_RUN_ONLY`: may return trade candidates and recommend dry-run workflows only.
- `DEMO_AUTONOMY_DISABLED`: reserved, no execution.
- `MICRO_LIVE_DISABLED`: reserved, no execution.

Default mode is `ADVISORY_ONLY`.

## Decision Meaning

`TRADE_LONG` and `TRADE_SHORT` mean the decision engine approves a candidate direction. They do not mean execution. No order request or command is created by Part 33.

Manual approval controls operating mode. AURIX controls the decision. The Risk Governor remains a final veto, OMS remains the execution controller, and Broker Reconciliation remains the truth check.

## Checks

The engine blocks on unsafe system state, broker mismatches, high spread, blocked sessions, missing signals, low confidence, or risk veto. The score combines signal confidence, spread quality, broker cleanliness, session quality, and system health.

## Commands

```bash
python3 scripts/check_decision_engine.py
python3 scripts/evaluate_decision_engine.py
python3 scripts/show_decision_history.py
python3 scripts/watch_decision_engine.py
```
