# AURIX Agent Notes

This project is Part 1 only: the Mac/Wine MT5 bridge layer.

Do not use the official Python `MetaTrader5` package for this setup. Native macOS Python cannot directly control the MT5 terminal running inside Wine.

Architecture:

```text
Python FastAPI server on macOS
  <-> MQL5 Expert Advisor inside MT5/Wine
  <-> Exness MT5 account
```

Safety rules for future agents:

- Do not enable live trading automatically.
- Do not send real trades unless the user explicitly asks.
- Keep `AllowLiveTrading=false` as the EA default.
- Keep `MaxVolume=0.01` as the EA default unless the user explicitly changes it.
- Do not add strategy logic, AI reasoning, auto-trading, or a Risk Governor in Part 1.
- Treat commands as queued bridge messages; execution is blocked by the EA unless `AllowLiveTrading=true` is manually set in EA inputs and the command includes `live_confirm="I_ACCEPT_LIVE_RISK"`.
