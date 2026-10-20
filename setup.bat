@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title DGUT-Network setup

echo ============================================================
echo   DGUT campus network auto-login  :  setup
echo ============================================================
echo.

net session >nul 2>nul
if not "%errorlevel%"=="0" (
  echo [ERR] Administrator required.
  echo       Right-click setup.bat, then choose "Run as administrator".
  echo.
  pause
  exit /b 2
)

rem ---------------- 1) locate python ----------------
set "PYEXE="
set "PYWEXE="

if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"  set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" set "PYWEXE=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"

if not defined PYEXE for /f "delims=" %%I in ('where python 2^>nul') do if not defined PYEXE set "PYEXE=%%I"
if not defined PYWEXE for /f "delims=" %%I in ('where pythonw 2^>nul') do if not defined PYWEXE set "PYWEXE=%%I"

if not defined PYEXE (
  echo [ERR] Python not found in PATH.
  echo       Install Python 3.9+ from python.org and tick "Add python.exe to PATH".
  echo.
  pause
  exit /b 3
)

echo [OK] python  : !PYEXE!
if defined PYWEXE (
  echo [OK] pythonw : !PYWEXE!
) else (
  echo [WARN] pythonw.exe not found - the scheduled task may fail to start.
)

rem ---------------- 2) dependencies ----------------
echo.
"!PYEXE!" -c "import requests, urllib3, curl_cffi" >nul 2>nul
if errorlevel 1 (
  echo [..] installing requests / urllib3 / curl_cffi ...
  "!PYEXE!" -m pip install --disable-pip-version-check requests urllib3 curl_cffi
  if errorlevel 1 (
    echo [WARN] pip install failed. Install manually:
    echo        "!PYEXE!" -m pip install requests urllib3 curl_cffi
  )
) else (
  echo [OK] dependencies present
)

rem ---------------- 3) config ----------------
set "RECONF=N"
if exist "config.yaml" (
  echo.
  echo [INFO] config.yaml already exists.
  set /p "RECONF=Reconfigure it? [y/N]: "
)

if /i "!RECONF!"=="y" goto :write_config
if not exist "config.yaml" goto :write_config
echo [OK] keep existing config.yaml
goto :install_task

:write_config
echo.
echo Enter your campus account. Password is stored locally in config.yaml only.
set "CU_USER="
set "CU_PASS="
set /p "CU_USER=Student ID : "
set /p "CU_PASS=Password   : "
if not defined CU_USER goto :cfg_fail
if not defined CU_PASS goto :cfg_fail

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_config.ps1"
if not exist "config.yaml" goto :cfg_fail
goto :install_task

:cfg_fail
echo.
echo [ERR] config.yaml was not generated. Aborted.
pause
exit /b 4

rem ---------------- 4) scheduled task ----------------
:install_task
echo.
echo [..] registering logon task (elevated, current user) ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0switch_to_logon_task.ps1"
if errorlevel 1 (
  echo.
  echo [ERR] task registration failed. See messages above.
  pause
  exit /b 5
)

rem ---------------- 5) verify ----------------
echo.
echo ================ status ================
powershell -NoProfile -Command "$t=Get-ScheduledTask -TaskName 'CampusLoginAutoLoopPy_Logon' -ErrorAction SilentlyContinue; if($t){'task    : '+$t.TaskName+'  state='+$t.State+'  level='+$t.Principal.RunLevel}else{'task    : NOT FOUND'}; $p=Get-Process pythonw -ErrorAction SilentlyContinue; if($p){'process : pythonw PID='+($p.Id -join ',')}else{'process : none'}; if(Test-Path 'config.yaml'){'config  : config.yaml'}"
Get-Content "campus_login.log" -Tail 4 -ErrorAction SilentlyContinue
echo ========================================
echo.
echo Done. Log file: %~dp0campus_login.log
echo If the log keeps saying "未联网", see README troubleshooting.
echo.
pause
exit /b 0
