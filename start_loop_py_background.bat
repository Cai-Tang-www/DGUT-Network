@echo off
setlocal
cd /d "%~dp0"

set "SCRIPT=%~dp0campus_login.py"
set "CFG=%~dp0config.yaml"
set "RUN_LOG=%~dp0runner.log"

if not exist "%SCRIPT%" (
  echo [%date% %time%] ERROR script not found: %SCRIPT%>>"%RUN_LOG%" 2>nul
  exit /b 1
)
if not exist "%CFG%" (
  echo [%date% %time%] ERROR config not found: %CFG%>>"%RUN_LOG%" 2>nul
  exit /b 1
)

set "PY_CMD="

where pyw >nul 2>nul
if %errorlevel%==0 set "PY_CMD=pyw"

if not defined PY_CMD (
  where pythonw >nul 2>nul
  if %errorlevel%==0 set "PY_CMD=pythonw"
)

if not defined PY_CMD (
  where py >nul 2>nul
  if %errorlevel%==0 set "PY_CMD=py"
)

if not defined PY_CMD (
  where python >nul 2>nul
  if %errorlevel%==0 set "PY_CMD=python"
)

if not defined PY_CMD (
  for /f "delims=" %%I in ('where /r "C:\Users" pythonw.exe 2^>nul') do (
    set "PY_CMD=%%~fI"
    goto :py_found
  )
)

if not defined PY_CMD (
  for /f "delims=" %%I in ('where /r "C:\Users" python.exe 2^>nul') do (
    set "PY_CMD=%%~fI"
    goto :py_found
  )
)

:py_found
if not defined PY_CMD (
  echo [%date% %time%] ERROR python launcher not found>>"%RUN_LOG%" 2>nul
  exit /b 2
)

set "CAMPUS_CONFIG_FILE=%CFG%"

echo [%date% %time%] INFO start with %PY_CMD%>>"%RUN_LOG%" 2>nul

if /i "%PY_CMD%"=="pyw" (
  start "" /min pyw "%SCRIPT%" --loop
) else if /i "%PY_CMD%"=="pythonw" (
  start "" /min pythonw "%SCRIPT%" --loop
) else if /i "%PY_CMD%"=="py" (
  start "" /min py "%SCRIPT%" --loop
) else if /i "%PY_CMD%"=="python" (
  start "" /min python "%SCRIPT%" --loop
) else (
  start "" /min "%PY_CMD%" "%SCRIPT%" --loop
)

exit /b 0
