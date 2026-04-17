@echo off
setlocal
cd /d "%~dp0"

:: 检查配置文件
if not exist "%~dp0config.yaml" (
  echo [ERR] 找不到 config.yaml
  pause
  exit /b 1
)

:: 直接用 Python 后台运行源码（无黑框）
echo [INFO] 正在启动校园网自动登录...
start /B pythonw.exe "%~dp0campus_login.py" --loop

echo [INFO] 已后台启动，不会显示窗口
exit