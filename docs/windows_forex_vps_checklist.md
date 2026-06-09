# Windows Forex VPS Checklist

Use this checklist after copying or pulling AURIX onto the Windows Forex VPS.

- [ ] Code copied or pulled to `C:\AURIX`
- [ ] Python 3.10+ installed
- [ ] Git installed
- [ ] Virtual environment created with `python -m venv .venv`
- [ ] Virtual environment activated
- [ ] Dependencies installed with `pip install -r requirements.txt`
- [ ] `.env.example` copied to `.env`
- [ ] `.env` keeps `AURIX_HOST=127.0.0.1`
- [ ] `.env` keeps `AURIX_LIVE_EXECUTION_ENABLED=false`
- [ ] `.env` keeps `AURIX_DEMO_BROKER_EXECUTION_ENABLED=false`
- [ ] `.env` keeps `AURIX_COMMAND_QUEUE_ENABLED=false`
- [ ] Server starts with `.\scripts\windows\start_aurix_server.ps1`
- [ ] Dashboard opens at `http://127.0.0.1:8765/dashboard`
- [ ] `AurixBridgeEA.mq5` copied into MT5 `MQL5\Experts`
- [ ] EA compiled in MetaEditor
- [ ] EA attached to `XAUUSDm`
- [ ] EA input `AllowLiveTrading=false`
- [ ] EA input `MaxVolume=0.01`
- [ ] MT5 WebRequest allows `http://127.0.0.1:8765`
- [ ] Snapshots received by the bridge
- [ ] `.\scripts\windows\check_aurix_server.ps1` prints runtime summary fields
- [ ] `python scripts\check_windows_vps_preflight.py` passes required checks
- [ ] Startup task installed with `.\scripts\windows\install_aurix_startup_task.ps1`
- [ ] After reboot/logon, AURIX starts again
- [ ] Live execution remains false
- [ ] Demo execution remains false
- [ ] Command queueing remains false
