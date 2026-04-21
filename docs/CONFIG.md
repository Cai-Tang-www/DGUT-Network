# 配置说明（config.yaml）

## 配置加载优先级

1. 环境变量（最高优先级）
2. `config.yaml`
3. 代码默认值

可通过环境变量 `CAMPUS_CONFIG_FILE` 指定配置文件路径。

## 示例

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
loop_interval: 20
captive_host: "login.dgut.edu.cn"
captive_path: "/eportal/index.jsp"
auto_wifi_recovery: true
wifi_ssid: "莞工全光无线"
wifi_connect_wait: 8
wifi_retry_interval: 60

log_file: "./campus_login.log"
log_level: "INFO"
log_max_size_mb: 5
log_backup_count: 3
```

## 字段详解

- `base_url`：认证门户地址，默认 `https://login.dgut.edu.cn`
- `user_id`：学号/账号
- `password`：密码
- `verify_tls`：是否校验证书，门户证书异常时可设为 `false`
- `captive_query_string`：手动兜底 queryString（通常留空，由脚本自动抓）
- `debug_query_fetch`：是否打印 queryString 抓取调试日志
- `force_rsa_encrypt`：是否强制使用 RSA（有 key 时）
- `use_curl_cffi`：对 portal HTTPS 请求优先使用 `curl_cffi`
- `curl_impersonate`：`curl_cffi` 浏览器指纹（如 `chrome124`）
- `query_fetch_retries`：抓取 queryString 失败重试次数
- `query_fetch_retry_delay`：重试间隔（秒）
- `loop_interval`：循环模式检测间隔（秒）
- `captive_host`：portal 主机名（默认从 `base_url` 推断）
- `captive_path`：portal 登录页路径（默认 `/eportal/index.jsp`）
- `auto_wifi_recovery`：是否启用“有线优先 + WLAN 自动恢复”
- `wifi_ssid`：无有线时自动尝试连接的无线名称（SSID）
- `wifi_connect_wait`：发起 WLAN 连接后等待秒数
- `wifi_retry_interval`：WLAN 自动恢复最小重试间隔（秒）
- `log_file`：日志文件路径（相对路径以配置文件目录为基准）
- `log_level`：日志级别（`DEBUG`/`INFO`/`WARN`/`ERROR`）
- `log_max_size_mb`：单日志文件最大大小（MB）
- `log_backup_count`：日志轮转保留数量

## 环境变量映射

- `CAMPUS_BASE_URL`
- `CAMPUS_USER_ID`
- `CAMPUS_PASSWORD`
- `CAMPUS_VERIFY_TLS`
- `CAMPUS_QUERY_STRING`
- `CAMPUS_DEBUG_QUERY_FETCH`
- `CAMPUS_FORCE_RSA_ENCRYPT`
- `CAMPUS_USE_CURL_CFFI`
- `CAMPUS_CURL_IMPERSONATE`
- `CAMPUS_QUERY_FETCH_RETRIES`
- `CAMPUS_QUERY_FETCH_RETRY_DELAY`
- `CAMPUS_LOOP_INTERVAL`
- `CAMPUS_CAPTIVE_HOST`
- `CAMPUS_CAPTIVE_PATH`
- `CAMPUS_AUTO_WIFI_RECOVERY`
- `CAMPUS_WIFI_SSID`
- `CAMPUS_WIFI_CONNECT_WAIT`
- `CAMPUS_WIFI_RETRY_INTERVAL`
- `CAMPUS_LOG_FILE`
- `CAMPUS_LOG_LEVEL`
- `CAMPUS_LOG_MAX_SIZE_MB`
- `CAMPUS_LOG_BACKUP_COUNT`
