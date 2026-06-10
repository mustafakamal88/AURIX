# Windows Forex VPS Setup

This guide explains how to run AURIX on a Windows Forex VPS with Exness MT5, the AURIX Expert Advisor, and the AURIX Python/FastAPI bridge on the same machine.

This setup is deployment packaging only. It keeps the dashboard read-only and keeps live execution, demo broker execution, and MT5 command queueing disabled.

## What This Setup Does

- Runs the AURIX Python bridge on the VPS at `http://127.0.0.1:8765`.
- Lets the AURIX EA in MT5 send snapshots to the local bridge.
- Lets you open the runtime cockpit inside the VPS browser at `http://127.0.0.1:8765/dashboard`.
- Optionally installs a Windows Scheduled Task so AURIX starts when you log in.
- Does not open firewall ports.
- Does not expose the dashboard publicly.
- Does not enable trading.

## Recommended VPS Layout

Use this simple layout:

```text
C:\AURIX
C:\AURIX\.venv
C:\AURIX\logs
C:\AURIX\data
```

Install MT5 normally. The EA stays inside the MT5 data folder:

```text
MQL5\Experts\AurixBridgeEA.mq5
```

## Install Python On Windows

1. Download Python from `https://www.python.org/downloads/windows/`.
2. Install Python 3.10 or newer.
3. During install, select:

```text
Add python.exe to PATH
```

Check it in PowerShell:

```powershell
python --version
```

## Install Git On Windows

1. Download Git from `https://git-scm.com/download/win`.
2. Install with the default options.
3. Check it in PowerShell:

```powershell
git --version
```

## Clone Or Copy AURIX To C:\AURIX

Option A, clone with Git:

```powershell
cd C:\
git clone https://github.com/mustafakamal88/AURIX.git AURIX
cd C:\AURIX
```

Option B, copy the project folder manually to:

```text
C:\AURIX
```

## Create And Activate Python Virtual Environment

From PowerShell:

