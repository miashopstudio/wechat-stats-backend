"""
微信支付 API v3 · 账单拉取客户端（真实对接主路径）。

流程：
  1. 用商户 API 证书私钥对请求签名，构造 Authorization 头。
  2. 调用 /v3/bill/tradebill 获取账单下载地址。
  3. 下载并解压（交易账单为 gzip；资金账单为 AES-256-GCM 加密，需 APIv3 密钥解密）。

凭证均来自 config.py（环境变量）。未配置时相关接口会返回明确错误提示，
不影响 CSV 导入兜底路径使用。
"""
import time
import gzip
import json
import base64
import hashlib
import subprocess
import os
from datetime import datetime, date
import requests
from config import Config


def _load_private_key():
    path = Config.WX_PRIVATE_KEY_PATH
    if not path or not os.path.exists(path):
        raise RuntimeError("未配置商户 API 证书私钥 WX_PRIVATE_KEY_PATH")
    with open(path, "rb") as f:
        return f.read()


def _build_authorization(method: str, url_path: str, body: str = ""):
    """生成微信支付 v3 请求签名 Authorization 头。"""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    private_key = load_pem_private_key(_load_private_key(), password=None)
    serial = Config.WX_MERCHANT_SERIAL
    if not serial:
        raise RuntimeError("未配置商户证书序列号 WX_MERCHANT_SERIAL")
    nonce = hashlib.md5(str(time.time()).encode()).hexdigest()
    timestamp = str(int(time.time()))
    message = f"{method}\n{url_path}\n{timestamp}\n{nonce}\n{body}\n"
    signature = private_key.sign(message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    sign_b64 = base64.b64encode(signature).decode()
    return (
        f'WECHATPAY2-SHA256-RSA2048 '
        f'mchid="{Config.WX_MCHID}",nonce_str="{nonce}",'
        f'signature="{sign_b64}",timestamp="{timestamp}",serial_no="{serial}"'
    )


def _http_get(url_path: str):
    url = Config.WX_API_BASE + url_path
    headers = {
        "Authorization": _build_authorization("GET", url_path),
        "Accept": "application/json",
        "User-Agent": "wechat-stats-backend/1.0",
    }
    resp = requests.get(url, headers=headers, timeout=30)
    return resp


def fetch_trade_bill(day: date):
    """
    拉取指定日期的交易账单原文（gzip 解压后的 CSV 文本）。
    返回 CSV 字符串；失败抛异常。
    """
    if not Config.WX_MCHID:
        raise RuntimeError("未配置微信支付商户号 WX_MCHID")
    url_path = (
        f"/v3/bill/tradebill?bill_date={day.strftime('%Y-%m-%d')}"
        f"&bill_type=ALL"
    )
    resp = _http_get(url_path)
    if resp.status_code != 200:
        raise RuntimeError(f"微信账单接口返回 {resp.status_code}: {resp.text}")
    data = resp.json()
    download_url = data.get("download_url")
    if not download_url:
        raise RuntimeError("账单接口未返回下载地址")
    # 下载账单文件（gzip）。注意：微信账单文件接口同样需要商户签名头
    from urllib.parse import urlparse

    dl = urlparse(download_url)
    dl_path = dl.path + (("?" + dl.query) if dl.query else "")
    dl_auth = _build_authorization("GET", dl_path)
    r = requests.get(
        download_url,
        headers={"Authorization": dl_auth, "Accept": "application/gzip,application/octet-stream"},
        timeout=60,
    )
    r.raise_for_status()
    raw = r.content
    # 交易账单为 gzip；资金账单为加密（需 AES 解密）—这里处理交易账单
    try:
        csv_text = gzip.decompress(raw).decode("utf-8")
    except (OSError, gzip.BadGzipFile):
        # 兜底：可能是已解压文本
        csv_text = raw.decode("utf-8", errors="ignore")
    return csv_text


# ----------------- 资金账单 AES-256-GCM 解密（如需） -----------------
def decrypt_fund_bill(ciphertext_b64: str, nonce_b64: str, associated_b64: str):
    """解密微信资金账单（APIv3 密钥）。依赖 openssl 命令行。"""
    import subprocess
    key = Config.WX_API_V3_KEY.encode()
    ct = base64.b64decode(ciphertext_b64)
    nonce = base64.b64decode(nonce_b64)
    assoc = base64.b64decode(associated_b64)
    # 用 openssl 不便直接做 GCM，这里给出 Python 实现占位（需 cryptography 的 AESGCM）
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ct, assoc)
    return plaintext
