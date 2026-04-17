@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "SCRIPT=%~dp0campus_login.py"
set "CFG=%~dp0config.yaml"
set "HC_LOG=%~dp0healthcheck.log"

echo ==================================================>>"%HC_LOG%"
echo [%date% %time%] health check start>>"%HC_LOG%"

if not exist "%SCRIPT%" (
  echo [%date% %time%] ERROR script not found: %SCRIPT%>>"%HC_LOG%"
  exit /b 1
)
if not exist "%CFG%" (
  echo [%date% %time%] ERROR config not found: %CFG%>>"%HC_LOG%"
  exit /b 1
)

set "PY_CMD="
where py >nul 2>nul
if %errorlevel%==0 set "PY_CMD=py"
if not defined PY_CMD (
  where python >nul 2>nul
  if %errorlevel%==0 set "PY_CMD=python"
)
if not defined PY_CMD (
  echo [%date% %time%] ERROR python launcher not found>>"%HC_LOG%"
  exit /b 2
)

set "CAMPUS_CONFIG_FILE=%CFG%"
echo [%date% %time%] INFO run once with %PY_CMD%>>"%HC_LOG%"
%PY_CMD% "%SCRIPT%" 1>>"%HC_LOG%" 2>>&1
set "RC=!ERRORLEVEL!"
echo [%date% %time%] INFO run_once exitcode=!RC!>>"%HC_LOG%"
echo [INFO] run_once exitcode=!RC!

echo [%date% %time%] INFO process snapshot>>"%HC_LOG%"
tasklist /FI "IMAGENAME eq python.exe" /FO TABLE >>"%HC_LOG%"
tasklist /FI "IMAGENAME eq pythonw.exe" /FO TABLE >>"%HC_LOG%"
tasklist /FI "IMAGENAME eq py.exe" /FO TABLE >>"%HC_LOG%"
tasklist /FI "IMAGENAME eq pyw.exe" /FO TABLE >>"%HC_LOG%"

echo [%date% %time%] health check done>>"%HC_LOG%"
exit /b 0
