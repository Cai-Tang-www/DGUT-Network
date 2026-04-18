@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "TASK_START=CampusLoginAutoLoopPy_OnStart_SYSTEM"
set "TASK_WATCHDOG=CampusLoginAutoLoopPy_Watchdog_SYSTEM"
set "VBS=%~dp0start_loop_py_background.vbs"

if not exist "%VBS%" (
  echo [ERR] not found: %VBS%
  exit /b 1
)

:: Require Administrator
net session >nul 2>nul
if not "%errorlevel%"=="0" (
  echo [ERR] Please run this bat as Administrator.
  exit /b 2
)

set "TR=wscript.exe \"%VBS%\""

echo [INFO] Creating SYSTEM ONSTART task...
schtasks /Create /TN "%TASK_START%" /TR "%TR%" /SC ONSTART /RU SYSTEM /RL HIGHEST /F
if errorlevel 1 (
  echo [ERR] failed to create %TASK_START%
  exit /b 3
)

echo [INFO] Creating SYSTEM watchdog task (every 5 min)...
schtasks /Create /TN "%TASK_WATCHDOG%" /TR "%TR%" /SC MINUTE /MO 5 /RU SYSTEM /RL HIGHEST /F
if errorlevel 1 (
  echo [ERR] failed to create %TASK_WATCHDOG%
  exit /b 4
)

echo [OK] Installed SYSTEM tasks.
echo [INFO] Run now:  schtasks /Run /TN "%TASK_START%"
echo [INFO] Check:    schtasks /Query /TN "%TASK_START%" /V /FO LIST
echo [INFO] Check:    schtasks /Query /TN "%TASK_WATCHDOG%" /V /FO LIST
echo [INFO] Delete:   schtasks /Delete /TN "%TASK_START%" /F
echo [INFO] Delete:   schtasks /Delete /TN "%TASK_WATCHDOG%" /F
exit /b 0
