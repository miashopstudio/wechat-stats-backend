"""数据同步：微信支付 API 拉取 + CSV 导入兜底 + 订单查询。"""
import io
from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify
from db import db
from models import OrderSync
from utils import login_required
from services.wechat_pay import fetch_trade_bill
from services.sync_service import parse_and_import

sync_bp = Blueprint("sync", __name__, url_prefix="/api/sync")


@sync_bp.route("/orders", methods=["POST"])
@login_required
def pull_wechat():
    """手动触发：按日期从微信支付 API 拉取交易账单并入库。"""
    data = request.get_json(silent=True) or {}
    day_str = data.get("date") or datetime.now().strftime("%Y-%m-%d")
    try:
        day = datetime.strptime(day_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "日期格式应为 YYYY-MM-DD"}), 400
    try:
        csv_text = fetch_trade_bill(day)
    except Exception as e:
        return jsonify({"error": f"微信拉取失败：{e}。可改用 CSV 导入兜底。"}), 502
    result = parse_and_import(csv_text, source=f"wechat:{day_str}")
    return jsonify({"ok": True, "day": day_str, **result})


@sync_bp.route("/orders/import", methods=["POST"])
@login_required
def import_csv():
    """兜底：上传微信导出的交易报表 CSV 进行解析入库。"""
    if "file" not in request.files:
        return jsonify({"error": "未收到文件（字段名 file）"}), 400
    f = request.files["file"]
    raw = f.read()
    # 处理 UTF-8 BOM
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    text = raw.decode("utf-8", errors="ignore")
    try:
        result = parse_and_import(text, source=f"csv:{f.filename}")
    except Exception as e:
        return jsonify({"error": f"解析失败：{e}"}), 400
    return jsonify({"ok": True, **result})


@sync_bp.route("/orders", methods=["GET"])
@login_required
def list_orders():
    """查看已同步订单（可按活动商品过滤）。"""
    campaign_item_id = request.args.get("campaign_item_id", type=int)
    q = OrderSync.query
    if campaign_item_id:
        q = q.filter_by(campaign_item_id=campaign_item_id)
    rows = q.order_by(OrderSync.order_time.desc()).limit(500).all()
    return jsonify([o.to_dict() for o in rows])
