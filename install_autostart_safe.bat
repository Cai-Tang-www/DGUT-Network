@echo off
setlocal
cd /d "%~dp0"

set "TASK_START=CampusLoginAutoLoopPy_OnStart"
set "TASK_LOGON=CampusLoginAutoLoopPy_OnLogon"
set "TASK_WATCHDOG=CampusLoginAutoLoopPy_Watchdog"
set "VBS=%~dp0start_loop_py_background.vbs"

if not exist "%VBS%" (
  echo [ERR] not found: %VBS%
  exit /b 1
)

set "TR=wscript.exe \"%VBS%\""

echo [INFO] Create startup task (SYSTEM)...
schtasks /Create /TN "%TASK_START%" /TR "%TR%" /SC ONSTART /RU SYSTEM /RL HIGHEST /F
if errorlevel 1 (
  echo [ERR] failed to create %TASK_START%
  exit /b 2
)

echo [INFO] Create logon task (current user)...
schtasks /Create /TN "%TASK_LOGON%" /TR "%TR%" /SC ONLOGON /RL HIGHEST /F
if errorlevel 1 (
  echo [ERR] failed to create %TASK_LOGON%
  exit /b 3
)

echo [INFO] Create watchdog task (every 5 min)...
schtasks /Create /TN "%TASK_WATCHDOG%" /TR "%TR%" /SC MINUTE /MO 5 /RL HIGHEST /F
if errorlevel 1 (
  echo [ERR] failed to create %TASK_WATCHDOG%
  exit /b 4
)

echo [OK] Installed 3 tasks.
echo [INFO] View:   schtasks /Query /TN "%TASK_START%" /V /FO LIST
echo [INFO] View:   schtasks /Query /TN "%TASK_LOGON%" /V /FO LIST
echo [INFO] View:   schtasks /Query /TN "%TASK_WATCHDOG%" /V /FO LIST
echo [INFO] Delete: schtasks /Delete /TN "%TASK_START%" /F
echo [INFO] Delete: schtasks /Delete /TN "%TASK_LOGON%" /F
echo [INFO] Delete: schtasks /Delete /TN "%TASK_WATCHDOG%" /F
exit /b 0
