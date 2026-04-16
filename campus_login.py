import html
import json
import logging
import os
import re
import sys
import time
from logging.handlers import RotatingFileHandler
from urllib.parse import parse_qs, quote, unquote, urlparse

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


def run_once():
    if USE_CURL_CFFI_FOR_PORTAL_HTTPS and curl_requests is None:
        log("WARN", "未安装 curl_cffi，portal HTTPS 可能握手失败")

    client = NetClient()

    connected, reason = check_internet(client)
    if connected:
        log("OK", f"已联网: {reason}")
        return

    log("INFO", f"未联网，开始认证: {reason}")
    success = login_campus_network(client)
    if not success:
        log("ERR", "自动认证失败")


def run_loop(interval):
    log("INFO", f"循环模式启动，间隔 {interval}s")
    while True:
        try:
            run_once()
        except Exception as err:
            log("ERR", f"循环异常: {short_exc(err)}")
        time.sleep(interval)


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
        run_loop(interval)
    else:
        run_once()


if __name__ == "__main__":
    main()



