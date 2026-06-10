# macOS + Wine MT5 Setup

## Python Server

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 scripts/run_server.py
```

Open:

```text
http://127.0.0.1:8765/docs
```

## MT5 Expert Advisor

Copy:

```text
mql5/Experts/AurixBridgeEA.mq5
```

to:

```text
MT5 Data Folder/MQL5/Experts/
```

In MT5:

1. Open MetaEditor.
2. Compile `AurixBridgeEA.mq5`.
3. Attach `AurixBridgeEA` to an `XAUUSDm` M15 chart.
4. Keep `AURIX_BROKER_EXECUTION=false` for bridge testing.
5. Confirm `TradeSymbol=XAUUSDm`.

## WebRequest Allow List

In MT5:

```text
Tools -> Options -> Expert Advisors
```

Enable:

```text
Allow WebRequest for listed URL
```

Add exactly:

```text
http://127.0.0.1:8765
```

## Local Verification

With the server running:

```bash
python3 scripts/check_server.py
python3 scripts/watch_snapshot.py
```

`watch_snapshot.py` should start printing account and tick fields after the EA posts its first snapshot.
