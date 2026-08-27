"""活动管理：列表 / 新建编辑 / 添加活动商品。"""
from datetime import datetime
from flask import Blueprint, request, jsonify
from db import db
from models import Campaign, CampaignItem, Product
from utils import login_required, parse_datetime

campaigns_bp = Blueprint("campaigns", __name__, url_prefix="/api/campaigns")


def refresh_statuses():
    """活动结束时间已过 -> 自动标记为已结束（存档），仅影响 status!= -1。"""
    now = datetime.now()
    changed = False
    for c in Campaign.query.filter(Campaign.status != -1).all():
        if c.end_date and c.end_date < now and c.status != 0:
            c.status = 0
            changed = True
    if changed:
        db.session.commit()


@campaigns_bp.route("", methods=["GET"])
@login_required
def list_campaigns():
    refresh_statuses()
    include_archived = request.args.get("archived") == "1"
    q = Campaign.query
    if not include_archived:
        q = q.filter(Campaign.status != -1)
    items = q.order_by(Campaign.start_date.desc()).all()
    return jsonify([c.to_dict() for c in items])


@campaigns_bp.route("", methods=["POST"])
@login_required
def save_campaign():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "活动名称必填"}), 400
    try:
        start = parse_datetime(data.get("start_date"), "开始时间")
        end = parse_datetime(data.get("end_date"), "结束时间")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if end <= start:
        return jsonify({"error": "结束时间必须晚于开始时间"}), 400

    cid = data.get("id")
    if cid:
        c = db.session.get(Campaign, cid)
        if not c:
            return jsonify({"error": "活动不存在"}), 404
        c.name, c.start_date, c.end_date = name, start, end
    else:
        c = Campaign(name=name, start_date=start, end_date=end, status=1)
        db.session.add(c)
    db.session.commit()
    return jsonify(c.to_dict())


@campaigns_bp.route("/<int:cid>", methods=["GET"])
@login_required
def get_campaign(cid):
    c = db.session.get(Campaign, cid)
    if not c:
        return jsonify({"error": "活动不存在"}), 404
    data = c.to_dict()
    data["items"] = [it.to_dict(with_product=True) for it in c.items]
    return jsonify(data)


@campaigns_bp.route("/<int:cid>/items", methods=["POST"])
@login_required
def add_items(cid):
    c = db.session.get(Campaign, cid)
    if not c:
        return jsonify({"error": "活动不存在"}), 404
    payload = request.get_json(silent=True) or {}
    rows = payload.get("items") or []
    if not rows:
        return jsonify({"error": "未提供商品"}), 400

    created = []
    for r in rows:
        pid = int(r.get("product_id"))
        product = db.session.get(Product, pid)
        if not product:
            continue
        # 默认带出商品默认成本
        cost = float(r.get("cost_price")) if r.get("cost_price") not in (None, "") else float(product.default_cost_price)
        price = float(r.get("activity_price") or 0)
        is_bundle = bool(r.get("is_bundle", False))
        bundle_qty = int(r.get("bundle_quantity") or 1)
        # 若已存在同商品则更新，否则新增
        existing = CampaignItem.query.filter_by(campaign_id=cid, product_id=pid).first()
        if existing:
            existing.activity_price = price
            existing.cost_price = cost
            existing.is_bundle = is_bundle
            existing.bundle_quantity = bundle_qty
            item = existing
        else:
            item = CampaignItem(
                campaign_id=cid, product_id=pid, activity_price=price,
                cost_price=cost, is_bundle=is_bundle, bundle_quantity=bundle_qty,
            )
            db.session.add(item)
        db.session.flush()
        created.append(item.to_dict(with_product=True))
    db.session.commit()
    return jsonify(created)


@campaigns_bp.route("/<int:cid>/items/<int:item_id>", methods=["DELETE"])
@login_required
def remove_item(cid, item_id):
    item = CampaignItem.query.filter_by(id=item_id, campaign_id=cid).first()
    if not item:
        return jsonify({"error": "活动商品不存在"}), 404
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True})


@campaigns_bp.route("/<int:cid>/hide", methods=["POST"])
@login_required
def hide_campaign(cid):
    c = db.session.get(Campaign, cid)
    if not c:
        return jsonify({"error": "活动不存在"}), 404
    c.status = -1  # 标记隐藏（仅在列表默认不显示，数据永久保留）
    db.session.commit()
    return jsonify({"ok": True})
