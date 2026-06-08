# AURIX Shadow Strategy Engine

Part 4 adds deterministic shadow signal generation. It reads the latest MT5 snapshot and logs paper-only strategy signals.

It does not queue orders, execute trades, call the EA command endpoint, or use AI reasoning.

## Config

Strategy settings live in:

```text
config/strategy_xauusd_shadow_v1.yaml
```

Defaults:

- enabled: true
- mode: SHADOW
- symbol: XAUUSDm
- timeframe: M1
- min_candles: 20
- max_spread_points: 350
- allow_buy: true
- allow_sell: true
- signal_cooldown_seconds: 60
- session_filter_enabled: false

## Signal Statuses

```text
NO_SIGNAL
SHADOW_SIGNAL
SKIPPED_SPREAD
SKIPPED_INSUFFICIENT_DATA
SKIPPED_COOLDOWN
ERROR
```

## V1 Signal Logic

The `xauusd_shadow_v1` strategy is only plumbing validation, not the final trading model.

It checks:

- snapshot symbol is `XAUUSDm`
- at least 20 M1 candles exist
- spread is at or below the configured cap
- bid and ask are valid

BUY shadow signal:

- last candle closes bullish
- close is above previous candle high

SELL shadow signal:

- last candle closes bearish
- close is below previous candle low

Otherwise it returns `NO_SIGNAL`.

## Storage

Signals are stored in:

```text
data/strategy_signals.json
```

Each signal stores `risk_checked=false` and `command_id=null`. This is intentional: Part 4 does not queue or execute.

## Endpoints

```text
GET  /strategy/status
GET  /strategy/signals
POST /strategy/evaluate
POST /strategy/reset-signals
```

## Scripts

Check status:

```bash
python3 scripts/check_strategy.py
```

Evaluate once:

```bash
python3 scripts/evaluate_strategy_once.py
```

Watch shadow signals:

```bash
python3 scripts/watch_strategy.py
```

Run local mock self-checks:

```bash
python3 scripts/self_check_strategy.py
```

Keep `AllowLiveTrading=false` in the EA.
