# DGUT-Network

> 校园网自动认证脚本（DGUT 优先适配），支持未联网状态自动抓取会话参数、自动登录、循环保活检测，以及 Windows 开机后台运行。

## 免责声明

- 本项目仅用于个人网络运维与学习研究。
- 请遵守学校与网络服务提供方的相关规定。
- 使用本项目造成的后果由使用者自行承担。

## 项目简介

本仓库用于解决校园网认证场景中的两个常见问题：

- 网络被认证页劫持时，HTTP 状态码可能仍是 `200`，导致普通“联网检测”误判。
- 登录参数中的 `queryString` 会话值是动态的，不能长期硬编码。

脚本会在检测到“未真正联网”后，自动尝试抓取当前会话 `queryString`，获取 `pageInfo`，并按门户要求提交登录请求（支持 RSA 模式）。

## 适用范围

- 已在东莞理工学院（DGUT）网络环境验证。
- 同样适用于其他高校中“同类 portal/eportal 认证流程”的校园网。
- 若其他学校接口字段不同，通常只需调整 `base_url` / `captive_host` / `captive_path` 及少量请求参数。
- 如果目标门户没有 `pageInfo` 或使用完全不同的加密方案，需要按学校页面 JS 再做适配。

## 功能特性

- 自动联网检测（识别 portal 劫持，不只看 `200`）
- 自动抓取当次会话 `queryString`
- 自动调用 `pageInfo` 并按需 RSA 加密密码
- 可配置循环模式（`--loop`）
- 支持 YAML 配置 + 环境变量覆盖
- 支持 `curl_cffi` 作为 TLS 兼容后端（处理部分门户握手问题）
- 支持 Windows 后台无界面启动 + 计划任务开机自启
- 支持文件日志轮转（便于长期运行排障）

## 使用说明

### 1) 环境准备

- Python 3.10+（仅源码运行需要）
- 依赖安装：

```powershell
pip install requests urllib3 curl_cffi
```

### 2) 配置文件

复制模板并填写账号密码：

```powershell
copy config.yaml.example config.yaml
```

关键字段：

- `user_id`：学号/账号
- `password`：密码
- `base_url`：认证门户地址（默认 DGUT）
- `loop_interval`：循环检测间隔（秒）
- `log_file`：日志文件路径

完整字段见：[`docs/CONFIG.md`](./docs/CONFIG.md)

### 3) 源码运行（调试）

单次检测/登录：

```powershell
py campus_login.py
```

循环运行：

```powershell
py campus_login.py --loop
```

自定义循环间隔：

```powershell
py campus_login.py --loop --interval 30
```

### 4) 打包版运行（无 Python 环境）

打包版可直接运行 `dist\campus_login.exe`，目标机无需安装 Python：

```powershell
.\dist\campus_login.exe --loop
```

### 5) Windows 后台无界面运行

手动后台启动：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_hidden.ps1
```

开机自启（管理员 PowerShell）：

```powershell
.\install_startup_task.ps1
```

查看任务：

```powershell
Get-ScheduledTask -TaskName "CampusLoginAutoLoop"
```

删除任务：

```powershell
Unregister-ScheduledTask -TaskName "CampusLoginAutoLoop" -Confirm:$false
```

### 6) 日志与排障

- 默认日志按 `config.yaml` 中 `log_file` 输出（支持轮转）。
- 常见报错关键字：
  - `DNS失败`
  - `超时`
  - `TLS握手失败`
  - `未获取到 queryString`
- 若处于代理环境，需在代理软件中放行认证域名与探测域名。

## 配置说明

- 详细字段说明：[`docs/CONFIG.md`](./docs/CONFIG.md)
- Windows 后台运行与开机自启：[`docs/DEPLOYMENT_WINDOWS.md`](./docs/DEPLOYMENT_WINDOWS.md)

## 许可证

本项目使用 Apache License 2.0，见 [`LICENSE`](./LICENSE)。
