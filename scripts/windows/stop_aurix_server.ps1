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

$processes = Get-CimInstance Win32_Process |
    Where-Object {
        ($_.CommandLine -like "*scripts\run_server.py*" -or $_.CommandLine -like "*scripts/run_server.py*") -and
        $_.CommandLine -like "*$root*"
    }

if (-not $processes) {
    Write-Host "No AURIX server process found for $root."
    exit 0
}

foreach ($process in $processes) {
    Write-Host ("Stopping AURIX server PID {0}" -f $process.ProcessId)
    Stop-Process -Id $process.ProcessId -Force
}

Write-Host "AURIX server stopped. MT5 was not stopped."
