# AURIX Context Engine

Part 7 adds deterministic session and market-regime context for XAUUSDm.

It classifies context only. It does not queue commands, execute trades, alter strategy behavior, or use AI reasoning.

## Config

Settings live in:

```text
config/context.yaml
```

Configured sessions use `Europe/London` time:

- ASIA: 00:00 to 07:00
- LONDON: 07:00 to 12:00
- NY_PRE_MARKET: 12:00 to 14:30
- NY_OPEN: 14:30 to 17:00
- NY_LATE: 17:00 to 21:00
- CLOSED: fallback

## Regimes

```text
INSUFFICIENT_DATA
HIGH_SPREAD
RANGE
BULLISH_BREAKOUT
BEARISH_BREAKDOWN
VOLATILITY_EXPANSION
CHOP
```

Directional bias:

```text
BULLISH
BEARISH
NEUTRAL
```

## Storage

Context snapshots are stored in:

```text
data/context_snapshots.json
```

## Endpoints

```text
GET  /context/status
GET  /context/latest
GET  /context/history
POST /context/evaluate
POST /context/reset
```

## Scripts

Check status:

```bash
python3 scripts/check_context.py
```

Evaluate once:

```bash
python3 scripts/evaluate_context_once.py
```

Watch context:

```bash
python3 scripts/watch_context.py
```

Run local self-checks:

```bash
python3 scripts/self_check_context.py
```

Keep `AllowLiveTrading=false` in the EA.
