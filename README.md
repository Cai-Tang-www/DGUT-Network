# 东莞理工学院校园网自动化脚本（DGUT-Network）

> 面向东莞理工学院（DGUT）校园网认证场景的自动登录脚本，支持自动检测未联网、自动抓取会话参数、自动认证、后台循环保活。

## 免责声明

- 本项目仅用于个人网络运维与学习研究。
- 请遵守学校与网络服务提供方相关规定。
- 使用本项目造成的任何后果由使用者自行承担。

## 项目简介

这个项目用于解决校园网 portal 认证中的常见问题：

- 认证劫持页面返回 `200`，导致“只看状态码”的联网检测误判。
- `queryString` 属于动态会话参数，不能长期硬编码。
- 部分门户环境下 HTTPS/TLS 兼容性较差，默认请求库可能握手失败。

脚本会在检测到未联网或被认证劫持时，自动尝试抓取当前会话 `queryString`，调用 `pageInfo`，并提交登录请求（支持 RSA 模式）。

## 适用范围

- 已针对东莞理工学院（DGUT）校园网流程适配。
- 也可用于其他高校中同类 `portal/eportal` 认证系统。
- 迁移到其他学校时，通常只需调整：`base_url`、`captive_host`、`captive_path`，必要时补充字段适配。

## 功能特性

- 识别 portal 劫持的联网检测（不只依赖 HTTP `200`）
- 自动抓取当次会话 `queryString`
- 自动获取 `pageInfo` 并按需执行 RSA 登录参数加密
- 支持 YAML 配置 + 环境变量覆盖
- 支持循环模式（`--loop`）
- 支持 `curl_cffi` 兼容 TLS 握手
- 支持日志文件输出与轮转
- 支持 Windows 后台无界面启动与开机自启动

## 上线操作清单（建议按顺序执行）

### 1. 基础配置

```powershell
copy config.yaml.example config.yaml
```

编辑 `config.yaml`（至少填写）：

- `user_id`：学号/账号
- `password`：密码
- `base_url`：认证门户地址（DGUT 默认已内置）

### 2. 选择运行方式（py / exe）

#### A) `py` 方式（调试方便）

安装依赖（注意必须和 `py` 同环境）：

```powershell
py -m pip install requests urllib3 curl_cffi
```

单次运行：

```powershell
py campus_login.py
```

循环运行：

```powershell
py campus_login.py --loop
```

#### B) `exe` 方式（服务器更稳，不依赖 Python）

```powershell
.\dist\campus_login.exe --loop
```

说明：`exe` 会读取同目录 `config.yaml`（或 `CAMPUS_CONFIG_FILE` 指定路径）。

## 自动启动（管理员模式，开机未登录也启动）

### 1. py 版 SYSTEM 任务（推荐）

管理员终端执行：

```powershell
.\install_onstart_system.bat
```

会创建：

- `CampusLoginAutoLoopPy_OnStart_SYSTEM`（开机触发）
- `CampusLoginAutoLoopPy_Watchdog_SYSTEM`（每 5 分钟兜底）

### 2. exe 版 SYSTEM 任务（可选）

如果你改用 `exe` 常驻，管理员终端可直接执行：

```powershell
schtasks /Create /TN "CampusLoginAutoLoopExe_OnStart_SYSTEM" /TR "\"G:\校园网日志\dist\campus_login.exe\" --loop" /SC ONSTART /RU SYSTEM /RL HIGHEST /F
schtasks /Create /TN "CampusLoginAutoLoopExe_Watchdog_SYSTEM" /TR "\"G:\校园网日志\dist\campus_login.exe\" --loop" /SC MINUTE /MO 5 /RU SYSTEM /RL HIGHEST /F
```

## 如何确认任务已创建且有效

### 1. 查任务详情

```powershell
schtasks /Query /TN "CampusLoginAutoLoopPy_OnStart_SYSTEM" /V /FO LIST
schtasks /Query /TN "CampusLoginAutoLoopPy_Watchdog_SYSTEM" /V /FO LIST
```

重点看：

- `作为用户运行: SYSTEM`
- `计划任务状态: 已启用`
- `上次结果: 0` 或 `0x0`

### 2. 手动触发一次验证

```powershell
schtasks /Run /TN "CampusLoginAutoLoopPy_OnStart_SYSTEM"
Start-Sleep -Seconds 5
```

### 3. 检查后台进程

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like "*campus_login.py*" -and $_.CommandLine -like "*--loop*" } |
  Select-Object ProcessId,Name,CommandLine
```

若为 `exe` 方案，检查：

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -eq "campus_login.exe" } |
  Select-Object ProcessId,Name,CommandLine
```

### 4. 检查日志是否持续刷新

```powershell
Get-Content -Tail 80 .\campus_login.log
Get-Content -Tail 80 .\runner.log
```

## 受限权限模式（无法创建 SYSTEM 任务时）

```powershell
.\install_autostart_safe.bat
```

该模式为“登录后启动 + 看门狗”。  
若你已经切到 SYSTEM 模式，建议移除 Startup/HKCU 启动项，避免双触发噪音。

## 健康检查（不断网）

```powershell
.\check_runtime_no_disconnect.bat
```

输出文件：

- `healthcheck.log`（单次自检结果）
- `campus_login.log`（主循环日志）

## 常见故障排查

- `ModuleNotFoundError: requests`：使用 `py -m pip install ...`，不要单独 `pip install`
- `Access is denied`（创建任务）：需管理员权限，且命令在管理员终端执行
- 能跑但看不到进程：Win10 任务管理器看“详细信息”中的 `pythonw.exe/pyw.exe`
- 多进程担忧：代码含单实例锁，重复触发会自动退出后续实例

## 文档

- 配置项说明：[`docs/CONFIG.md`](./docs/CONFIG.md)
- Windows 部署说明：[`docs/DEPLOYMENT_WINDOWS.md`](./docs/DEPLOYMENT_WINDOWS.md)
- 自启动任务说明：[`AUTOSTART_TASK.md`](./AUTOSTART_TASK.md)

## 许可证

本项目使用 Apache License 2.0，见 [`LICENSE`](./LICENSE)。
