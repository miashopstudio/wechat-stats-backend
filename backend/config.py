"""
集中配置：所有敏感信息都从环境变量读取（见 .env.example）。
数据库默认连 MySQL；若未配置 MYSQL_HOST，则自动回退到本地 SQLite，
方便本地无依赖先跑起来验证。
"""
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # ---- 基础 ----
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-production")
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"

    # ---- 数据库：优先 MySQL（云端保存、多端实时同步），否则 SQLite 兜底 ----
    MYSQL_HOST = os.getenv("MYSQL_HOST")
    if MYSQL_HOST:
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{os.getenv('MYSQL_USER','root')}"
            f":{os.getenv('MYSQL_PASSWORD','')}@{MYSQL_HOST}"
            f":{os.getenv('MYSQL_PORT','3306')}"
            f"/{os.getenv('MYSQL_DB','wechat_stats')}?charset=utf8mb4"
        )
    else:
        SQLALCHEMY_DATABASE_URI = os.getenv(
            "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'wechat_stats.db')}"
        )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 3600}

    # ---- 微信支付 API v3（账单拉取）----
    # 注意：微信支付 v3 用「商户 API 证书私钥」对请求签名，而不是 access_token。
    WX_APPID = os.getenv("WX_APPID")            # 小程序 AppID
    WX_APPSECRET = os.getenv("WX_APPSECRET")    # 小程序 AppSecret（仅用于必要时获取接口调用凭证）
    WX_MCHID = os.getenv("WX_MCHID")            # 微信支付商户号
    WX_API_V3_KEY = os.getenv("WX_API_V3_KEY")  # APIv3 密钥（用于解密资金账单）
    WX_MERCHANT_SERIAL = os.getenv("WX_MERCHANT_SERIAL")  # 商户 API 证书序列号
    WX_PRIVATE_KEY_PATH = os.getenv("WX_PRIVATE_KEY_PATH")  # apiclient_key.pem 路径
    # 云端部署时（如云托管）不便把 .pem 打进镜像：可用 base64 形式的环境变量传入，
    # 启动时自动解码写回文件，避免密钥固化在镜像里。
    if not WX_PRIVATE_KEY_PATH:
        b64 = os.getenv("WX_PRIVATE_KEY_B64")
        if b64:
            import base64

            pem_path = os.path.join(BASE_DIR, "apiclient_key.pem")
            with open(pem_path, "wb") as f:
                f.write(base64.b64decode(b64))
            WX_PRIVATE_KEY_PATH = pem_path
    WX_API_BASE = "https://api.mch.weixin.qq.com"

    # ---- 管理员（单人后台）----
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

    # ---- 小程序云开发商品同步（主动推送校验）----
    # 云函数推送商品时需在请求头带 X-Sync-Token，值与这里一致才接受写入。
    GOODS_SYNC_TOKEN = os.getenv("GOODS_SYNC_TOKEN", "")

    # ---- 前端静态目录（Flask 同源托管，免 CORS）----
    FRONTEND_DIR = os.getenv(
        "FRONTEND_DIR", os.path.join(BASE_DIR, "..", "frontend")
    )
