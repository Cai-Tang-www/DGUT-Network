# 东莞理工学院校园网自动化脚本（DGUT-Network）

> 面向东莞理工学院（DGUT）校园网认证场景的自动登录脚本：自动探测未联网 / 被门户劫持、自动恢复 WLAN、自动抓取会话参数并完成认证，后台静默常驻。

## 免责声明

- 本项目仅用于个人网络运维与学习研究。
- 请遵守学校与网络服务提供方相关规定。
- 使用本项目造成的任何后果由使用者自行承担。

## 它解决什么问题

校园网 portal 认证有几个常见坑，这个脚本就是冲着它们去的：

- 认证劫持页返回 `200`，只看状态码的检测会误判成"已联网"。
- `queryString` 是动态会话参数，不能硬编码。
- 部分门户 TLS 指纹校验严格，普通请求库握手失败（用 `curl_cffi` 绕过）。
- Wi-Fi 漫游或省电导致链路抖动，掉线后没人重新认证。

## 运行逻辑

每 `loop_interval`（默认 20 秒）执行一轮：

1. **探测**：HTTPS 请求 `baidu.com`，失败再试 `bing.com`；同时识别是否被重定向到认证页。
2. **已联网**：只记日志，不动任何链路。
3. **未联网**：累加失败计数，连续 2 次（约 40 秒）才进入恢复流程。
   - 已连到目标 SSID → 直接返回，绝不打断健康连接。
   - WLAN 无线电被关 → 通过 `wlanapi` 打开（**不需要管理员权限**）。
   - 选 profile（上次成功的优先）→ `netsh wlan connect`。
   - 恢复失败 → 15 秒后重试，不会一停就是几分钟。
4. **有链路但仍未联网** → 走认证：抓 `queryString` → 取 RSA 公钥 → 加密密码 → 提交登录。
5. **完全无链路**（无以太网、WLAN 也连不上）→ 跳过认证，等下一轮，不空刷日志。
6. **脚本文件或配置被改** → 自动原地重载（`os.execv`），继承当前权限，无需手工重启。

有线优先：只要检测到以太网已连接，就不碰 WLAN。

## 快速开始（推荐）

1. 安装 Python 3.9+（安装时勾选 **Add python.exe to PATH**）。
2. **右键 `setup.bat` → 以管理员身份运行**。
3. 按提示输入学号、密码。
4. 完成后看窗口末尾的状态输出，以及 `campus_login.log`。

`setup.bat` 做了这些事：

- 校验管理员权限
- 定位 `python.exe` / `pythonw.exe`
- 检查并安装依赖（`requests` / `urllib3` / `curl_cffi`）
- 由 `config.yaml.example` 生成 `config.yaml`（UTF-8 无 BOM）
- 调 `switch_to_logon_task.ps1` 注册登录自启任务并立即启动
- 打印任务状态、进程状态、日志尾部

幂等：可以重复运行；已有 `config.yaml` 时会问你要不要重新配置。

## 手动部署

```powershell
copy config.yaml.example config.yaml
# 编辑 config.yaml，至少填 user_id / password

python -m pip install requests urllib3 curl_cffi
python campus_login.py --loop
```

后台常驻（管理员）：

```powershell
.\switch_to_logon_task.bat
```

## 自启动任务

任务名：`CampusLoginAutoLoopPy_Logon`

| 项目 | 值 |
|---|---|
| 触发器 | 当前用户登录时 |
| 运行账户 | 当前用户（不是 SYSTEM） |
| 运行级别 | 最高权限（`HighestAvailable`，登录时静默提升，不弹 UAC） |
| 动作 | `pythonw.exe "<目录>\campus_login.py" --loop` |
| 多实例 | `IgnoreNew`（配合脚本内单实例锁） |
| 电池 | 电池上不自动启动；已启动的实例在拔掉电源后**继续运行** |

为什么用"当前用户 + 最高权限"而不是 SYSTEM：SYSTEM 任务默认禁止电池启动、进程在任务管理器里杀不掉、和注册表启动项抢单实例锁；而当前用户的提权任务既能做 `Enable-NetAdapter` 之类操作，又完全受你控制。

