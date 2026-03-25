param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$Reload
)

$ErrorActionPreference = "Stop"

# Always resolve paths from this script's directory.
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

# Prefer project venv, then fallback to workspace venv.
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
    Write-Host "[ERROR] Python executable not found in known virtual environments." -ForegroundColor Red
    Write-Host "Expected one of:" -ForegroundColor Yellow
    $PythonCandidates | ForEach-Object { Write-Host " - $_" }
    exit 1
}

# Stop old uvicorn/flowmind server instances to avoid port conflicts.
$old = Get-CimInstance Win32_Process |
    Where-Object { $_.Name -eq "python.exe" -and $_.CommandLine -match "uvicorn|flowmind:app" }

if ($old) {
    foreach ($p in $old) {
        Stop-Process -Id $p.ProcessId -Force
    }
    Start-Sleep -Seconds 1
    Write-Host ("[INFO] Stopped " + $old.Count + " old FlowMind server process(es).") -ForegroundColor Yellow
}

$args = @(
    "-m", "uvicorn",
    "flowmind:app",
    "--app-dir", $ProjectRoot,
    "--host", $HostName,
    "--port", "$Port"
)

if ($Reload.IsPresent) {
    $args += "--reload"
}

Write-Host "[INFO] Starting FlowMind server..." -ForegroundColor Cyan
Write-Host ("[INFO] URL: http://" + $HostName + ":" + $Port) -ForegroundColor Green
Write-Host ("[INFO] Python: " + $PythonExe) -ForegroundColor DarkGray
Write-Host "[INFO] Press Ctrl+C to stop." -ForegroundColor DarkGray

& $PythonExe @args
