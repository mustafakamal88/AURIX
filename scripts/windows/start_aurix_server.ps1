param(
    [string]$ProjectRoot
)

$ErrorActionPreference = "Stop"

function Resolve-AurixRoot {
    param([string]$ProvidedRoot)
    if ($ProvidedRoot) {
        return (Resolve-Path $ProvidedRoot).Path
    }
    $scriptPath = Split-Path -Parent $MyInvocation.ScriptName
    return (Resolve-Path (Join-Path $scriptPath "..\..")).Path
}

$root = Resolve-AurixRoot -ProvidedRoot $ProjectRoot
Set-Location $root

$logsDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

$stdoutLog = Join-Path $logsDir "windows_aurix_server.log"
$stderrLog = Join-Path $logsDir "windows_aurix_server_error.log"
$venvPython = Join-Path $root ".venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    $pythonExe = $venvPython
} else {
    $pythonExe = "python"
}

$env:AURIX_HOST = if ($env:AURIX_HOST) { $env:AURIX_HOST } else { "127.0.0.1" }
$env:AURIX_PORT = if ($env:AURIX_PORT) { $env:AURIX_PORT } else { "8765" }
$env:AURIX_DASHBOARD_READ_ONLY = "true"
$env:AURIX_BROKER_EXECUTION = "false"

$existing = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -like "*scripts\run_server.py*" -or
        $_.CommandLine -like "*scripts/run_server.py*"
    }

if ($existing) {
    Write-Host "AURIX server already appears to be running:"
    $existing | ForEach-Object { Write-Host ("PID {0}: {1}" -f $_.ProcessId, $_.CommandLine) }
    exit 0
}

Write-Host "Starting AURIX server from $root"
Write-Host "Host: $env:AURIX_HOST"
Write-Host "Port: $env:AURIX_PORT"
Write-Host "Logs: $stdoutLog"
Write-Host "Errors: $stderrLog"

$process = Start-Process `
    -FilePath $pythonExe `
    -ArgumentList @("scripts\run_server.py") `
    -WorkingDirectory $root `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -WindowStyle Hidden `
    -PassThru

Write-Host ("AURIX server started. PID: {0}" -f $process.Id)
Write-Host "Dashboard: http://127.0.0.1:8765/dashboard"
