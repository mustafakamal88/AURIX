# AURIX Paper Trade Ledger

Part 5 adds a forward-test layer for shadow strategy signals.

It simulates the full trade path without sending anything to MT5:

```text
shadow signal
  -> simulated risk check
  -> paper trade ledger
  -> live snapshot monitoring
  -> virtual SL/TP close
  -> paper P/L and R multiple
```

No MT5 command is queued by the paper engine. No live execution is added.

## Config

Settings live in:

```text
config/paper_trading.yaml
```

Defaults:

- enabled: true
- symbol: XAUUSDm
- default_volume: 0.01
- default_stop_points: 300
- default_take_profit_points: 600
- max_open_paper_trades: 1
- allow_multiple_same_direction: false
- spread_points_for_entry: snapshot
- commission_per_lot: 0.0
- slippage_points: 0

## Storage

Paper trades are stored in:

```text
data/paper_trades.json
```

## Endpoints

```text
GET  /paper/status
GET  /paper/trades
GET  /paper/open
POST /paper/evaluate-signal
POST /paper/update
POST /paper/close/{paper_trade_id}
POST /paper/reset
```

## Update Rules

BUY:

- TP hit when `bid >= take_profit`
- SL hit when `bid <= stop_loss`

SELL:

- TP hit when `ask <= take_profit`
- SL hit when `ask >= stop_loss`

The ledger records `pnl_points` and `r_multiple` when a trade closes.

## Scripts

Check status:

```bash
python3 scripts/check_paper.py
```

Evaluate one signal and maybe create a paper trade:

```bash
python3 scripts/evaluate_paper_once.py
```

Update open paper trades:

```bash
python3 scripts/update_paper_once.py
```

Watch paper trading:

```bash
python3 scripts/watch_paper.py
```

Run local self-checks:

```bash
python3 scripts/self_check_paper.py
```

Keep `AURIX_BROKER_EXECUTION=false` in the EA.
