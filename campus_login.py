import html
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
from logging.handlers import RotatingFileHandler
from urllib.parse import parse_qs, quote, unquote, urlparse
from xml.sax.saxutils import escape as xml_escape

import requests
import urllib3

try:
    from curl_cffi import requests as curl_requests
except Exception:
    curl_requests = None


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


APP_DIR = app_dir()
DEFAULT_CONFIG_PATH = os.path.join(APP_DIR, "config.yaml")

DEFAULTS = {
    "base_url": "https://login.dgut.edu.cn",
    "user_id": "",
    "password": "",
    "verify_tls": False,
    "captive_query_string": "",
    "debug_query_fetch": False,
    "force_rsa_encrypt": True,
    "use_curl_cffi": True,
    "curl_impersonate": "chrome124",
    "query_fetch_retries": 3,
    "query_fetch_retry_delay": 3,
    "loop_interval": 20,
    "captive_host": "",
    "captive_path": "/eportal/index.jsp",
    "log_file": "./campus_login.log",
    "log_level": "INFO",
    "log_max_size_mb": 5,
    "log_backup_count": 3,
    "auto_wifi_recovery": True,
    "wifi_ssid": "莞工全光无线",
    "wifi_ssid_prefix_match": True,
    "wifi_connect_wait": 8,
    "wifi_retry_interval": 60,
    "wifi_recovery_after_fails": 3,
    "wifi_recovery_cooldown": 300,
    "wifi_recovery_retry": 15,
    "wifi_auto_add_profile": False,
    "login_fail_backoff": 120,
}

ENV_MAP = {
    "base_url": "CAMPUS_BASE_URL",
    "user_id": "CAMPUS_USER_ID",
    "password": "CAMPUS_PASSWORD",
    "verify_tls": "CAMPUS_VERIFY_TLS",
    "captive_query_string": "CAMPUS_QUERY_STRING",
    "debug_query_fetch": "CAMPUS_DEBUG_QUERY_FETCH",
    "force_rsa_encrypt": "CAMPUS_FORCE_RSA_ENCRYPT",
    "use_curl_cffi": "CAMPUS_USE_CURL_CFFI",
    "curl_impersonate": "CAMPUS_CURL_IMPERSONATE",
    "query_fetch_retries": "CAMPUS_QUERY_FETCH_RETRIES",
    "query_fetch_retry_delay": "CAMPUS_QUERY_FETCH_RETRY_DELAY",
    "loop_interval": "CAMPUS_LOOP_INTERVAL",
    "captive_host": "CAMPUS_CAPTIVE_HOST",
    "captive_path": "CAMPUS_CAPTIVE_PATH",
    "log_file": "CAMPUS_LOG_FILE",
    "log_level": "CAMPUS_LOG_LEVEL",
    "log_max_size_mb": "CAMPUS_LOG_MAX_SIZE_MB",
    "log_backup_count": "CAMPUS_LOG_BACKUP_COUNT",
    "auto_wifi_recovery": "CAMPUS_AUTO_WIFI_RECOVERY",
    "wifi_ssid": "CAMPUS_WIFI_SSID",
    "wifi_ssid_prefix_match": "CAMPUS_WIFI_SSID_PREFIX_MATCH",
    "wifi_connect_wait": "CAMPUS_WIFI_CONNECT_WAIT",
    "wifi_retry_interval": "CAMPUS_WIFI_RETRY_INTERVAL",
    "wifi_recovery_after_fails": "CAMPUS_WIFI_RECOVERY_AFTER_FAILS",
    "wifi_recovery_cooldown": "CAMPUS_WIFI_RECOVERY_COOLDOWN",
    "wifi_recovery_retry": "CAMPUS_WIFI_RECOVERY_RETRY",
    "wifi_auto_add_profile": "CAMPUS_WIFI_AUTO_ADD_PROFILE",
    "login_fail_backoff": "CAMPUS_LOGIN_FAIL_BACKOFF",
}


def to_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def to_int(value, default=0):
    try:
        num = int(str(value).strip())
        return num if num > 0 else default
    except Exception:
        return default


def cast_like_default(value, default):
    if isinstance(default, bool):
        return to_bool(value, default)
    if isinstance(default, int):
        return to_int(value, default)
    if value is None:
        return default
    return str(value)


def parse_simple_yaml(path):
    data = {}
    if not os.path.exists(path):
        return data

    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            key = k.strip()
            value = v.strip()
            if not key:
                continue

            if value == "":
                data[key] = ""
                continue

            if value[0:1] in {'"', "'"} and value[-1:] == value[0:1] and len(value) >= 2:
                data[key] = value[1:-1]
                continue

            low = value.lower()
            if low in {"true", "yes", "on"}:
                data[key] = True
                continue
            if low in {"false", "no", "off"}:
                data[key] = False
                continue

            if re.fullmatch(r"-?\d+", value):
                try:
                    data[key] = int(value)
                    continue
                except Exception:
                    pass

            data[key] = value

    return data


def load_config():
    cfg = dict(DEFAULTS)

    config_path = os.getenv("CAMPUS_CONFIG_FILE", DEFAULT_CONFIG_PATH)
    yaml_data = parse_simple_yaml(config_path)
    for key in cfg:
        if key in yaml_data:
            cfg[key] = cast_like_default(yaml_data[key], DEFAULTS[key])

    for key, env_name in ENV_MAP.items():
        env_val = os.getenv(env_name)
        if env_val is not None:
            cfg[key] = cast_like_default(env_val, DEFAULTS[key])

    cfg["base_url"] = str(cfg["base_url"]).rstrip("/")

    if not cfg["captive_host"]:
        parsed = urlparse(cfg["base_url"])
        cfg["captive_host"] = parsed.netloc or "login.dgut.edu.cn"

    cfg["_config_path"] = config_path
    return cfg


CFG = load_config()

