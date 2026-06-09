# Backtest / Replay Engine

Part 14 adds an offline replay engine for XAUUSD Paper Strategy V1 logic.

It reads recorded M1 candles from:

```text
data/market_candles_m1.json
```

It writes:

```text
data/backtest_report.json
data/backtest_trades.json
```

CSV export writes:

```text
data/exports/backtest_trades.csv
```

## Config

Settings live in:

```text
config/backtest.yaml
```

Default config:

```yaml
enabled: true
symbol: "XAUUSDm"
timeframe: "M1"
source_candles_file: "data/market_candles_m1.json"
default_volume: 0.01
default_stop_points: 300
default_take_profit_points: 600
max_spread_points: 350
lookback_range_candles: 10
min_candles: 20
allowed_sessions: ["LONDON", "NY_PRE_MARKET", "NY_OPEN", "NY_LATE"]
block_closed_session: true
```

## API

```text
GET  /backtest/status
GET  /backtest/report
GET  /backtest/trades
POST /backtest/run
POST /backtest/reset
```

## Scripts

Check status:

```bash
python3 scripts/check_backtest.py
```

Run backtest:

```bash
python3 scripts/run_backtest.py
```

Export CSV:

```bash
python3 scripts/export_backtest_csv.py
```

## Replay Rules

- Start after `min_candles`.
- Use previous `lookback_range_candles` to calculate range high and low.
- BUY setup: previous candle sweeps below range low, current candle closes back above range low, current candle is bullish.
- SELL setup: previous candle sweeps above range high, current candle closes back below range high, current candle is bearish.
- Simulate forward candle-by-candle to TP or SL.
- If TP and SL are both hit in the same candle, assume SL first.
- Avoid overlapping trades.

## Safety

- Backtest/replay only.
- No MT5 execution.
- No MT5 command queueing.
- No external AI calls.
- No automatic strategy mutation.
- EA settings are not modified.
