# Long Forward-Test Mode

Part 22 adds a controlled long-running paper-forward test mode.

It is designed to run AURIX across London and New York sessions, collect evidence, update reports, and persist a clear status log without live execution.

## Safety

Long forward-test mode is paper-only.

It does not:

- enable live trading
- modify EA inputs
- queue MT5 commands
- call trading execution endpoints
- call external AI APIs
- mutate strategy config
- autostart on server boot

The manager safety status always includes:

```text
paper_only=true
live_execution_allowed=false
command_queueing_allowed=false
external_llm_allowed=false
autostart_on_server_boot=false
mt5_commands_queued=false
```

## Config

Settings live in:

```text
config/long_forward_test.yaml
```

The default is:

```text
mode=PAPER
auto_start_orchestrator=true
auto_start_daemon=false
allow_command_queueing=false
allow_live_execution=false
allow_external_llm=false
autostart_on_server_boot=false
```

## Run

Start the API:

```bash
python3 scripts/run_server.py
```

Check status:

```bash
python3 scripts/check_long_forward_test.py
```

Run one cycle:

```bash
python3 scripts/run_long_forward_test_once.py
```

Start the background long-run loop:

```bash
python3 scripts/start_long_forward_test.py
```

Watch status:

```bash
python3 scripts/watch_long_forward_test.py
```

Stop the loop:

```bash
python3 scripts/stop_long_forward_test.py
```

Generate a daily report:

```bash
python3 scripts/generate_long_forward_daily_report.py
```

## API

```text
GET  /long-forward-test/status
POST /long-forward-test/run-once
POST /long-forward-test/start
POST /long-forward-test/stop
POST /long-forward-test/daily-report
POST /long-forward-test/reset
```

The server does not autostart this mode. Start it explicitly when you want a long paper-forward test window.