BASE_URL = CFG["base_url"]
USER_ID = CFG["user_id"]
PASSWORD = CFG["password"]
VERIFY_TLS = CFG["verify_tls"]
CAPTIVE_QUERY_STRING = CFG["captive_query_string"]
DEBUG_QUERY_FETCH = CFG["debug_query_fetch"]
FORCE_RSA_ENCRYPT = CFG["force_rsa_encrypt"]
USE_CURL_CFFI_FOR_PORTAL_HTTPS = CFG["use_curl_cffi"]
CURL_IMPERSONATE = CFG["curl_impersonate"]
QUERY_FETCH_RETRIES = CFG["query_fetch_retries"]
QUERY_FETCH_RETRY_DELAY = CFG["query_fetch_retry_delay"]
LOOP_INTERVAL = CFG["loop_interval"]
CAPTIVE_HOST = CFG["captive_host"]
CAPTIVE_PATH = CFG["captive_path"]
LOG_FILE = CFG["log_file"]
LOG_LEVEL = str(CFG["log_level"]).upper().strip() or "INFO"
LOG_MAX_SIZE_MB = CFG["log_max_size_mb"]
LOG_BACKUP_COUNT = CFG["log_backup_count"]
AUTO_WIFI_RECOVERY = CFG["auto_wifi_recovery"]
WIFI_SSID = str(CFG["wifi_ssid"] or "").strip()
WIFI_SSID_PREFIX_MATCH = CFG["wifi_ssid_prefix_match"]
WIFI_CONNECT_WAIT = CFG["wifi_connect_wait"]
WIFI_RETRY_INTERVAL = CFG["wifi_retry_interval"]
WIFI_RECOVERY_AFTER_FAILS = CFG["wifi_recovery_after_fails"]
WIFI_RECOVERY_COOLDOWN = CFG["wifi_recovery_cooldown"]
WIFI_RECOVERY_RETRY = CFG["wifi_recovery_retry"]
WIFI_AUTO_ADD_PROFILE = CFG["wifi_auto_add_profile"]
LOGIN_FAIL_BACKOFF = CFG["login_fail_backoff"]
CONFIG_FILE = CFG.get("_config_path", DEFAULT_CONFIG_PATH)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0"
)

if not VERIFY_TLS:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def resolve_path(path, base_dir):
    if not path:
        return ""
    if os.path.isabs(path):
        return path
    return os.path.abspath(os.path.join(base_dir, path))


def normalize_log_level(level_name):
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "WARN": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return level_map.get((level_name or "INFO").upper(), logging.INFO)


def setup_logger():
    logger = logging.getLogger("campus_login")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    level = normalize_log_level(LOG_LEVEL)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    cfg_dir = os.path.dirname(os.path.abspath(CONFIG_FILE)) if CONFIG_FILE else APP_DIR
    log_path = resolve_path(LOG_FILE, cfg_dir or APP_DIR)
    if log_path:
        try:
            log_dir = os.path.dirname(log_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=max(1, int(LOG_MAX_SIZE_MB)) * 1024 * 1024,
                backupCount=max(1, int(LOG_BACKUP_COUNT)),
                encoding="utf-8",
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as err:
            print(f"[WARN] log file handler init failed: {err}")

    return logger


LOGGER = setup_logger()
SINGLE_INSTANCE_HANDLE = None
LAST_WIFI_RECOVERY_TS = 0.0


def log(level, msg):
    level_map = {
        "DBG": logging.DEBUG,
        "INFO": logging.INFO,
        "OK": logging.INFO,
        "WARN": logging.WARNING,
        "ERR": logging.ERROR,
    }
    py_level = level_map.get(level, logging.INFO)
    if level == "OK":
        msg = f"[OK] {msg}"
    LOGGER.log(py_level, msg)


def acquire_single_instance_lock(lock_path):
    global SINGLE_INSTANCE_HANDLE
    try:
        lock_dir = os.path.dirname(lock_path)
        if lock_dir:
            os.makedirs(lock_dir, exist_ok=True)

        fh = open(lock_path, "a+", encoding="utf-8")
        fh.seek(0)
        if os.path.getsize(lock_path) == 0:
            fh.write("0")
            fh.flush()
        fh.seek(0)

        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                fh.close()
                return False
        else:
            import fcntl

            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                fh.close()
                return False

        fh.seek(0)
        fh.truncate()
        fh.write(str(os.getpid()))
        fh.flush()
        SINGLE_INSTANCE_HANDLE = fh
        return True
    except Exception as err:
        log("WARN", f"单实例锁初始化失败: {short_exc(err)}")
        return True


def short_exc(err, limit=140):
    s = f"{type(err).__name__}: {err}"
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"0x[0-9A-Fa-f]+", "0x...", s)
    if len(s) > limit:
        s = s[: limit - 3] + "..."
    return s


def classify_error(err):
    s = short_exc(err, limit=100)
    low = s.lower()
    if "nameresolutionerror" in low or "getaddrinfo failed" in low:
        return "DNS失败"
    if "connecttimeout" in low or "readtimeout" in low or "timed out" in low:
        return "超时"
    if "winerror 10051" in low:
        return "网络不可达(10051)"
    if "handshake" in low:
        return "TLS握手失败"
    return s


def decode_console_bytes(raw):
    """控制台输出解码：优先 utf-8，失败回落到 mbcs(ANSI/GBK)。

    netsh / powershell 的编码取决于父进程的控制台代码页：正常启动是 936(GBK)，
    但控制台被设成 UTF-8(65001) 时会输出 utf-8。两种都要能解。
    """
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        return raw.decode("mbcs", errors="replace")
    except Exception:
        return raw.decode("latin-1", errors="replace")


def run_cmd(args, timeout=8):
    try:
        run_kwargs = {}
        if os.name == "nt":
            create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if create_no_window:
                run_kwargs["creationflags"] = create_no_window
        proc = subprocess.run(
            args,
            capture_output=True,
            timeout=timeout,
            check=False,
            **run_kwargs,
        )
        return (
            proc.returncode,
            decode_console_bytes(proc.stdout).strip(),
            decode_console_bytes(proc.stderr).strip(),
        )
    except Exception as err:
        return -1, "", short_exc(err)


def run_powershell(script, timeout=10):
    return run_cmd(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        timeout=timeout,
    )


def ps_single_quote(text):
    return str(text or "").replace("'", "''")


def get_physical_adapters():
    if os.name != "nt":
        return []

    script = (
        "$items = Get-NetAdapter -Physical -ErrorAction SilentlyContinue | ForEach-Object { "
        "[PSCustomObject]@{ "
        "Name=$_.Name; "
        "InterfaceDescription=$_.InterfaceDescription; "
        "Status=$_.Status; "
        "NdisPhysicalMedium=$(if ($_.PSObject.Properties.Name -contains 'NdisPhysicalMedium') { [string]$_.NdisPhysicalMedium } else { '' }); "
        "MediaConnectionState=$(if ($_.PSObject.Properties.Name -contains 'MediaConnectionState') { [string]$_.MediaConnectionState } else { '' }) "
        "} }; "
        "$items | ConvertTo-Json -Compress"
    )
    code, out, err = run_powershell(script, timeout=12)
    if code != 0:
        if DEBUG_QUERY_FETCH:
            log("DBG", f"Get-NetAdapter失败: {err}")
        return []
    if not out:
        return []
    try:
        data = json.loads(out)
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            return data
    except Exception:
        if DEBUG_QUERY_FETCH:
            log("DBG", "Get-NetAdapter JSON解析失败")
    return []


