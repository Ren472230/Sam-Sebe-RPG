param(
    [switch]$Reset
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if ($Reset) {
    python scripts/reset_stream_slice.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

python scripts/stream_preflight.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Stream Slice URL: http://127.0.0.1:5173/?stream=1"
Write-Host "Backend DB: data/stream-slice.sqlite3"
Write-Host "Fixed opening clock: 2026-08-24 17:00 UTC"
Write-Host "Ctrl+C stops the web server; backend is stopped automatically."
Write-Host ""

$Backend = Start-Process python -ArgumentList @("scripts/run_stream_slice.py") -PassThru -NoNewWindow
try {
    Start-Sleep -Milliseconds 800
    Push-Location (Join-Path $Root "web")
    try {
        npm run dev -- --host 127.0.0.1 --port 5173
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($Backend -and -not $Backend.HasExited) {
        Stop-Process -Id $Backend.Id -Force
    }
}
