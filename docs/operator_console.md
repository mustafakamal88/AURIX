# Operator Console and System Health

Part 10 adds a read-only operator status layer for AURIX.

It combines the main system health signals into one place:

- MT5 bridge status
- Latest snapshot freshness
- Account balance and equity
- Market quality
- Context session and regime
- Risk status
- Strategy status
- Paper trading status
- Supervisor status
- Open commands
- Latest execution results
- Latest research parameter sweep summary
- Latest evidence gate report
- Daemon status
- Forward test campaign status
- Session orchestrator status
- Safety status

## API

```text
GET /operator/status
GET /operator/summary
```

`GET /operator/status` returns the full combined JSON payload:

```text
service
timestamp
bridge
account
market
context
risk
strategy
paper
supervisor
analytics
journal
ai_review
backtest
research
evidence
daemon
forward_test
orchestrator
commands
execution
safety
```

`GET /operator/summary` returns a shorter operator view:

```text
ok
mode
symbol
session
regime
spread_points
market_quality_ok
paper_open_count
paper_closed_trades
paper_win_rate
paper_total_r
paper_expectancy_r
supervisor_loop_count
journal_entry_count
backtest_trade_count
backtest_expectancy_r
research_best_expectancy_r
research_warning_count
evidence_status
evidence_live_ready
evidence_blocking_reasons_count
daemon_running
daemon_loop_count
daemon_last_heartbeat_at
daemon_errors
forward_test_status
forward_test_progress_percent
forward_test_closed_paper_trades
orchestrator_running
orchestrator_current_session
orchestrator_session_allowed
orchestrator_forward_test_progress
orchestrator_evidence_status
warnings
```

## Scripts

Print a readable dashboard:

```bash
python3 scripts/operator_status.py
```

Watch the summary:

```bash
python3 scripts/watch_operator.py
```

Override watch interval:

```bash
AURIX_OPERATOR_WATCH_SECONDS=2 python3 scripts/watch_operator.py
```

## Safety

The operator layer is monitoring-only. It does not evaluate strategy, run the supervisor, call `/commands/open-market`, poll `/mt5/command`, or queue MT5 commands.

The safety section includes:

- `live_trading_enabled: false`
- `paper_only: true`
- `ea_allow_live_trading_seen` from snapshot `raw.allow_live_trading` when available
- `command_queueing_from_supervisor`
- `strategy_command_id_present`

Keep EA `AllowLiveTrading=false`.
