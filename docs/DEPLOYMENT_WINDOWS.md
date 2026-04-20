# Windows 部署（后台无界面）

## 1. 准备文件

建议至少准备以下文件：

- `campus_login.py` 或 `dist\campus_login.exe`
- `config.yaml`
- `start_loop_py_background.vbs`
- `start_loop_py_background.bat`

若使用管理员 SYSTEM 开机任务，还需要：

- `install_onstart_system.bat`

## 2. 手动后台启动（无窗口）

```powershell
cmd /c .\start_loop_py_background.bat
```

说明：

- 启动入口由 `start_loop_py_background.vbs` 间接调用 `start_loop_py_background.bat`
- `start_loop_py_background.bat` 会自动设置 `CAMPUS_CONFIG_FILE`
- 循环模式已内置单实例锁，重复触发不会多开

## 3. 安装开机自启任务（管理员，未登录也启动）

以管理员身份打开终端，执行：

```powershell
.\install_onstart_system.bat
```

默认创建任务：

- `CampusLoginAutoLoopPy_OnStart_SYSTEM`（系统启动触发）
- `CampusLoginAutoLoopPy_Watchdog_SYSTEM`（每 5 分钟兜底）

## 4. 任务运维与校验

查看任务：

```powershell
schtasks /Query /TN "CampusLoginAutoLoopPy_OnStart_SYSTEM" /V /FO LIST
schtasks /Query /TN "CampusLoginAutoLoopPy_Watchdog_SYSTEM" /V /FO LIST
```

手动触发验证：

```powershell
schtasks /Run /TN "CampusLoginAutoLoopPy_OnStart_SYSTEM"
```

查看运行中的进程（py 版）：

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like "*campus_login.py*" -and $_.CommandLine -like "*--loop*" } |
  Select-Object ProcessId,Name,CommandLine
```

查看运行中的进程（exe 版）：

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -eq "campus_login.exe" } |
  Select-Object ProcessId,Name,CommandLine
```

删除任务：

```powershell
schtasks /Delete /TN "CampusLoginAutoLoopPy_OnStart_SYSTEM" /F
schtasks /Delete /TN "CampusLoginAutoLoopPy_Watchdog_SYSTEM" /F
```

## 5. 日志排障

默认日志文件：`./campus_login.log`（相对 `config.yaml` 所在目录）

建议重点关注：

- `DNS失败`
- `超时`
- `TLS握手失败`
- `未获取到 queryString`
