# Part 29: Fast RSI First-Reversal Strategy Agent

Part 29 adds the `fast_rsi_first_reversal_v1` Strategy Agent.

The agent is a Python implementation inside the AURIX Strategy Agent layer. It does not modify the MT5 EA. The EA remains only the bridge.

## Logic

The strategy watches RSI and RSI SMA on `XAUUSDm` M1 candles.

BUY setup:

1. RSI first drops below the buy extreme level, default `30`.
2. On a later evaluation, RSI crosses above RSI SMA9.
3. The signal is valid only while RSI remains below the balance zone, default below `45`.

SELL setup:

1. RSI first rises above the sell extreme level, default `70`.
2. On a later evaluation, RSI crosses below RSI SMA9.
3. The signal is valid only while RSI remains above the balance zone, default above `55`.

Balance-zone reset:

```text
45 <= RSI <= 55
```

When RSI enters this zone, both extreme-state flags reset and no signal is emitted.

## Persistent State

State lives in:

```text
data/strategy_agents/fast_rsi_first_reversal_state.json
```

Tracked fields:

- `rsi_was_below_buy_extreme`
- `rsi_was_above_sell_extreme`
- `last_signal_bar_time`
- `last_evaluated_bar_time`
- `updated_at`

## Filters

The agent checks:

- symbol matches `XAUUSDm`
- spread is at or below `max_spread_points`
- one signal per bar
- optional session filter
- HMR/high-margin protection as observation/risk context

If account margin data is unavailable, the agent adds `hmr_margin_data_unavailable` as a warning. It does not reject a setup solely because margin data is missing.

## Outputs

Every evaluation publishes:

```text
STRATEGY_EVALUATION_EVENT
```

Valid signals also publish:

```text
SIGNAL_EVENT
```

Signal payloads include `command_id: null`.

## Safety

Part 29 is signal-only:

- no paper trade creation
- no order request creation
- no MT5 command queueing
- no demo execution
- no live execution
- no EA setting changes
- no broker calls

Future OMS work can decide whether a signal becomes a demo order. Part 29 does not make that decision.
