@echo off
setlocal
cd /d "%~dp0"

if not exist "%~dp0config.yaml" (
  echo [ERR] config.yaml not found. Please copy config.yaml.example to config.yaml first.
  pause
  exit /b 1
)

set "EXE_PATH=%~dp0campus_login.exe"
if not exist "%EXE_PATH%" set "EXE_PATH=%~dp0dist\campus_login.exe"
if not exist "%EXE_PATH%" (
  echo [ERR] campus_login.exe not found.
  echo [ERR] Expected: "%~dp0campus_login.exe" or "%~dp0dist\campus_login.exe"
  pause
  exit /b 1
)

echo [INFO] Starting: "%EXE_PATH%" --loop
"%EXE_PATH%" --loop

echo [ERR] process exited with code %errorlevel%
pause
