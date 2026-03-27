param(
    [string]$TaskName = "FlowMind-LearningMaintenance",
    [string]$RunTime = "02:00"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runner = Join-Path $ProjectRoot "run_learning_maintenance.ps1"

if (-not (Test-Path $Runner)) {
    Write-Host "[ERROR] Missing runner script: $Runner" -ForegroundColor Red
    exit 1
}

$taskCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$Runner`""

schtasks /Create /SC DAILY /TN $TaskName /TR $taskCommand /ST $RunTime /F | Out-Null

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to create scheduled task." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "[INFO] Scheduled task created." -ForegroundColor Green
Write-Host ("[INFO] Task Name: " + $TaskName) -ForegroundColor DarkGray
Write-Host ("[INFO] Time: " + $RunTime + " daily") -ForegroundColor DarkGray
Write-Host "[INFO] To run immediately: schtasks /Run /TN $TaskName" -ForegroundColor DarkGray
