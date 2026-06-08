# AURIX Market Data Recorder

Part 6 records live MT5 snapshot data into local JSON files for later replay, backtesting, signal review, and paper trade analysis.

It records data only. It does not queue commands, execute trades, change strategy behavior, or use AI reasoning.

## Config

Settings live in:

```text
config/market_data.yaml
```

Defaults:

- enabled: true
- symbol: XAUUSDm
- record_ticks: true
- record_candles: true
- record_spread: true
- max_tick_records: 5000
- max_candle_records: 10000
- max_snapshot_age_seconds: 10
- max_spread_points: 350
- min_candles_required: 20

## Storage

```text
data/market_ticks.json
data/market_candles_m1.json
data/market_quality.json
```

Ticks are appended and capped by `max_tick_records`. Candles are deduplicated by timestamp and capped by `max_candle_records`.

## Quality Report

The quality report includes:

- ok
- symbol
- latest_snapshot_age_seconds
- tick_present
- candles_count
- spread_points
- spread_ok
- snapshot_fresh
- reasons
- updated_at

## Endpoints

```text
GET  /market/status
GET  /market/ticks
GET  /market/candles
GET  /market/quality
POST /market/reset
```

## Scripts

Check market status:

```bash
python3 scripts/check_market.py
```

Watch quality:

```bash
python3 scripts/watch_market.py
```

Export CSV:

```bash
python3 scripts/export_market_csv.py
```

Run local self-checks:

```bash
python3 scripts/self_check_market_data.py
```

Exports are written to:

```text
data/exports/market_ticks.csv
data/exports/market_candles_m1.csv
```

Keep `AllowLiveTrading=false` in the EA.
