# Part 32: Demo Command Queue Adapter

Part 32 builds a dry-run command adapter between Demo OMS order requests and the MT5 command queue.

By default it does not queue commands. It creates command previews and dry-run MT5 command payload objects only.

It does not call `/commands/open-market`, write to the MT5 command queue, create broker orders, create paper trades, modify broker orders, close broker orders, change EA settings, or enable live/demo execution.

## Safety Defaults

Configuration lives in `config/demo_command_queue.yaml`.

The default gates remain off:

- `manual_demo_arm: false`
- `allow_demo_command_queueing: false`
- `allow_mt5_command_queueing: false`
- `allow_demo_execution: false`
- `allow_live_execution: false`
- `allow_live_arming: false`
- `allow_real_account_execution: false`

The adapter requires a `CLEAN` broker reconciliation report and checks that no broker position/order exists for `XAUUSDm`.

## Commands

Check status:

```bash
python3 scripts/check_demo_command_queue.py
```

Preview latest Demo OMS request:

```bash
python3 scripts/preview_latest_demo_command.py
```

Build a dry-run payload:

```bash
python3 scripts/dry_run_latest_demo_command.py
```

Show previews and payloads:

```bash
python3 scripts/show_demo_command_previews.py
python3 scripts/show_demo_command_payloads.py
```

Actual demo queueing requires a future explicit change where manual demo arming and queue flags are enabled intentionally. Real-account execution remains blocked.
