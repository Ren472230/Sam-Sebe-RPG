param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("PlayFounder", "PlaySystems", "ResetSave")]
    [string]$Action
)

$ErrorActionPreference = "Stop"
$LauncherContractVersion = "1"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$VenvDir = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvGame = Join-Path $VenvDir "Scripts\sam-sebe-rpg.exe"
$StampPath = Join-Path $VenvDir ".sam-sebe-launcher-version"
$PlaytestsDir = Join-Path $RepoRoot "playtests"
$FounderDb = Join-Path $PlaytestsDir "founder-free.db"
$SystemsDb = Join-Path $PlaytestsDir "founder-systems.db"

function Test-Python312 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Executable,
        [string[]]$PrefixArgs = @()
    )

    try {
        $probe = 'import sys; raise SystemExit(sys.version_info < (3, 12))'
        & $Executable @PrefixArgs -c $probe 2>$null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
}

function Find-CompatiblePython {
    $candidates = @(
        [pscustomobject]@{ Executable = "py"; PrefixArgs = @("-3.12"); Label = "py -3.12" },
        [pscustomobject]@{ Executable = "python"; PrefixArgs = @(); Label = "python" },
        [pscustomobject]@{ Executable = "python3"; PrefixArgs = @(); Label = "python3" }
    )

    foreach ($candidate in $candidates) {
        if (-not (Get-Command $candidate.Executable -ErrorAction SilentlyContinue)) {
            continue
        }
        if (Test-Python312 -Executable $candidate.Executable -PrefixArgs $candidate.PrefixArgs) {
            return $candidate
        }
    }
    return $null
}

function Ensure-Venv {
    param(
        [Parameter(Mandatory = $true)]
        $PythonCommand
    )

    if (Test-Path -LiteralPath $VenvPython) {
        if (Test-Python312 -Executable $VenvPython) {
            return
        }
        Write-Host "Локальное окружение .venv использует неподходящий Python. Пересоздаю только .venv..." -ForegroundColor Yellow
        Remove-Item -LiteralPath $VenvDir -Recurse -Force
    }

    Write-Host "Создаю локальное окружение .venv на Python 3.12+..."
    & $PythonCommand.Executable @($PythonCommand.PrefixArgs) -m venv $VenvDir
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $VenvPython)) {
        throw "Не удалось создать .venv."
    }
}

function Ensure-GameInstalled {
    $stampMatches = $false
    if (Test-Path -LiteralPath $StampPath) {
        $stampMatches = ((Get-Content -LiteralPath $StampPath -Raw).Trim() -eq $LauncherContractVersion)
    }

    if ((Test-Path -LiteralPath $VenvGame) -and $stampMatches) {
        return
    }

    Write-Host "Устанавливаю Sam-Sebe-RPG в локальное окружение..."
    Push-Location $RepoRoot
    try {
        & $VenvPython -m pip install -e .
        if ($LASTEXITCODE -ne 0) {
            throw "pip install -e . завершился с ошибкой."
        }
    }
    finally {
        Pop-Location
    }

    if (-not (Test-Path -LiteralPath $VenvGame)) {
        throw "После установки не найден .venv\Scripts\sam-sebe-rpg.exe."
    }
    Set-Content -LiteralPath $StampPath -Value $LauncherContractVersion -Encoding ASCII
}

function Get-OllamaModels {
    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $ollama) {
        return @()
    }

    $OllamaCommand = $ollama.Source
    try {
        $lines = & $OllamaCommand list 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $lines) {
            Write-Host "Ollama найдена, но список локальных моделей недоступен. Проверь, что Ollama запущена." -ForegroundColor Yellow
            return @()
        }
    }
    catch {
        Write-Host "Ollama найдена, но не отвечает. Проверь, что приложение Ollama запущено." -ForegroundColor Yellow
        return @()
    }

    $models = @()
    foreach ($line in ($lines | Select-Object -Skip 1)) {
        $trimmed = [string]$line
        if ([string]::IsNullOrWhiteSpace($trimmed)) {
            continue
        }
        $name = ($trimmed.Trim() -split "\s+")[0]
        if ($name) {
            $models += $name
        }
    }
    return @($models | Select-Object -Unique)
}

