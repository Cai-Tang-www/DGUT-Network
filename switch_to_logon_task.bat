@echo off
setlocal EnableExtensions
cd /d "%~dp0"

net session >nul 2>nul
if not "%errorlevel%"=="0" (
  echo [ERR] Administrator required.
  echo       Right-click this file and choose "Run as administrator".
  echo.
  pause
  exit /b 2
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0switch_to_logon_task.ps1"

echo.
echo Done. Press any key to close.
pause >nul
exit /b 0
