# 配置说明（config.yaml）

## 加载优先级

1. 环境变量（最高优先级）
2. `config.yaml`
3. 代码内置默认值

可用环境变量 `CAMPUS_CONFIG_FILE` 指定配置文件路径。

文件必须是 UTF-8（无 BOM）。相对路径以配置文件所在目录为基准。

## 完整示例

```yaml
base_url: "https://login.dgut.edu.cn"
user_id: "2024xxxxxxxx"
password: "your-password"

verify_tls: false
captive_query_string: ""
debug_query_fetch: false
force_rsa_encrypt: true
use_curl_cffi: true
curl_impersonate: "chrome124"
query_fetch_retries: 3
query_fetch_retry_delay: 3
captive_host: "login.dgut.edu.cn"
captive_path: "/eportal/index.jsp"

loop_interval: 20

auto_wifi_recovery: true
wifi_ssid: "莞工全光无线"
wifi_ssid_prefix_match: true
wifi_recovery_after_fails: 2
wifi_recovery_cooldown: 300
wifi_recovery_retry: 15
wifi_auto_add_profile: false
wifi_connect_wait: 8
wifi_retry_interval: 60

login_fail_backoff: 120

log_file: "./campus_login.log"
log_level: "INFO"
log_max_size_mb: 5
log_backup_count: 3
```

## 认证相关

| 字段 | 默认 | 说明 |
|---|---|---|
| `base_url` | `https://login.dgut.edu.cn` | 认证门户地址 |
| `user_id` | 空 | 学号 / 账号 |
| `password` | 空 | 密码 |
| `verify_tls` | `false` | 是否校验证书，门户证书异常时保持 false |
| `captive_query_string` | 空 | 手动兜底 queryString，通常留空由脚本自动抓 |
| `debug_query_fetch` | `false` | 打印 queryString 抓取过程 |
| `force_rsa_encrypt` | `true` | 有公钥时强制 RSA 加密密码 |
| `use_curl_cffi` | `true` | 对 portal 的 HTTPS 请求优先用 curl_cffi |
| `curl_impersonate` | `chrome124` | curl_cffi 浏览器指纹 |
| `query_fetch_retries` | `3` | 抓 queryString 的重试次数 |
| `query_fetch_retry_delay` | `3` | 每次重试间隔（秒） |
| `captive_host` | 由 `base_url` 推断 | portal 主机名 |
| `captive_path` | `/eportal/index.jsp` | 登录页路径 |

## 循环

| 字段 | 默认 | 说明 |
|---|---|---|
| `loop_interval` | `20` | 每轮探测间隔（秒）。**恢复重试的最快节奏也受它限制** |

## WLAN 兜底

| 字段 | 默认 | 说明 |
|---|---|---|
| `auto_wifi_recovery` | `true` | 是否启用"有线优先 + WLAN 自动恢复" |
| `wifi_ssid` | `莞工全光无线` | 目标 SSID；支持逗号分隔多个 |
| `wifi_ssid_prefix_match` | `true` | 允许匹配 Windows 重名后缀（`xxx 2`）和同前缀 SSID |
| `wifi_recovery_after_fails` | `2` | 连续失败几次才动 WLAN（× `loop_interval`） |
| `wifi_recovery_cooldown` | `300` | 恢复**成功**后的冷却（秒），防止反复折腾 |
| `wifi_recovery_retry` | `15` | 恢复**失败**后的重试间隔（秒） |
| `wifi_auto_add_profile` | `false` | 机器上没有匹配 profile 时是否自动新建（写 UTF-8 hex SSID） |
| `wifi_connect_wait` | `8` | 发起连接后等待确认的秒数 |
| `wifi_retry_interval` | `60` | 与 cooldown 取较大值作为最小干预间隔 |

行为约定：

- 已连到目标 SSID → 什么都不做，不会 `netsh wlan connect` 掐断健康链路。
- 无线电关闭 → 先用 `wlanapi` 打开（无需管理员），失败才退到 `netsh autoconfig` / 重置适配器（这两步需要管理员）。
- 连接失败时只标记候选为可疑并换序重试，不会无限重连同一个 profile。

## 认证退避

| 字段 | 默认 | 说明 |
|---|---|---|
| `login_fail_backoff` | `120` | 认证失败退避基数（秒），失败 n 次等 n×120，上限 4 倍 |

## 日志

| 字段 | 默认 | 说明 |
|---|---|---|
| `log_file` | `./campus_login.log` | 日志路径（相对配置文件目录） |
| `log_level` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `log_max_size_mb` | `5` | 单文件上限（MB） |
| `log_backup_count` | `3` | 轮转保留份数 |

## 环境变量映射

| 配置键 | 环境变量 |
|---|---|
| `base_url` | `CAMPUS_BASE_URL` |
| `user_id` | `CAMPUS_USER_ID` |
| `password` | `CAMPUS_PASSWORD` |
| `verify_tls` | `CAMPUS_VERIFY_TLS` |
| `captive_query_string` | `CAMPUS_QUERY_STRING` |
| `debug_query_fetch` | `CAMPUS_DEBUG_QUERY_FETCH` |
| `force_rsa_encrypt` | `CAMPUS_FORCE_RSA_ENCRYPT` |
| `use_curl_cffi` | `CAMPUS_USE_CURL_CFFI` |
| `curl_impersonate` | `CAMPUS_CURL_IMPERSONATE` |
| `query_fetch_retries` | `CAMPUS_QUERY_FETCH_RETRIES` |
| `query_fetch_retry_delay` | `CAMPUS_QUERY_FETCH_RETRY_DELAY` |
| `loop_interval` | `CAMPUS_LOOP_INTERVAL` |
| `captive_host` | `CAMPUS_CAPTIVE_HOST` |
| `captive_path` | `CAMPUS_CAPTIVE_PATH` |
| `auto_wifi_recovery` | `CAMPUS_AUTO_WIFI_RECOVERY` |
| `wifi_ssid` | `CAMPUS_WIFI_SSID` |
| `wifi_ssid_prefix_match` | `CAMPUS_WIFI_SSID_PREFIX_MATCH` |
| `wifi_recovery_after_fails` | `CAMPUS_WIFI_RECOVERY_AFTER_FAILS` |
| `wifi_recovery_cooldown` | `CAMPUS_WIFI_RECOVERY_COOLDOWN` |
| `wifi_recovery_retry` | `CAMPUS_WIFI_RECOVERY_RETRY` |
| `wifi_auto_add_profile` | `CAMPUS_WIFI_AUTO_ADD_PROFILE` |
| `wifi_connect_wait` | `CAMPUS_WIFI_CONNECT_WAIT` |
| `wifi_retry_interval` | `CAMPUS_WIFI_RETRY_INTERVAL` |
| `login_fail_backoff` | `CAMPUS_LOGIN_FAIL_BACKOFF` |
| `log_file` | `CAMPUS_LOG_FILE` |
| `log_level` | `CAMPUS_LOG_LEVEL` |
| `log_max_size_mb` | `CAMPUS_LOG_MAX_SIZE_MB` |
| `log_backup_count` | `CAMPUS_LOG_BACKUP_COUNT` |