function Resolve-FounderModel {
    param(
        [string[]]$Models
    )

    $configured = $env:SAM_SEBE_OLLAMA_MODEL
    if ($configured) {
        if ($Models -contains $configured) {
            Write-Host "Использую настроенную Ollama-модель: $configured"
            return $configured
        }
        Write-Host "SAM_SEBE_OLLAMA_MODEL=$configured указана, но такой локальной модели сейчас нет." -ForegroundColor Yellow
        return $null
    }

    if ($Models.Count -eq 0) {
        return $null
    }
    if ($Models.Count -eq 1) {
        Write-Host "Найдена локальная Ollama-модель: $($Models[0])"
        return $Models[0]
    }

    Write-Host "Найдено несколько локальных Ollama-моделей:"
    for ($i = 0; $i -lt $Models.Count; $i++) {
        Write-Host ("  {0}. {1}" -f ($i + 1), $Models[$i])
    }
    $choice = Read-Host "Выбери номер модели для founder-режима"
    $number = 0
    if (-not [int]::TryParse($choice, [ref]$number)) {
        Write-Host "Номер не распознан." -ForegroundColor Yellow
        return $null
    }
    if ($number -lt 1 -or $number -gt $Models.Count) {
        Write-Host "Такого номера в списке нет." -ForegroundColor Yellow
        return $null
    }
    return $Models[$number - 1]
}

function Start-Game {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("founder", "systems")]
        [string]$Mode,
        [string]$Model
    )

    if (-not (Test-Path -LiteralPath $PlaytestsDir)) {
        New-Item -ItemType Directory -Path $PlaytestsDir | Out-Null
    }

    if ($Mode -eq "systems") {
        Write-Host "Запускаю системный режим. Сохранение: playtests\founder-systems.db" -ForegroundColor Cyan
        & $VenvGame --mode systems --db $SystemsDb
        return $LASTEXITCODE
    }

    $gameArgs = @("--mode", "founder", "--db", $FounderDb, "--ollama-model", $Model)
    if ($env:SAM_SEBE_OLLAMA_URL) {
        $gameArgs += @("--ollama-url", $env:SAM_SEBE_OLLAMA_URL)
    }
    Write-Host "Запускаю founder-режим. Сохранение: playtests\founder-free.db" -ForegroundColor Cyan
    Write-Host "Свободный ввод: Ollama $Model" -ForegroundColor Cyan
    & $VenvGame @gameArgs
    return $LASTEXITCODE
}

function Reset-PlaytestSave {
    Write-Host "Какой тестовый мир сбросить?"
    Write-Host "  1. playtests\founder-free.db"
    Write-Host "  2. playtests\founder-systems.db"
    Write-Host "  3. отмена"
    $choice = Read-Host "Выбор"

    switch ($choice) {
        "1" { $target = $FounderDb }
        "2" { $target = $SystemsDb }
        default {
            Write-Host "Сброс отменён."
            return 0
        }
    }

    Write-Host "Будет удалён только этот файл: $target" -ForegroundColor Yellow
    $confirmation = Read-Host "Для подтверждения введи DELETE"
    if ($confirmation -ne "DELETE") {
        Write-Host "Сброс отменён."
        return 0
    }

    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Force
        Write-Host "Тестовый мир удалён. Следующий запуск создаст новый." -ForegroundColor Green
    }
    else {
        Write-Host "Такого save-файла пока нет. Ничего не удалено."
    }
    return 0
}

function Prepare-GameRuntime {
    $pythonCommand = Find-CompatiblePython
    if (-not $pythonCommand) {
        Write-Host "Python 3.12+ не найден." -ForegroundColor Red
        Write-Host "Лаунчер ничего не устанавливал. Установи Python 3.12 или новее, затем снова запусти .bat-файл."
        return $false
    }

    Write-Host "Python найден: $($pythonCommand.Label)"
    Ensure-Venv -PythonCommand $pythonCommand
    Ensure-GameInstalled
    return $true
}

try {
    if ($Action -eq "ResetSave") {
        exit (Reset-PlaytestSave)
    }

    if (-not (Prepare-GameRuntime)) {
        exit 10
    }

    if ($Action -eq "PlaySystems") {
        $code = Start-Game -Mode "systems"
        if ($null -eq $code) { $code = 0 }
        exit $code
    }

    $models = @(Get-OllamaModels)
    $model = Resolve-FounderModel -Models $models
    if ($model) {
        $code = Start-Game -Mode "founder" -Model $model
        if ($null -eq $code) { $code = 0 }
        exit $code
    }

    Write-Host "Founder-режим со свободным вводом требует уже установленную и запущенную Ollama с локальной моделью." -ForegroundColor Yellow
    Write-Host "Лаунчер не устанавливает Ollama и не скачивает модели автоматически."
    $fallback = Read-Host "Запустить системный режим сейчас? [Y/N]"
    if ($fallback -match '^[Yy]$') {
        $code = Start-Game -Mode "systems"
        if ($null -eq $code) { $code = 0 }
        exit $code
    }

    Write-Host "Запуск отменён."
    exit 0
}
catch {
    Write-Host "Ошибка запуска Sam-Sebe-RPG:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 20
}
