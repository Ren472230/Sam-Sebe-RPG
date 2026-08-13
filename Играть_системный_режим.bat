@echo off
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\windows\setup_and_run.ps1" -Action PlaySystems
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo Запуск завершился с ошибкой. Код: %EXIT_CODE%
  pause
)
exit /b %EXIT_CODE%