```powershell
cd C:\AURIX
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

## Install Python Dependencies

With the virtual environment active:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Copy the example environment file:

```powershell
Copy-Item .env.example .env
```

Keep these safety values:

```env
AURIX_HOST=127.0.0.1
AURIX_DASHBOARD_READ_ONLY=true
AURIX_BROKER_EXECUTION=false
```

Broker execution is controlled by this single switch only. Demo/live routing is not a Railway or environment concept; AURIX keeps spread limits, queue behavior, risk defaults, and strategy selection inside internal engine config.

## Start AURIX Bridge Manually

Recommended PowerShell command:

```powershell
cd C:\AURIX
.\scripts\windows\start_aurix_server.ps1
```

Direct Python command:

```powershell
cd C:\AURIX
.\.venv\Scripts\python.exe scripts\run_server.py
```

The Windows start script writes logs to:

```text
C:\AURIX\logs\windows_aurix_server.log
C:\AURIX\logs\windows_aurix_server_error.log
```

## Open Dashboard Inside VPS

Open this URL in the VPS browser:

```text
http://127.0.0.1:8765/dashboard
```

The dashboard should load the read-only runtime cockpit.

## Copy AURIX EA Into MT5 MQL5\Experts

In MT5:

```text
File -> Open Data Folder
```

Copy:

```text
C:\AURIX\mql5\Experts\AurixBridgeEA.mq5
```

to:

```text
MQL5\Experts\AurixBridgeEA.mq5
```

## Compile EA In MetaEditor

1. Open MetaEditor from MT5.
2. Open `AurixBridgeEA.mq5`.
3. Click Compile.
4. Confirm there are no compile errors.

## Attach EA To XAUUSDm

1. In MT5, open an `XAUUSDm` chart.
2. Use M15 unless you are deliberately testing another chart period.
3. Attach `AurixBridgeEA`.
4. Keep:

```text
AURIX_BROKER_EXECUTION=false
MagicNumber=880001
```

5. In MT5 WebRequest settings, allow:

```text
http://127.0.0.1:8765
```

## Confirm EA Snapshots Are Reaching The Bridge

Run:

```powershell
cd C:\AURIX
.\scripts\windows\check_aurix_server.ps1
```

Or open:

```text
http://127.0.0.1:8765/dashboard/runtime-summary
```

Look for:

- `symbol` equals `XAUUSDm`
- market bid/ask values
- account balance/equity
- latest tick time
- runtime session id

## Check Dashboard Runtime Summary

Run:

```powershell
cd C:\AURIX
python scripts\check_windows_vps_preflight.py
```

With the server running, this checks `/dashboard/runtime-summary` and confirms the safety fields are disabled.

## Install Windows Startup Task

Install the scheduled task:

```powershell
cd C:\AURIX
.\scripts\windows\install_aurix_startup_task.ps1
```

Task name:

```text
AURIX Forex VPS Runtime
```

The task starts AURIX when the Windows user logs in. It does not open firewall ports and does not bind the server to public interfaces.

## Stop AURIX Safely

Stop only the AURIX Python bridge:

```powershell
cd C:\AURIX
.\scripts\windows\stop_aurix_server.ps1
```

This does not stop MT5.

## Uninstall Startup Task

Remove only the AURIX scheduled task:

```powershell
cd C:\AURIX
.\scripts\windows\uninstall_aurix_startup_task.ps1
```

## Troubleshooting

### Python Not Recognized

Check:

```powershell
python --version
```

If it fails, reinstall Python and select `Add python.exe to PATH`, or run Python from its full installed path.

### PowerShell Execution Policy Blocks Scripts

Run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then retry:

```powershell
.\.venv\Scripts\Activate.ps1
```

### Port 8765 Already In Use

Check:

```powershell
netstat -ano | findstr :8765
```

Stop the conflicting process or set another local-only port in `.env`:

```env
AURIX_HOST=127.0.0.1
AURIX_PORT=8766
```

Then update the MT5 WebRequest URL and dashboard URL to match.

### Dashboard Not Opening

Check the server:

```powershell
.\scripts\windows\check_aurix_server.ps1
```

Check logs:

```powershell
Get-Content .\logs\windows_aurix_server_error.log -Tail 50
```

### EA Not Sending Snapshots

Check:

- AURIX bridge is running.
- MT5 WebRequest allows `http://127.0.0.1:8765`.
- EA is attached to the chart.
- EA inputs still point to the local bridge.
- MT5 AutoTrading can remain off for safety, but WebRequest must be allowed.

### Wrong Symbol Name

Exness often uses suffixes such as:

```text
XAUUSDm
```

Attach the EA to the exact broker symbol shown in Market Watch.

### MT5 Not Logged In

Log in to the Exness demo account in MT5. The dashboard cannot show current account/feed state if MT5 is disconnected.

### VPS Restarted

After reboot or reconnect:

```powershell
Get-ScheduledTask -TaskName "AURIX Forex VPS Runtime"
.\scripts\windows\check_aurix_server.ps1
```

If needed, start manually:

```powershell
.\scripts\windows\start_aurix_server.ps1
```

## Safety Checklist Before Demo Execution

Before any later gated demo-execution part:

- Confirm the account is demo.
- Confirm EA input `AURIX_BROKER_EXECUTION=false` unless intentionally enabling broker execution.
- Confirm `AURIX_BROKER_EXECUTION=false` unless intentionally enabling broker execution.
- Confirm there are no demo/live broker execution environment switches.
- Confirm broker positions and orders are expected.
- Confirm dashboard safety assertion is safe.
- Confirm no public firewall rule exposes port `8765`.

## What Remains Disabled In This Part

- Live execution.
- Demo broker execution.
- MT5 command queueing.
- Broker order creation.
- Broker order modification.
- Broker position closing.
- Paper trade creation by this deployment pack.
- Order request creation by this deployment pack.
- EA settings changes.
- Public dashboard exposure.
