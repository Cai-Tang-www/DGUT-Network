# DGUT-Network

> 校园网自动认证脚本（DGUT），支持未联网状态自动抓取会话参数、自动登录、循环保活检测，以及 Windows 开机后台运行。

## 免责声明

- 本项目仅用于个人网络运维与学习研究。
- 请遵守学校与网络服务提供方的相关规定。
- 使用本项目造成的后果由使用者自行承担。

## 项目简介

本仓库用于解决校园网认证场景中的两个常见问题：

- 网络被认证页劫持时，HTTP 状态码可能仍是 `200`，导致普通“联网检测”误判。
- 登录参数中的 `queryString` 会话值是动态的，不能长期硬编码。

脚本会在检测到“未真正联网”后，自动尝试抓取当前会话 `queryString`，获取 `pageInfo`，并按门户要求提交登录请求（支持 RSA 模式）。

## 功能特性

- 自动联网检测（识别 portal 劫持，不只看 `200`）
- 自动抓取当次会话 `queryString`
- 自动调用 `pageInfo` 并按需 RSA 加密密码
- 可配置循环模式（`--loop`）
- 支持 YAML 配置 + 环境变量覆盖
- 支持 `curl_cffi` 作为 TLS 兼容后端（处理部分门户握手问题）
- 支持 Windows 后台无界面启动 + 计划任务开机自启
- 支持文件日志轮转（便于长期运行排障）

## 仓库结构

```text
campus_login.py              # 主程序
config.yaml.example          # 配置模板
start_loop.bat               # 前台循环启动（便于调试）
start_hidden.ps1             # 后台无界面启动入口
install_startup_task.ps1     # 安装开机自启计划任务
AUTOSTART_TASK.md            # 自启动运维说明
docs/CONFIG.md               # 配置项详细说明
docs/DEPLOYMENT_WINDOWS.md   # Windows 部署说明
```

## 快速开始

1. 复制配置模板并填写账号密码：

```powershell
copy config.yaml.example config.yaml
```

2. 单次运行（调试）：

```powershell
py campus_login.py
```

3. 循环运行：

```powershell
py campus_login.py --loop
```

> 打包版可直接运行 `dist\campus_login.exe`，目标机无需安装 Python。

## 配置说明

- 详细字段说明：[`docs/CONFIG.md`](./docs/CONFIG.md)
- Windows 后台运行与开机自启：[`docs/DEPLOYMENT_WINDOWS.md`](./docs/DEPLOYMENT_WINDOWS.md)

## 运维命令（计划任务）

安装（管理员 PowerShell）：

```powershell
.\install_startup_task.ps1
```

查看：

```powershell
Get-ScheduledTask -TaskName "CampusLoginAutoLoop"
```

删除：

```powershell
Unregister-ScheduledTask -TaskName "CampusLoginAutoLoop" -Confirm:$false
```

## 参考

- 文档结构参考：<https://github.com/mjz001/-dgut->

## 许可证

本项目使用 Apache License 2.0，见 [`LICENSE`](./LICENSE)。
