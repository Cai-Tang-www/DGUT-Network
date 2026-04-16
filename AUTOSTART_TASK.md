# Campus Login 后台自启动（无界面）

## 1) 安装开机自启动任务（管理员 PowerShell）

```powershell
Set-Location "G:\校园网日志"
.\install_startup_task.ps1
```

默认任务名：`CampusLoginAutoLoop`，触发器：系统启动（`AtStartup`），账户：`SYSTEM`，权限：最高。

## 2) 运维命令

查看任务：

```powershell
Get-ScheduledTask -TaskName "CampusLoginAutoLoop"
```

删除任务：

```powershell
Unregister-ScheduledTask -TaskName "CampusLoginAutoLoop" -Confirm:$false
```

## 3) 日志文件

日志配置在 `config.yaml`：

- `log_file`
- `log_level`
- `log_max_size_mb`
- `log_backup_count`

默认日志文件：`G:\校园网日志\campus_login.log`
