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
$taskName = "AURIX Forex VPS Runtime"
$startScript = Join-Path $root "scripts\windows\start_aurix_server.ps1"

if (-not (Test-Path $startScript)) {
    throw "Start script not found: $startScript"
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$startScript`" -ProjectRoot `"$root`""
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DisallowStartIfOnBatteries:$false `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Starts the local AURIX Forex VPS runtime on user logon. Binds to localhost only." `
    -Force | Out-Null

Write-Host "Installed scheduled task: $taskName"
Write-Host "The task starts AURIX on user logon and does not open firewall ports."
