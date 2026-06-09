param(
    [string]$Url = "http://127.0.0.1:8765/dashboard/runtime-summary"
)

$ErrorActionPreference = "Stop"

try {
    $summary = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 5
} catch {
    Write-Host "AURIX server check failed: $($_.Exception.Message)"
    exit 1
}

$runtime = $summary.runtime_provenance
$safety = $summary.safety
$market = $summary.market
$decision = $summary.decision
$commandQueue = $summary.demo_command_queue

$snapshotAge = $null
if ($market -and $market.PSObject.Properties.Name -contains "snapshot_age_seconds") {
    $snapshotAge = $market.snapshot_age_seconds
} elseif ($summary.health -and $summary.health.PSObject.Properties.Name -contains "bridge_snapshot_age_seconds") {
    $snapshotAge = $summary.health.bridge_snapshot_age_seconds
}

Write-Host ("health: {0}" -f $summary.health)
Write-Host ("symbol: {0}" -f $summary.symbol)
Write-Host ("latest decision/action: {0}" -f $decision.action)
Write-Host ("runtime session id: {0}" -f $runtime.runtime_session_id)
Write-Host ("live execution allowed: {0}" -f $safety.live_execution_allowed)
Write-Host ("demo broker execution allowed: {0}" -f $safety.demo_execution_allowed)
Write-Host ("command queueing allowed: {0}" -f $safety.demo_command_queueing_allowed)
Write-Host ("demo command queue mode: {0}" -f $commandQueue.mode)
Write-Host ("MT5 snapshot age seconds: {0}" -f $(if ($null -ne $snapshotAge) { $snapshotAge } else { "unknown" }))
