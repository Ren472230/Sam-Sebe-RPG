@echo off
setlocal
cd /d "%~dp0"

start "Sam-Sebe-RPG server" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RUN_STREAM_SLICE.ps1" -Reset -PromptForOpenAIKey

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$url='http://127.0.0.1:5173/'; for($i=0;$i -lt 120;$i++){try{$response=Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 1;if($response.StatusCode -eq 200){Start-Process $url;exit 0}}catch{};Start-Sleep -Milliseconds 500};Write-Host 'Game server did not become ready.';exit 1"

endlocal
