param(
    [switch]$Reset,
    [switch]$PromptForOpenAIKey
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.12+ was not found. Install Python, reopen this launcher, and try again."
}

$PythonConstraints = Join-Path $Root "constraints/python-3.12.txt"
python -c "import samseberpg" 2>$null
if ($LASTEXITCODE -ne 0) {
    if (-not (Test-Path $PythonConstraints)) {
        throw "Python constraints file was not found: $PythonConstraints"
    }
    Write-Host "Installing local Python package and constrained test/runtime dependencies..."
    python -m pip install -c $PythonConstraints -e ".[dev]"
    if ($LASTEXITCODE -ne 0) {
        throw "Python dependency installation failed. Review the pip output above."
    }
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "Node.js 22+ / npm was not found. Install Node.js, reopen this launcher, and try again."
}

$WebNodeModules = Join-Path $Root "web/node_modules"
$WebLockfile = Join-Path $Root "web/package-lock.json"
if (-not (Test-Path $WebNodeModules)) {
    Write-Host "Installing web dependencies..."
    Push-Location (Join-Path $Root "web")
    try {
        if (Test-Path $WebLockfile) {
            npm ci --no-audit --no-fund
        }
        else {
            Write-Warning "web/package-lock.json is missing; falling back to npm install for this local checkout."
            npm install --no-audit --no-fund
        }
        if ($LASTEXITCODE -ne 0) {
            throw "Web dependency installation failed. Review the npm output above."
        }
    }
    finally {
        Pop-Location
    }
}

if ($PromptForOpenAIKey -and -not $env:OPENAI_API_KEY) {
    Write-Host ""
    Write-Host "OpenAI NPC dialogue key is not configured for this process."
    $SecureKey = Read-Host "Paste OpenAI API key (input is hidden)" -AsSecureString
    $KeyPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureKey)
    try {
        $PlainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($KeyPtr)
        if (-not [string]::IsNullOrWhiteSpace($PlainKey)) {
            $env:OPENAI_API_KEY = $PlainKey
            Write-Host "OpenAI NPC dialogue: enabled for this playtest session."
        }
        else {
            Write-Host "OpenAI NPC dialogue: fallback mode (no key supplied)."
        }
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($KeyPtr)
        Remove-Variable PlainKey -ErrorAction SilentlyContinue
        Remove-Variable SecureKey -ErrorAction SilentlyContinue
    }
}
elseif ($env:OPENAI_API_KEY) {
    Write-Host "OpenAI NPC dialogue: enabled from existing environment."
}

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
