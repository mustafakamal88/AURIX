# XAUUSD Paper Strategy V2

Part 20 adds a paper/research-only XAUUSD sweep-reclaim strategy variant.

V2 uses the parameter-sweep evidence as a structural improvement, not as proof of profitability:

- `stop_points: 400`
- `take_profit_points: 600`
- `lookback_range_candles: 5`
- `max_spread_points: 280`
- allowed sessions: London and New York windows only

The replay and forward samples are still small. Treat every V2 result as research evidence only.

## Safety

V2 never queues MT5 commands and never calls `/commands/open-market`.

All V2 signals are created with:

```text
mode=PAPER
risk_checked=false
command_id=null
```

Live trading remains disabled. Do not change EA safety inputs for V2 testing.

## Config

Settings live in:

```text
config/strategy_xauusd_paper_v2.yaml
```

Key filters:

- blocks missing snapshot, missing context, poor market quality, high spread, closed sessions, disallowed sessions, insufficient candles, and CHOP regime
- requires current candle reclaim close and impulse confirmation
- limits repeated signals with cooldown and max signals per session

## Run

Start the API:

```bash
python3 scripts/run_server.py
```

Evaluate once:

```bash
python3 scripts/evaluate_xauusd_paper_v2_once.py
```

Watch V2:

```bash
python3 scripts/watch_xauusd_paper_v2.py
```

Run V2 replay:

```bash
python3 scripts/run_backtest_v2.py
```

Compare V1 and V2:

```bash
python3 scripts/compare_backtest_v1_v2.py
```

## API

```text
POST /strategy/evaluate-paper-v2
POST /paper/evaluate-paper-v2
POST /backtest/run-v2
GET  /backtest/compare-v1-v2
```

`/paper/evaluate-paper-v2` can create a simulated paper trade only. It does not queue terminal commands.
