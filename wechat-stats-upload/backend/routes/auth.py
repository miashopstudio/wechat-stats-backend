"""认证：单人后台登录 / 登出。session 校验。"""
from flask import Blueprint, request, session, jsonify, current_app
from config import Config

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if username == Config.ADMIN_USERNAME and password == Config.ADMIN_PASSWORD:
        session["logged_in"] = True
        session["username"] = username
        session.permanent = True
        return jsonify({"ok": True, "username": username})
    return jsonify({"error": "账号或密码错误"}), 401


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@auth_bp.route("/me", methods=["GET"])
def me():
    if session.get("logged_in"):
        return jsonify({"logged_in": True, "username": session.get("username")})
    return jsonify({"logged_in": False})