### 检查

```powershell
Get-ScheduledTask -TaskName "CampusLoginAutoLoopPy_Logon" | Select-Object TaskName,State
Get-Process pythonw | Select-Object Id,StartTime
Get-Content .\campus_login.log -Tail 20
```

日志里启动行会写明进程 PID 和权限：

```
循环模式启动，间隔 20s，进程PID=23380，权限=管理员
```

### 卸载

```powershell
Unregister-ScheduledTask -TaskName "CampusLoginAutoLoopPy_Logon" -Confirm:$false
```

再删掉 `config.yaml`、`campus_login.log` 即可，不留其他痕迹。

## 配置

见 [`docs/CONFIG.md`](./docs/CONFIG.md)。最小可用配置只有三项：

```yaml
base_url: "https://login.dgut.edu.cn"
user_id: "2024xxxxxxxx"
password: "your-password"
```

## 常见问题

### 日志一直报"未联网"、抓不到 queryString

1. 浏览器访问 `http://neverssl.com`（必须 http），触发认证跳转。
2. 复制地址栏 `index.jsp?` 之后整段参数，临时写进 `config.yaml`：

```yaml
captive_query_string: "这里填完整参数串"
debug_query_fetch: true
```

3. 单次运行验证链路：`python campus_login.py`
4. 通了之后清空 `captive_query_string`，改回自动抓取。

### Wi-Fi 看着是同一个名字，实际连不上

Windows 里 SSID 是按字节比较的。中文 SSID 若被不同编码写入 profile（UTF-8 vs GBK），会生成两个"同名"网络，其中一个在空气里根本不存在。

检查机器上有几个匹配的 profile：

```powershell
netsh wlan show profiles
netsh wlan export profile name="莞工全光无线" folder=.
```

导出的 XML 里 `<hex>` 就是真实字节。删掉错的那个：

```powershell
netsh wlan delete profile name="<profile名>" interface=WLAN
```

脚本新建 profile 时会写 UTF-8 hex SSID，不会再产生这类"影子网络"。

### WLAN 开关关着，脚本能自己打开吗

能。通过 `wlanapi` 的 `WlanSetInterface(radio_state)`，和系统设置里那个开关是同一条路径，且**不需要管理员权限**（实测）。

注意：`netsh wlan set autoconfig enabled=yes` 和重置网卡对这个开关无效。

### 代理绕过（Clash / 系统代理）

开了代理时认证流量被劫持会导致抓不到 `queryString`，把下列目标设为直连：

- `login.dgut.edu.cn`
- `10.60.0.1`
- `1.1.1.1`
- `114.114.114.114`
- `www.baidu.com` / `www.bing.com`
- `www.msftconnecttest.com`
- `connect.rom.miui.com`

```yaml
rules:
  - DOMAIN,login.dgut.edu.cn,DIRECT
  - DOMAIN,www.baidu.com,DIRECT
  - DOMAIN,www.bing.com,DIRECT
  - DOMAIN,www.msftconnecttest.com,DIRECT
  - DOMAIN,connect.rom.miui.com,DIRECT
  - IP-CIDR,10.60.0.1/32,DIRECT,no-resolve
  - IP-CIDR,1.1.1.1/32,DIRECT,no-resolve
  - IP-CIDR,114.114.114.114/32,DIRECT,no-resolve
```

## 文件说明

| 文件 | 用途 |
|---|---|
| `campus_login.py` | 主脚本 |
| `config.yaml` | 本地配置（含账号密码，**不入库**） |
| `config.yaml.example` | 配置模板 |
| `setup.bat` | 一键安装引导（需管理员） |
| `setup_config.ps1` | 由模板生成 `config.yaml`（被 setup.bat 调用） |
| `switch_to_logon_task.bat` | 注册/修复自启任务（需管理员） |
| `switch_to_logon_task.ps1` | 任务注册的实际逻辑 |
| `docs/CONFIG.md` | 配置项详解 |
| `docs/DEPLOYMENT_WINDOWS.md` | Windows 部署与运维 |

## 许可证

Apache License 2.0，见 [`LICENSE`](./LICENSE)。
