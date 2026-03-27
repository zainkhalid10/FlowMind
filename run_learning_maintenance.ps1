param(
    [int]$NFeedback = 50,
    [int]$BackfillLimit = 0
)

$ErrorActionPreference = "Continue"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$PythonCandidates = @(
    (Join-Path $ProjectRoot ".venv\Scripts\python.exe"),
    "D:\fyp_phase2\.venv\Scripts\python.exe"
)

$PythonExe = $null
foreach ($candidate in $PythonCandidates) {
    if (Test-Path $candidate) {
        $PythonExe = $candidate
        break
    }
}

if (-not $PythonExe) {
    Write-Host "[ERROR] Python executable not found." -ForegroundColor Red
    exit 1
}

$ReportsDir = Join-Path $ProjectRoot "reports"
if (-not (Test-Path $ReportsDir)) {
    New-Item -ItemType Directory -Path $ReportsDir | Out-Null
}

$LogsDir = Join-Path $ReportsDir "logs"
if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir | Out-Null
}

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $LogsDir ("learning_maintenance_" + $ts + ".log")

$args = @(
    "scripts/learning_maintenance.py",
    "--n-feedback", "$NFeedback",
    "--backfill-limit", "$BackfillLimit"
)

Write-Host "[INFO] Running FlowMind learning maintenance..." -ForegroundColor Cyan
Write-Host ("[INFO] Python: " + $PythonExe) -ForegroundColor DarkGray
Write-Host ("[INFO] Log: " + $logFile) -ForegroundColor DarkGray

& $PythonExe @args 2>&1 | Tee-Object -FilePath $logFile

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Learning maintenance failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "[INFO] Learning maintenance completed successfully." -ForegroundColor Green
