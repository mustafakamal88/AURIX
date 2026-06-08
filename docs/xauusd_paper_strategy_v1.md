# XAUUSD Paper Strategy V1

Part 8 adds a deterministic XAUUSDm paper strategy using context, recorded candles, spread filtering, session filtering, and a simple liquidity sweep/reclaim idea.

It is paper-only. It never calls `/commands/open-market`, never queues MT5 commands, and never executes trades.

## Config

Settings live in:

```text
config/strategy_xauusd_paper_v1.yaml
```

Defaults:

- enabled: true
- mode: PAPER
- symbol: XAUUSDm
- timeframe: M1
- min_candles: 20
- lookback_range_candles: 10
- max_spread_points: 350
- allowed_sessions: LONDON, NY_PRE_MARKET, NY_OPEN, NY_LATE
- block_closed_session: true
- allow_buy: true
- allow_sell: true
- signal_cooldown_seconds: 120
- default_stop_points: 300
- default_take_profit_points: 600

## Setup Logic

BUY:

- previous candle low sweeps below recent range low
- current candle closes back above recent range low
- current candle is bullish
- context is not `HIGH_SPREAD`

SELL:

- previous candle high sweeps above recent range high
- current candle closes back below recent range high
- current candle is bearish
- context is not `HIGH_SPREAD`

If no setup is present, it returns `NO_SIGNAL`.

## Endpoints

```text
POST /strategy/evaluate-paper-v1
POST /paper/evaluate-paper-v1
```

`/strategy/evaluate-paper-v1` stores a signal only.

`/paper/evaluate-paper-v1` evaluates the signal and may create a paper trade only. It does not create MT5 commands.

## Scripts

Evaluate once:

```bash
python3 scripts/evaluate_xauusd_paper_v1_once.py
```

Watch:

```bash
python3 scripts/watch_xauusd_paper_v1.py
```

Self-check:

```bash
python3 scripts/self_check_xauusd_paper_v1.py
```

Keep `AllowLiveTrading=false` in the EA.
