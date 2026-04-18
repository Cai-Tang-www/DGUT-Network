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

## 快速开始

### 1. 配置账号

```powershell
copy config.yaml.example config.yaml
```

编辑 `config.yaml`：

- `user_id`：学号/账号
- `password`：密码
- `base_url`：认证门户地址（DGUT 默认已内置）

### 2. 源码运行

安装依赖：

```powershell
pip install requests urllib3 curl_cffi
```

单次检测登录：

```powershell
py campus_login.py
```

循环模式：

```powershell
py campus_login.py --loop
```

自定义循环间隔：

```powershell
py campus_login.py --loop --interval 30
```

### 3. 打包版运行（无 Python 环境）

```powershell
.\dist\campus_login.exe --loop
```

## Windows 后台无界面运行（推荐）

### 方案 A：管理员模式（开机未登录也启动）

右键“以管理员身份运行”：

```powershell
.\install_onstart_system.bat
```

会创建 2 个 SYSTEM 任务：

- `CampusLoginAutoLoopPy_OnStart_SYSTEM`（开机触发）
- `CampusLoginAutoLoopPy_Watchdog_SYSTEM`（每 5 分钟兜底）

查看任务：

```powershell
schtasks /Query /TN "CampusLoginAutoLoopPy_OnStart_SYSTEM" /V /FO LIST
schtasks /Query /TN "CampusLoginAutoLoopPy_Watchdog_SYSTEM" /V /FO LIST
```

删除任务：

```powershell
schtasks /Delete /TN "CampusLoginAutoLoopPy_OnStart_SYSTEM" /F
schtasks /Delete /TN "CampusLoginAutoLoopPy_Watchdog_SYSTEM" /F
```

### 方案 B：受限权限模式（登录后启动）

如果机器策略不允许创建 SYSTEM 任务，可使用：

```powershell
.\install_autostart_safe.bat
```

该脚本会创建登录触发 + 看门狗任务；你也可以仅保留 Startup + `HKCU\Run` 方式。

### 启动入口

- `start_loop_py_background.vbs`（隐藏运行）
- `start_loop_py_background.bat`（后台启动 `campus_login.py --loop`）

当前代码已内置循环单实例锁，多触发也只会保留一个循环实例。

## 健康检查（不断网）

```powershell
.\check_runtime_no_disconnect.bat
```

会输出到 `healthcheck.log`，用于验证：

- 依赖与配置可用
- 单次检测流程可执行
- 当前机器后台 Python 进程快照

## 日志与排障

- 日志路径由 `config.yaml` 中 `log_file` 控制（支持轮转）。
- 常见关键字：`DNS失败`、`超时`、`TLS握手失败`、`未获取到 queryString`。

## 文档

- 配置项说明：[`docs/CONFIG.md`](./docs/CONFIG.md)
- Windows 部署说明：[`docs/DEPLOYMENT_WINDOWS.md`](./docs/DEPLOYMENT_WINDOWS.md)
- 自启动任务说明：[`AUTOSTART_TASK.md`](./AUTOSTART_TASK.md)

## 许可证

本项目使用 Apache License 2.0，见 [`LICENSE`](./LICENSE)。
