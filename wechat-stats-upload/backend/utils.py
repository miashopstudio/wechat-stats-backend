"""通用工具：登录保护、JSON 响应。"""
from functools import wraps
from flask import session, jsonify, request


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return jsonify({"error": "未登录或登录已失效"}), 401
        return f(*args, **kwargs)
    return wrapper


def get_operator():
    return session.get("username", "admin")


def parse_datetime(value, field="时间"):
    """把前端传来的字符串解析为 datetime，失败给出友好错误。"""
    from datetime import datetime
    if not value:
        raise ValueError(f"{field}不能为空")
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    # 兼容 ISO 含 Z
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{field}格式不正确，请用 YYYY-MM-DD HH:MM")
