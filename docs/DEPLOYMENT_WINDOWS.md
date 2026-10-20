# Windows 部署与运维

## 1. 环境要求

- Windows 10 / 11
- Python 3.9+（64 位），安装时勾选 **Add python.exe to PATH**
- 管理员权限（仅用于注册登录自启任务，注册完成后不需要常驻管理员）

## 2. 一键部署

```text
右键 setup.bat → 以管理员身份运行
```

脚本会依次：校验权限 → 定位 Python → 安装依赖 → 生成 `config.yaml` → 注册任务 → 启动 → 自检。

## 3. 目录约定

所有文件放在同一个目录（例如 `G:\校园网日志`），任务动作里写的是绝对路径，**移动目录后必须重新运行 `switch_to_logon_task.bat`**。

必须存在的文件：

```
campus_login.py
config.yaml
```

自启相关：

```
setup.bat                 （一键引导）
setup_config.ps1          （生成配置）
switch_to_logon_task.bat  （注册任务）
switch_to_logon_task.ps1  （注册逻辑）
```

## 4. 后台启动方式

任务注册后，登录时自动以 `pythonw.exe` 启动，无窗口、无控制台。

手动调试（前台，能看输出）：

```powershell
python campus_login.py --loop
```

手动启动/停止任务：

```powershell
Start-ScheduledTask -TaskName "CampusLoginAutoLoopPy_Logon"
Get-Process pythonw | Stop-Process -Force     # 下一次登录会重新拉起
```

## 5. 任务结构

| 项目 | 值 |
|---|---|
| 名称 | `CampusLoginAutoLoopPy_Logon` |
| 触发 | 当前用户登录（`AtLogOn`） |
| 账户 | 当前用户 |
| 级别 | `HighestAvailable`（静默提权，不弹 UAC） |
| 动作 | `pythonw.exe "<目录>\campus_login.py" --loop` |
| 工作目录 | 脚本所在目录 |
| 多实例 | `IgnoreNew` |
| 电池 | 电池上不启动；已运行实例拔电后继续跑 |

不用 SYSTEM 的原因：默认禁止电池启动、进程在任务管理器中无法结束、会与其它启动项抢单实例锁。

## 6. 校验是否正常

```powershell
Get-ScheduledTask -TaskName "CampusLoginAutoLoopPy_Logon" | Select-Object TaskName,State,@{n='Level';e={$_.Principal.RunLevel}}
Get-Process pythonw | Select-Object Id,StartTime
Get-Content .\campus_login.log -Tail 20
```

正常日志：

```
循环模式启动，间隔 20s，进程PID=23380，权限=管理员
[OK] 已联网: www.baidu.com:OK(200)
```

`权限=管理员` 说明提权生效。若显示 `普通用户`，说明进程不是任务拉起的（可能被手动启动），部分网络操作会受限。

## 7. 日志

- `campus_login.log`：主循环日志，默认 5 MB 轮转，保留 3 份。
- 关键行：
  - `已联网` — 一切正常
  - `未联网（连续失败 N 次）` — 探测失败
  - `WLAN 不可用（接口存在=..., 软件开关关闭=...）` — 无线电被关，正在尝试打开
  - `WLAN已连接: <SSID> via profile=<profile名>` — 恢复成功
  - `自动认证失败（连续 N 次）` — 认证链路有问题，按 120s×N 退避重试

## 8. 脚本自更新

`run_loop` 每轮比对 `campus_login.py` 和 `config.yaml` 的修改时间，发现变化就 `os.execv` 原地重载，**保留当前令牌**。所以：

- 改代码 / 改配置后不必手动重启，最多等一个 `loop_interval`。
- 重载日志：`检测到脚本或配置已更新，重载自身`。

## 9. 排障

| 现象 | 处理 |
|---|---|
| `ModuleNotFoundError: requests` | 用同一个解释器装依赖：`python -m pip install requests urllib3 curl_cffi`；依赖缺失时脚本会写 `campus_login_crash.log`，里面带解释器路径和修复命令 |
| `setup.bat` 双击后窗口一闪就关 | 手动排查：开 cmd，`cd /d 解压目录`，再输 `setup.bat`，错误会留在窗口里；同时看目录下 `setup.log`（每步都有记录）。常见原因：下载到的 `.bat` 是 LF 换行（用 v0.1.1 及以上版本）|
| 任务注册失败、提示拒绝访问 | `setup.bat` 不是以管理员身份运行的 |
| 进程存在但日志不更新 | 看日志尾部；可能卡在 `WLAN 不可用`，检查硬件无线开关 |
| 反复 `未联网` 但 Wi-Fi 显示已连接 | 门户认证没走通，按 README「抓不到 queryString」处理 |
| 出现两个同名 Wi-Fi | profile 的 SSID 字节编码不一致，见 README 同名网络一节 |

## 10. 卸载

```powershell
Unregister-ScheduledTask -TaskName "CampusLoginAutoLoopPy_Logon" -Confirm:$false
Remove-Item .\config.yaml, .\campus_login.log -Force
```
