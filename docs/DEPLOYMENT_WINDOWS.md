# Windows 部署（后台无界面）

## 1. 准备文件

建议至少准备以下文件：

- `campus_login.exe`（onefile 打包产物）
- `config.yaml`
- `start_hidden.ps1`
- `install_startup_task.ps1`

## 2. 手动后台启动（无窗口）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_hidden.ps1
```

说明：

- 脚本会优先查找 `.\campus_login.exe`，找不到则尝试 `.\dist\campus_login.exe`
- 会自动设置 `CAMPUS_CONFIG_FILE` 指向同目录 `config.yaml`
- 已运行时会避免重复拉起

## 3. 安装开机自启任务

以管理员身份打开 PowerShell，执行：

```powershell
.\install_startup_task.ps1
```

默认创建任务：

- 任务名：`CampusLoginAutoLoop`
- 触发器：系统启动（`AtStartup`）
- 运行用户：`SYSTEM`
- 运行权限：Highest
- 运行方式：无论用户是否登录都运行

## 4. 任务运维

查看任务：

```powershell
Get-ScheduledTask -TaskName "CampusLoginAutoLoop"
```

查看运行中的进程：

```powershell
Get-CimInstance Win32_Process -Filter "Name='campus_login.exe'" |
  Select-Object ProcessId,ExecutablePath,CommandLine
```

删除任务：

```powershell
Unregister-ScheduledTask -TaskName "CampusLoginAutoLoop" -Confirm:$false
```

## 5. 日志排障

默认日志文件：`./campus_login.log`（相对 `config.yaml` 所在目录）

建议重点关注：

- `DNS失败`
- `超时`
- `TLS握手失败`
- `未获取到 queryString`