def is_ethernet_adapter(item):
    name = str(item.get("Name", "")).lower()
    desc = str(item.get("InterfaceDescription", "")).lower()
    medium = str(item.get("NdisPhysicalMedium", "")).lower()
    text = f"{name} {desc}"

    if "802.3" in medium or "ethernet" in medium:
        return True

    wired_words = ("ethernet", "以太网", "lan", "gigabit", "gbe")
    wifi_words = ("wi-fi", "wifi", "wlan", "wireless", "无线")
    return any(w in text for w in wired_words) and not any(w in text for w in wifi_words)


def is_wifi_adapter(item):
    name = str(item.get("Name", "")).lower()
    desc = str(item.get("InterfaceDescription", "")).lower()
    medium = str(item.get("NdisPhysicalMedium", "")).lower()
    text = f"{name} {desc}"
    if "802.11" in medium or "wireless" in medium:
        return True
    return any(w in text for w in ("wi-fi", "wifi", "wlan", "无线"))


def get_ethernet_connected_adapter():
    adapters = get_physical_adapters()
    for item in adapters:
        if not is_ethernet_adapter(item):
            continue
        status = str(item.get("Status", "")).strip().lower()
        media_state = str(item.get("MediaConnectionState", "")).strip().lower()
        if status == "up" or media_state == "connected":
            return str(item.get("Name") or item.get("InterfaceDescription") or "").strip()
    return ""


def get_wifi_adapter_names():
    names = []
    for item in get_physical_adapters():
        if is_wifi_adapter(item):
            name = str(item.get("Name") or "").strip()
            if name:
                names.append(name)
    seen = set()
    uniq = []
    for name in names:
        if name not in seen:
            uniq.append(name)
            seen.add(name)
    return uniq


def get_wlan_names_from_netsh():
    names = []
    code, out, _ = run_cmd(["netsh", "wlan", "show", "interfaces"], timeout=8)
    if code != 0 or not out:
        return names

    for line in out.splitlines():
        m = re.match(r"^\s*(?:名称|Name)\s*:\s*(.+?)\s*$", line, re.I)
        if m:
            n = m.group(1).strip()
            if n:
                names.append(n)
    seen = set()
    uniq = []
    for n in names:
        if n not in seen:
            uniq.append(n)
            seen.add(n)
    return uniq


def compact_text(text):
    s = unicodedata.normalize("NFKC", str(text or ""))
    s = s.replace("\u3000", " ")
    return re.sub(r"\s+", "", s).strip().lower()


def parse_netsh_interfaces(out):
    ifaces = []
    cur = None
    for raw in out.splitlines():
        line = raw.strip()
        if not line:
            continue
        if ":" in line:
            key, val = line.split(":", 1)
        elif "：" in line:
            key, val = line.split("：", 1)
        else:
            continue
        k = key.strip().lower()
        v = val.strip()

        if k in ("名称", "name", "接口名称", "interface name"):
            cur = {"name": v, "state": "", "ssid": "", "profile": "", "bssid": "", "signal": ""}
            ifaces.append(cur)
            continue
        if cur is None:
            continue
        if "bssid" in k:
            cur["bssid"] = v
            continue
        if k in ("状态", "state"):
            cur["state"] = v
            continue
        if k == "ssid":
            cur["ssid"] = v
            continue
        if k in ("配置文件", "profile"):
            cur["profile"] = v
            continue
        if k in ("信号", "signal"):
            cur["signal"] = v
    return ifaces


def is_wlan_state_connected(state):
    s = str(state or "").strip().lower()
    if not s:
        return False
    if "断开" in s or "disconnect" in s:
        return False
    return ("已连接" in s) or ("connected" in s)


def get_wlan_interfaces():
    if os.name != "nt":
        return []
    code, out, _ = run_cmd(["netsh", "wlan", "show", "interfaces"], timeout=8)
    if code != 0 or not out:
        return []
    return parse_netsh_interfaces(out)


def ssid_matches(ssid, target=None):
    """目标 SSID 匹配：忽略空白/全半角，允许 Windows 重名后缀（" 2"）与可选前缀匹配。"""
    if not ssid:
        return False
    target = WIFI_SSID if target is None else target
    if not target:
        return False

    got = compact_text(ssid)
    if not got:
        return False

    for part in re.split(r"[,;|]", str(target)):
        want = compact_text(part)
        if not want:
            continue
        if got == want:
            return True
        # Windows 给重名 profile 自动加 " 2" / " 3" 后缀
        if re.fullmatch(re.escape(want) + r"\d{1,2}", got):
            return True
        if WIFI_SSID_PREFIX_MATCH and got.startswith(want):
            return True
    return False


def get_connected_wifi_ssid():
    for item in get_wlan_interfaces():
        if is_wlan_state_connected(item.get("state")):
            ssid = str(item.get("ssid") or "").strip()
            if ssid and ssid != "0":
                return ssid
    return ""


def get_connected_wlan():
    for item in get_wlan_interfaces():
        if is_wlan_state_connected(item.get("state")):
            return item
    return {}


def list_wlan_profiles():
    code, out, _ = run_cmd(["netsh", "wlan", "show", "profiles"], timeout=8)
    if code != 0 or not out:
        return []
    names = []
    for line in out.splitlines():
        m = re.match(r"^\s*(?:所有用户配置文件|All User Profile|当前用户配置文件|User Profile)\s*:\s*(.+?)\s*$", line, re.I)
        if m:
            name = m.group(1).strip()
            if name and name not in names:
                names.append(name)
    return names


def wifi_state_path():
    base = os.path.dirname(os.path.abspath(CONFIG_FILE)) if CONFIG_FILE else APP_DIR
    return os.path.join(base or APP_DIR, "wifi_state.json")


def load_wifi_state():
    try:
        with open(wifi_state_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                data.setdefault("last_good", "")
                data.setdefault("bad", [])
                return data
    except Exception:
        pass
    return {"last_good": "", "bad": []}


def save_wifi_state(state):
    try:
        path = wifi_state_path()
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception as err:
        log("DBG", f"wifi_state 写入失败: {short_exc(err)}")


def wifi_profile_candidates():
    """返回可用 profile 名，优先上次成功的、跳过已知失败的。"""
    state = load_wifi_state()
    names = [n for n in list_wlan_profiles() if ssid_matches(n)]
    last_good = state.get("last_good", "")
    if last_good not in names:
        # 自动学习：当前正在用的 profile 就是最可靠的候选
        cur_profile = str((get_connected_wlan() or {}).get("profile") or "").strip()
        if cur_profile in names:
            last_good = cur_profile
        else:
            last_good = ""
    bad = set(state.get("bad") or [])

    head = [last_good] if last_good and last_good in names else []
    rest = [n for n in names if n not in head and n not in bad]
    tail = [n for n in names if n not in head and n in bad]
    return head + rest, head + rest + tail



def is_admin():
    if os.name != "nt":
        return True
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def wlan_radio_software_off():
    """探测 netsh 里的「无线电状态: 软件 关」（WLAN 开关被关掉）。"""
    code, out, _ = run_cmd(["netsh", "wlan", "show", "interfaces"], timeout=8)
    if code != 0 or not out:
        return False
    for line in out.splitlines():
        s = line.strip()
        if "软件" in s and "关" in s and "开" not in s.replace("开关", ""):
            return True
        low = s.lower()
        if "software" in low and "off" in low:
            return True
    return False


def force_wlan_radio_on_via_wlanapi():
    """用 wlanapi 的 WlanSetInterface(wlan_intf_opcode_radio_state) 打开软件无线电。

    这是 Windows 设置里那个 WLAN 开关走的同一条路径。实测：netsh wlan set
    autoconfig、Disable/Enable-NetAdapter 都改不动这个状态。需要管理员权限。
    """
    if os.name != "nt":
        return False
    try:
        import ctypes
        from ctypes import wintypes
    except Exception as err:
        log("WARN", f"ctypes 不可用: {short_exc(err)}")
        return False

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    class WLAN_INTERFACE_INFO(ctypes.Structure):
        _fields_ = [
            ("InterfaceGuid", GUID),
            ("strInterfaceDescription", wintypes.WCHAR * 256),
            ("isState", wintypes.DWORD),
        ]

    class WLAN_INTERFACE_INFO_LIST(ctypes.Structure):
        _fields_ = [
            ("dwNumberOfItems", wintypes.DWORD),
            ("dwIndex", wintypes.DWORD),
            ("InterfaceInfo", WLAN_INTERFACE_INFO * 8),
        ]

    class WLAN_PHY_RADIO_STATE(ctypes.Structure):
        _fields_ = [
            ("dwPhyIndex", wintypes.DWORD),
            ("SoftwareRadioState", wintypes.DWORD),
            ("HardwareRadioState", wintypes.DWORD),
        ]

    OPCODE_RADIO_STATE = 4
    RADIO_HW_SOFT_ON = 1
    ERROR_SUCCESS = 0

    try:
        wlanapi = ctypes.WinDLL("wlanapi.dll")
    except Exception as err:
        log("WARN", f"加载 wlanapi.dll 失败: {short_exc(err)}")
        return False

    handle = wintypes.HANDLE()
    negotiated = wintypes.DWORD()
    rc = wlanapi.WlanOpenHandle(2, None, ctypes.byref(negotiated), ctypes.byref(handle))
    if rc != ERROR_SUCCESS:
        log("WARN", f"WlanOpenHandle 失败 rc={rc}")
        return False

    ok = False
    plist = ctypes.c_void_p()
    try:
        rc = wlanapi.WlanEnumInterfaces(handle, None, ctypes.byref(plist))
        if rc != ERROR_SUCCESS or not plist:
            log("WARN", f"WlanEnumInterfaces 失败 rc={rc}")
            return False
        lst = ctypes.cast(plist, ctypes.POINTER(WLAN_INTERFACE_INFO_LIST)).contents
        if lst.dwNumberOfItems < 1:
            log("WARN", "WlanEnumInterfaces 返回 0 个无线接口")
            return False
        guid = lst.InterfaceInfo[0].InterfaceGuid

        size = wintypes.DWORD()
        data = ctypes.c_void_p()
        opcode_type = wintypes.DWORD()
        rc = wlanapi.WlanQueryInterface(
            handle,
            ctypes.byref(guid),
            OPCODE_RADIO_STATE,
            None,
            ctypes.byref(size),
            ctypes.byref(data),
            ctypes.byref(opcode_type),
        )
        if rc != ERROR_SUCCESS or not data:
            log("WARN", f"WlanQueryInterface 失败 rc={rc}")
            return False

        try:
            if size.value < ctypes.sizeof(WLAN_PHY_RADIO_STATE):
                log("WARN", f"radio_state 结构大小异常 size={size.value}")
                return False
            cur = ctypes.cast(data, ctypes.POINTER(WLAN_PHY_RADIO_STATE)).contents
            hw_state = cur.HardwareRadioState
        finally:
            wlanapi.WlanFreeMemory(data)

        new_state = WLAN_PHY_RADIO_STATE()
        new_state.dwPhyIndex = 0
        new_state.SoftwareRadioState = RADIO_HW_SOFT_ON
        new_state.HardwareRadioState = hw_state
        rc = wlanapi.WlanSetInterface(
            handle,
            ctypes.byref(guid),
            OPCODE_RADIO_STATE,
            ctypes.sizeof(new_state),
            ctypes.byref(new_state),
            None,
        )
        if rc == ERROR_SUCCESS:
            ok = True
            log("OK", "已通过 wlanapi 下发无线电开启指令")
        else:
            log("WARN", f"WlanSetInterface 失败 rc={rc}（5=拒绝访问 87=参数错误 1168=元素未找到）")
    finally:
        if plist:
            try:
                wlanapi.WlanFreeMemory(plist)
            except Exception:
                pass
        try:
            wlanapi.WlanCloseHandle(handle, None)
        except Exception:
            pass
    return ok


def force_enable_wlan_radio():
    """把「无线电状态: 软件 关」翻回「开」。

    三级：① wlanapi（设置页同款 API，实测无需管理员即可生效）
          ② netsh autoconfig ③ 重置适配器（②③ 需要管理员）。
    """
    names = get_wifi_adapter_names() or get_wlan_names_from_netsh() or ["WLAN"]

    if force_wlan_radio_on_via_wlanapi():
        time.sleep(2)
        if not wlan_radio_software_off():
            log("OK", "WLAN 无线电软件开关已打开（wlanapi）")
            return True
        # netsh 状态可能滞后：wlanapi 报成功就先放行，让后续 connect 去验证
        log("INFO", "wlanapi 已上报成功，但 netsh 仍显示软件关，继续尝试连接")
        return True

    if not is_admin():
        log("WARN", "非管理员：跳过需要提权的兜底方法（netsh autoconfig / 重置适配器）")
        return False

    for name in names:
        run_cmd(["netsh", "wlan", "set", "autoconfig", "enabled=yes", f"interface={name}"], timeout=10)
    time.sleep(1.5)
    if not wlan_radio_software_off():
        log("OK", "WLAN 无线电软件开关已打开（autoconfig）")
        return True

    for name in names:
        quoted = ps_single_quote(name)
        run_powershell(
            (
                f"$n='{quoted}'; "
                "try { Disable-NetAdapter -Name $n -Confirm:$false -ErrorAction SilentlyContinue } catch {}; "
                "Start-Sleep -Seconds 3; "
                "try { Enable-NetAdapter -Name $n -Confirm:$false -ErrorAction SilentlyContinue } catch {}"
            ),
            timeout=40,
        )
    time.sleep(4)
    if not wlan_radio_software_off():
        log("OK", "WLAN 无线电软件开关已打开（重置适配器）")
        return True

    log("WARN", "尝试打开 WLAN 无线电失败（可能被硬件开关或组策略锁住）")
    return False


def enable_wifi_interfaces(force=False):
    """只在接口确实被禁用时才启用它，避免反复 reset 掉正常的链路。"""
    run_cmd(["sc", "start", "WlanSvc"], timeout=8)

    names = get_wifi_adapter_names()
    if not names:
        names = get_wlan_names_from_netsh()

    for name in names:
        run_cmd(["netsh", "wlan", "set", "autoconfig", "enabled=yes", f"interface={name}"], timeout=8)

    if not force:
        return

    if not names:
        names = ["Wi-Fi", "WLAN", "无线网络连接", "无线网络"]

    for name in names:
        quoted = ps_single_quote(name)
        run_powershell(
            (
                f"$n='{quoted}'; "
                "$a = Get-NetAdapter -Name $n -ErrorAction SilentlyContinue; "
                "if ($a -and $a.Status -eq 'Disabled') { "
                "  try { Enable-NetAdapter -Name $n -Confirm:$false -ErrorAction Stop | Out-Null; exit 0 } "
                "  catch { exit 1 } "
                "} else { exit 0 }"
            ),
            timeout=10,
        )



def add_open_wifi_profile(ssid):
    """写入开放网络 profile。

    注意：不要用 <name> 让 netsh 自己转编码——中文 SSID 会被按 ANSI(GBK) 写进
    802.11 SSID 字段，造出一个空气里不存在的"影子 SSID"，connect 必然失败。
    这里显式给出 UTF-8 字节的 <hex>，与 AP 广播字节保持一致。
    """
    if not ssid:
        return False

    hex_ssid = ssid.encode("utf-8").hex().upper()
    profile_xml = (
        '<?xml version="1.0"?>\n'
        '<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">\n'
        f"  <name>{xml_escape(ssid)}</name>\n"
        "  <SSIDConfig>\n"
        "    <SSID>\n"
        f"      <hex>{hex_ssid}</hex>\n"
        f"      <name>{xml_escape(ssid)}</name>\n"
        "    </SSID>\n"
        "    <nonBroadcast>false</nonBroadcast>\n"
        "  </SSIDConfig>\n"
        "  <connectionType>ESS</connectionType>\n"
        "  <connectionMode>auto</connectionMode>\n"
        "  <MSM>\n"
        "    <security>\n"
        "      <authEncryption>\n"
        "        <authentication>open</authentication>\n"
        "        <encryption>none</encryption>\n"
        "        <useOneX>false</useOneX>\n"
        "      </authEncryption>\n"
        "    </security>\n"
        "  </MSM>\n"
        "</WLANProfile>\n"
    )
    fd, tmp_path = tempfile.mkstemp(prefix="campus_wifi_", suffix=".xml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(profile_xml)
        for scope in ("current", "all"):
            code, _, err = run_cmd(
                ["netsh", "wlan", "add", "profile", f"filename={tmp_path}", f"user={scope}"],
                timeout=8,
            )
            if code == 0:
                log("INFO", f"已写入 WLAN profile: {ssid} (scope={scope}, ssid_bytes_hex={hex_ssid})")
                return True
            if DEBUG_QUERY_FETCH:
                log("DBG", f"add profile scope={scope} 失败: {err}")
        return False
    except Exception as err:
        log("WARN", f"写入 profile 失败: {short_exc(err)}")
        return False
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


def wait_for_wlan_connection(timeout):
    deadline = time.time() + max(1, timeout)
    while time.time() < deadline:
        item = get_connected_wlan()
        if item and ssid_matches(item.get("ssid")):
            return True, item
        time.sleep(1.0)
    return False, get_connected_wlan()


def connect_wifi_ssid(ssid=None, force=False):
    """确保 WLAN 连到目标 SSID。

    force=False 时只要当前已连到目标 SSID 就什么都不做——绝不对健康链路
    调 netsh wlan connect（那会先断开现有连接）。
    """
    target = (ssid or WIFI_SSID or "").strip()
    if not target:
        return False, "SSID为空"

    current = get_connected_wlan()
    if current and ssid_matches(current.get("ssid"), target):
        if not force:
            return True, current.get("ssid", "")
        # force 场景下也不重复连接同一 profile
        return True, current.get("ssid", "")

    ifaces = get_wifi_adapter_names() or [""]
    iface = ifaces[0] if ifaces else ""

    tried, all_candidates = wifi_profile_candidates()
    if not all_candidates and WIFI_AUTO_ADD_PROFILE:
        if add_open_wifi_profile(target):
            tried = [target]

    if not tried:
        log("WARN", f"没有找到与 {target} 匹配的 WLAN profile（wifi_auto_add_profile=false）")
        return False, f"无可用 profile: {target}"

    state = load_wifi_state()
    bad = set(state.get("bad") or [])

    last_err = ""
    for name in tried:
        cmd = ["netsh", "wlan", "connect", f"name={name}"]
        if iface:
            cmd.append(f"interface={iface}")
        run_cmd(cmd, timeout=10)
        ok, item = wait_for_wlan_connection(WIFI_CONNECT_WAIT)
        if ok:
            state["last_good"] = name
            state["bad"] = sorted(bad - {name})
            save_wifi_state(state)
            return True, f"{item.get('ssid')} via profile={name}"
        last_err = f"profile={name} 未连上"

    # 全部失败：把所有候选记为可疑，下次换序重试
    state["bad"] = sorted(bad | set(tried))
    save_wifi_state(state)
    now = get_connected_wlan()
    return False, f"{last_err}（当前: {now.get('ssid') or '未连接'}）"



def _recovery_cooldown():
    """成功恢复后的冷却时长（防抖，避免反复折腾链路）。"""
    return max(1, int(WIFI_RETRY_INTERVAL), int(WIFI_RECOVERY_COOLDOWN))


def maybe_prepare_network_link(fail_streak=0):
    """联网失败时的 WLAN 兜底。

    三层保护，避免把一条本来正常的链路折腾断：
      1) 只要已连到目标 SSID（含 " 2" 之类的重名 profile），直接返回，绝不 connect；
      2) 连续失败次数不足 wifi_recovery_after_fails 时不动手（去抖，滤掉漫游抖动）；
      3) 两次动手之间至少间隔 wifi_recovery_cooldown 秒。
    """
    global LAST_WIFI_RECOVERY_TS

    if os.name != "nt":
        return False
    if not AUTO_WIFI_RECOVERY:
        return False

    eth_name = get_ethernet_connected_adapter()
    if eth_name:
        log("DBG", f"检测到以太网已连接({eth_name})，跳过WLAN切换")
        return False

    if not WIFI_SSID:
        log("WARN", "未配置 wifi_ssid，跳过WLAN自动连接")
        return False

    for item in get_wlan_interfaces():
        if is_wlan_state_connected(item.get("state")) and ssid_matches(item.get("ssid")):
            return False

    need = max(1, int(WIFI_RECOVERY_AFTER_FAILS))
    if fail_streak < need:
        log("DBG", f"WLAN未连到目标，但连续失败{fail_streak}/{need}，暂不干预")
        return False

    cooldown = _recovery_cooldown()
    now = time.time()
    if now - LAST_WIFI_RECOVERY_TS < cooldown:
        log("DBG", f"WLAN恢复冷却中（{int(cooldown - (now - LAST_WIFI_RECOVERY_TS))}s）")
        return False
    LAST_WIFI_RECOVERY_TS = now

    current = get_connected_wlan()
    if current:
        log("INFO", f"当前WLAN: {current.get('ssid') or '?'}，目标: {WIFI_SSID}，尝试切换")
    else:
        log("INFO", f"WLAN未连接，尝试连接: {WIFI_SSID}")

    enable_wifi_interfaces(force=True)
    time.sleep(2)

    has_iface = bool(get_wifi_adapter_names() or get_wlan_names_from_netsh())
    radio_off = wlan_radio_software_off()
    if (not has_iface) or radio_off:
        log("INFO", f"WLAN 不可用（接口存在={has_iface}, 软件开关关闭={radio_off}），尝试恢复")
        if is_admin():
            forced = force_enable_wlan_radio()
            time.sleep(2)
            has_iface = bool(get_wifi_adapter_names() or get_wlan_names_from_netsh())
            radio_off = wlan_radio_software_off()
            if forced and radio_off:
                # wlanapi 已下发成功，netsh 可能滞后，放行去连
                radio_off = False
        else:
            log("WARN", "非管理员权限，无法程序化打开 WLAN 开关；请手动打开，或让脚本以管理员计划任务运行")

    if (not has_iface) or radio_off:
        log("WARN", f"WLAN 仍不可用：接口存在={has_iface} 软件开关关闭={radio_off}，{WIFI_RECOVERY_RETRY}s 后重试")
        LAST_WIFI_RECOVERY_TS = time.time() - _recovery_cooldown() + max(10, int(WIFI_RECOVERY_RETRY))
        return False

    ok, info = connect_wifi_ssid(WIFI_SSID)
    if ok:
        LAST_WIFI_RECOVERY_TS = time.time()
        log("OK", f"WLAN已连接: {info}")
        return True

    LAST_WIFI_RECOVERY_TS = time.time() - _recovery_cooldown() + max(10, int(WIFI_RECOVERY_RETRY))
    log("WARN", f"WLAN连接未确认成功: {info}，{WIFI_RECOVERY_RETRY}s 后重试")
    return False



class NetClient:
    def __init__(self):
        self.req = requests.Session()
        self.req.verify = VERIFY_TLS
        self.req.headers.update(
            {
                "User-Agent": UA,
                "Accept": "*/*",
                "Origin": BASE_URL,
                "Referer": f"{BASE_URL}/eportal/",
            }
        )

        self.curl = None
        if curl_requests is not None:
            self.curl = curl_requests.Session()
            self.curl.verify = VERIFY_TLS
            self.curl.headers.update(
                {
                    "User-Agent": UA,
                    "Accept": "*/*",
                    "Origin": BASE_URL,
                    "Referer": f"{BASE_URL}/eportal/",
                }
            )

    def _use_curl_for_url(self, url):
        return (
            USE_CURL_CFFI_FOR_PORTAL_HTTPS
            and self.curl is not None
            and url.startswith(f"https://{CAPTIVE_HOST}")
        )

    def request(self, method, url, timeout=10, allow_redirects=True, data=None, headers=None):
        if self._use_curl_for_url(url):
            return self.curl.request(
                method,
                url,
                timeout=timeout,
                allow_redirects=allow_redirects,
                data=data,
                headers=headers,
                impersonate=CURL_IMPERSONATE,
            )

        try:
            return self.req.request(
                method,
                url,
                timeout=timeout,
                allow_redirects=allow_redirects,
                data=data,
                headers=headers,
            )
        except requests.exceptions.SSLError:
            if self.curl is not None and url.startswith("https://"):
                log("WARN", f"TLS切换到curl_cffi: {url}")
                return self.curl.request(
                    method,
                    url,
                    timeout=timeout,
                    allow_redirects=allow_redirects,
                    data=data,
                    headers=headers,
                    impersonate=CURL_IMPERSONATE,
                )
            raise


def e2(value):
    return quote(quote(value or "", safe=""), safe="")


def extract_query_from_url(url):
    if not url:
        return ""

    try:
        parsed = urlparse(url)
    except Exception:
        return ""

    host = parsed.netloc.lower()
    path = parsed.path
    if CAPTIVE_HOST in host and path.endswith(CAPTIVE_PATH):
        return parsed.query

    if not host and path.endswith(CAPTIVE_PATH) and parsed.query:
        return parsed.query

    return ""


def extract_query_from_text(text):
    if not text:
        return ""

    data = html.unescape(text)

    for m in re.finditer(
        r"(?:top\.self|self|window)?\.?location(?:\.href)?\s*=\s*['\"]([^'\"]+)['\"]",
        data,
        re.I,
    ):
        q = extract_query_from_url(m.group(1))
        if q:
            return q

    for m in re.finditer(r"https?://login\.dgut\.edu\.cn/eportal/index\.jsp\?([^\"'\s<>]+)", data, re.I):
        if m.group(1):
            return m.group(1)
    for m in re.finditer(r"/eportal/index\.jsp\?([^\"'\s<>]+)", data, re.I):
        if m.group(1):
            return m.group(1)

    return ""


def find_captive_query_in_response(resp):
    location = resp.headers.get("Location", "")

    q = extract_query_from_url(location)
    if q:
        return q, "location"

    q = extract_query_from_url(resp.url)
    if q:
        return q, "url"

    q = extract_query_from_text(getattr(resp, "text", ""))
    if q:
        return q, "html/js"

    return "", ""


def find_captive_query_in_chain(resp):
    history = getattr(resp, "history", []) or []
    for idx, item in enumerate(history):
        q, src = find_captive_query_in_response(item)
        if q:
            return q, f"history[{idx}]-{src}"

    q, src = find_captive_query_in_response(resp)
    if q:
        return q, f"final-{src}"

    return "", ""


def normalize_raw_query(query_string):
    if not query_string:
        return ""

    s = query_string.strip()
    if not s:
        return ""

    if s.startswith("http://") or s.startswith("https://"):
        q = extract_query_from_url(s)
        if q:
            s = q

    s = s.lstrip("?")
    s = html.unescape(s)

    if "&" not in s and "=" not in s and ("%3D" in s or "%26" in s):
        decoded_once = unquote(s)
        if "&" in decoded_once and "=" in decoded_once:
            return decoded_once

    return s


def summarize_login_response(text):
    s = (text or "").strip()
    try:
        obj = json.loads(s)
        result = obj.get("result", "?")
        msg = obj.get("message") or "-"
        user_index = obj.get("userIndex")
        if result == "success":
            if user_index:
                return f"result=success userIndex={str(user_index)[:20]}..."
            return "result=success"
        return f"result={result} msg={msg}"
    except Exception:
        pass

    if len(s) > 180:
        return s[:177] + "..."
    return s or "(empty)"


def check_internet(client, timeout=6):
    test_urls = [
        "https://www.baidu.com",
        "https://www.bing.com",
    ]

    reasons = []
    for test_url in test_urls:
        host = urlparse(test_url).netloc or test_url
        try:
            resp = client.request("GET", test_url, timeout=timeout, allow_redirects=True)
        except Exception as err:
            reasons.append(f"{host}:{classify_error(err)}")
            continue

        q, src = find_captive_query_in_chain(resp)
        if q:
            reasons.append(f"{host}:portal({src})")
            continue

        return True, f"{host}:OK({resp.status_code})"

    return False, " | ".join(reasons) if reasons else "全部失败"


def get_captive_query_string(client, timeout=8):
    probe_urls = [
        "http://10.60.0.1",
        "http://1.1.1.1",
        "http://114.114.114.114",
        "http://www.baidu.com",
        "https://www.baidu.com",
        "http://www.msftconnecttest.com/redirect",
        "http://connect.rom.miui.com/generate_204",
    ]

    for probe_url in probe_urls:
        if DEBUG_QUERY_FETCH:
            log("DBG", f"probe {probe_url}")

        try:
            resp = client.request("GET", probe_url, timeout=timeout, allow_redirects=False)
            if DEBUG_QUERY_FETCH:
                log("DBG", f"nr {resp.status_code} loc={resp.headers.get('Location', '')}")
            q, src = find_captive_query_in_response(resp)
            if q:
                if DEBUG_QUERY_FETCH:
                    log("DBG", f"hit {src}")
                return q
        except Exception as err:
            if DEBUG_QUERY_FETCH:
                log("DBG", f"nr err {classify_error(err)}")

        try:
            resp2 = client.request("GET", probe_url, timeout=timeout, allow_redirects=True)
            if DEBUG_QUERY_FETCH:
                log("DBG", f"fr {resp2.status_code} hist={len(getattr(resp2, 'history', []) or [])}")
            q, src = find_captive_query_in_chain(resp2)
            if q:
                if DEBUG_QUERY_FETCH:
                    log("DBG", f"hit {src}")
                return q
        except Exception as err:
            if DEBUG_QUERY_FETCH:
                log("DBG", f"fr err {classify_error(err)}")
            continue

    if DEBUG_QUERY_FETCH:
        log("DBG", "queryString not found")
    return ""


def parse_page_info_json(text):
    if not text:
        return {}

    s = text.strip()
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        pass

    m = re.search(r"\{.*\}", s, re.S)
    if not m:
        return {}
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def fetch_page_info(client, raw_query, timeout=8):
    page_query = quote(raw_query, safe="")
    body = f"queryString={page_query}"
    try:
        resp = client.request(
            "POST",
            f"{BASE_URL}/eportal/InterFace.do?method=pageInfo",
            data=body,
            timeout=timeout,
            allow_redirects=True,
            headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
        )
        return parse_page_info_json(getattr(resp, "text", ""))
    except Exception as err:
        log("WARN", f"pageInfo失败: {classify_error(err)}")
        return {}


def js_like_hex_from_int(value):
    if value == 0:
        return "0000"
    parts = []
    n = value
    while n > 0:
        parts.append(n & 0xFFFF)
        n >>= 16
    return "".join(f"{p:04x}" for p in reversed(parts))


def rsa_encrypt_legacy_js_style(plain_text, exponent_hex, modulus_hex):
    e = int(exponent_hex, 16)
    m = int(modulus_hex, 16)

    modulus_digits = []
    tmp = m
    while tmp > 0:
        modulus_digits.append(tmp & 0xFFFF)
        tmp >>= 16

    high_index = max(len(modulus_digits) - 1, 0)
    chunk_size = 2 * high_index
    if chunk_size <= 0:
        raise ValueError("invalid RSA chunk size")

    a = [ord(ch) for ch in plain_text]
    while len(a) % chunk_size != 0:
        a.append(0)

    blocks = []
    for i in range(0, len(a), chunk_size):
        block = 0
        j = 0
        k = i
        while k < i + chunk_size:
            digit = a[k]
            k += 1
            digit += a[k] << 8
            k += 1
            block += digit << (16 * j)
            j += 1

        crypt = pow(block, e, m)
        blocks.append(js_like_hex_from_int(crypt))

    return " ".join(blocks)


def build_login_payload(raw_query, page_info):
    page_encrypt_flag = str(page_info.get("passwordEncrypt", "")).lower() == "true"
    exponent = str(page_info.get("publicKeyExponent", "")).strip()
    modulus = str(page_info.get("publicKeyModulus", "")).strip()
    has_key = bool(exponent and modulus)

    need_encrypt = has_key and (FORCE_RSA_ENCRYPT or page_encrypt_flag)

    if need_encrypt:
        mac = parse_qs(raw_query, keep_blank_values=True).get("mac", [""])[0] or "111111111"
        src = f"{PASSWORD}>{mac}"
        encrypted = rsa_encrypt_legacy_js_style(src[::-1], exponent, modulus)
        password_to_send = encrypted
        encrypt_flag = "true"
        mode = "RSA"
    else:
        password_to_send = PASSWORD
        encrypt_flag = "false"
        mode = "PLAINTEXT"
        if FORCE_RSA_ENCRYPT and not has_key:
            mode += "(no-key-fallback)"

    body = (
        f"userId={e2(USER_ID)}"
        f"&password={e2(password_to_send)}"
        f"&service={e2('')}"
        f"&queryString={e2(raw_query)}"
        f"&operatorPwd={e2('')}"
        f"&operatorUserId={e2('')}"
        f"&validcode="
        f"&passwordEncrypt={e2(encrypt_flag)}"
    )
    return body, mode


def login_campus_network(client):
    if not USER_ID or not PASSWORD:
        log("ERR", "缺少配置: user_id / password")
        return False

    raw_query = ""
    for i in range(1, QUERY_FETCH_RETRIES + 1):
        fetched_query = get_captive_query_string(client)
        raw_query = normalize_raw_query(fetched_query or CAPTIVE_QUERY_STRING)
        if raw_query:
            break
        if i < QUERY_FETCH_RETRIES:
            log("WARN", f"抓取queryString失败，{QUERY_FETCH_RETRY_DELAY}s后重试({i}/{QUERY_FETCH_RETRIES})")
            time.sleep(QUERY_FETCH_RETRY_DELAY)

    if not raw_query:
        log("ERR", "未获取到 queryString")
        return False

    log("INFO", f"queryString长度: {len(raw_query)}")

    page_info = fetch_page_info(client, raw_query)
    has_key = bool(page_info.get("publicKeyExponent") and page_info.get("publicKeyModulus"))
    log("INFO", f"pageInfo passwordEncrypt={page_info.get('passwordEncrypt')} hasKey={has_key}")

    login_body, mode = build_login_payload(raw_query, page_info)
    log("INFO", f"登录模式: {mode}")

    index_url = f"{BASE_URL}/eportal/index.jsp?{raw_query}"
    try:
        client.request("GET", index_url, timeout=8, allow_redirects=True)
    except Exception:
        pass

    try:
        resp = client.request(
            "POST",
            f"{BASE_URL}/eportal/InterFace.do?method=login",
            data=login_body,
            timeout=10,
            allow_redirects=True,
            headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
        )
    except Exception as err:
        log("ERR", f"登录请求失败: {classify_error(err)}")
        return False

    log("INFO", f"登录返回: {summarize_login_response(getattr(resp, 'text', ''))}")

    ok, check_reason = check_internet(client, timeout=8)
    if ok:
        log("OK", f"联网成功: {check_reason}")
    else:
        log("WARN", f"登录后仍未联网: {check_reason}")
    return ok


INTERNET_FAIL_STREAK = 0
LOGIN_FAIL_STREAK = 0
LOGIN_FAIL_TS = 0.0


def run_once():
    global INTERNET_FAIL_STREAK, LOGIN_FAIL_STREAK, LOGIN_FAIL_TS

    if USE_CURL_CFFI_FOR_PORTAL_HTTPS and curl_requests is None:
        log("WARN", "未安装 curl_cffi，portal HTTPS 可能握手失败")

    client = NetClient()

    connected, reason = check_internet(client)
    if connected:
        if INTERNET_FAIL_STREAK:
            log("OK", f"网络已恢复（此前连续失败 {INTERNET_FAIL_STREAK} 次）: {reason}")
        else:
            log("OK", f"已联网: {reason}")
        INTERNET_FAIL_STREAK = 0
        LOGIN_FAIL_STREAK = 0
        return

    INTERNET_FAIL_STREAK += 1

    recovered = maybe_prepare_network_link(INTERNET_FAIL_STREAK)
    if recovered:
        connected, reason = check_internet(client, timeout=8)
        if connected:
            INTERNET_FAIL_STREAK = 0
            log("OK", f"WLAN恢复后已联网: {reason}")
            return

    # 连链路都没有时，认证必然失败，不必空跑抓 queryString
    if not get_ethernet_connected_adapter() and not get_connected_wlan():
        log("WARN", "当前无可用链路（以太网未连接、WLAN未连上），本轮跳过认证")
        return

    backoff = max(0, int(LOGIN_FAIL_BACKOFF))
    if backoff and LOGIN_FAIL_STREAK:
        wait_left = backoff * min(LOGIN_FAIL_STREAK, 4) - (time.time() - LOGIN_FAIL_TS)
        if wait_left > 0:
            log("DBG", f"认证退避中（连续失败 {LOGIN_FAIL_STREAK} 次，{int(wait_left)}s 后重试）")
            return

    log("INFO", f"未联网（连续失败 {INTERNET_FAIL_STREAK} 次），开始认证: {reason}")
    success = login_campus_network(client)
    if success:
        INTERNET_FAIL_STREAK = 0
        LOGIN_FAIL_STREAK = 0
    else:
        LOGIN_FAIL_STREAK += 1
        LOGIN_FAIL_TS = time.time()
        log("ERR", f"自动认证失败（连续 {LOGIN_FAIL_STREAK} 次）")



def _script_mtime():
    """脚本或配置被改动的最近时间，用于自动重载。"""
    newest = 0.0
    try:
        newest = os.path.getmtime(os.path.abspath(__file__))
    except Exception:
        pass
    try:
        if CONFIG_FILE and os.path.exists(CONFIG_FILE):
            newest = max(newest, os.path.getmtime(CONFIG_FILE))
    except Exception:
        pass
    return newest


def run_loop(interval):
    log(
        "INFO",
        f"循环模式启动，间隔 {interval}s，进程PID={os.getpid()}，"
        f"权限={'管理员' if is_admin() else '普通用户（无法启停网卡/打开WLAN开关）'}",
    )
    start_mtime = _script_mtime()
    while True:
        try:
            run_once()
        except Exception as err:
            log("ERR", f"循环异常: {short_exc(err)}")
        time.sleep(interval)

        # 脚本被改动就原地重载：继承当前令牌（管理员身份不会丢），省得手工重启
        now_mtime = _script_mtime()
        if now_mtime and now_mtime != start_mtime:
            log("INFO", "检测到脚本或配置已更新，重载自身")
            try:
                if SINGLE_INSTANCE_HANDLE is not None:
                    SINGLE_INSTANCE_HANDLE.close()
            except Exception:
                pass
            try:
                os.execv(
                    sys.executable,
                    [sys.executable, os.path.abspath(__file__), "--loop", "--interval", str(interval)],
                )
                return
            except Exception as err:
                log("ERR", f"自载失败，继续用旧代码运行: {short_exc(err)}")
                start_mtime = now_mtime


def parse_interval(argv):
    if "--interval" not in argv:
        return LOOP_INTERVAL
    idx = argv.index("--interval")
    if idx + 1 >= len(argv):
        return LOOP_INTERVAL
    try:
        val = int(argv[idx + 1])
        return val if val > 0 else LOOP_INTERVAL
    except Exception:
        return LOOP_INTERVAL


def main():
    if not os.path.exists(CONFIG_FILE):
        log("WARN", f"未找到配置文件: {CONFIG_FILE}")

    loop_mode = "--loop" in sys.argv
    interval = parse_interval(sys.argv)

    if loop_mode:
        lock_base_dir = os.path.dirname(os.path.abspath(CONFIG_FILE)) if CONFIG_FILE else APP_DIR
        lock_path = resolve_path("campus_login.lock", lock_base_dir or APP_DIR)
        if not acquire_single_instance_lock(lock_path):
            log("WARN", f"检测到已有循环实例在运行，退出。lock={lock_path}")
            return
        run_loop(interval)
    else:
        run_once()


if __name__ == "__main__":
    main()



