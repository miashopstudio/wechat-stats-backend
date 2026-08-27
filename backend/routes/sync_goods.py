"""小程序云开发商品同步接收：POST /api/sync/goods
由微信云函数（主动推送 / 定时触发）调用，用 X-Sync-Token 校验，按 sku upsert 商品。
"""
from flask import Blueprint, request, jsonify
from db import db
from models import Product
from config import Config

sync_goods_bp = Blueprint("sync_goods", __name__, url_prefix="/api/sync")


@sync_goods_bp.route("/goods", methods=["POST"])
def receive_goods():
    # 未配置令牌则关闭此入口
    if not Config.GOODS_SYNC_TOKEN:
        return jsonify({"error": "同步未开启（GOODS_SYNC_TOKEN 未配置）"}), 403
    token = request.headers.get("X-Sync-Token", "")
    if not token or token != Config.GOODS_SYNC_TOKEN:
        return jsonify({"error": "令牌错误"}), 401

    data = request.get_json(silent=True) or {}
    goods = data.get("goods") or []
    if not isinstance(goods, list):
        return jsonify({"error": "goods 必须为数组"}), 400

    upserted = 0
    skipped = 0
    for g in goods:
        sku = str(g.get("sku") or "").strip()
        name = str(g.get("name") or "").strip()
        if not sku or not name:
            skipped += 1
            continue
        try:
            cost = float(g.get("default_cost_price") or 0)
        except (TypeError, ValueError):
            cost = 0.0
        cat1 = str(g.get("category_l1") or "").strip()
        cat2 = str(g.get("category_l2") or "").strip()
        cat3 = str(g.get("category_l3") or "").strip()

        p = Product.query.filter_by(sku=sku).first()
        if p:
            # 仅当云端提供了非空值时覆盖，避免把已有成本/分类清掉
            p.name = name
            if cost or p.default_cost_price == 0:
                p.default_cost_price = cost
            if cat1:
                p.category_l1 = cat1
            if cat2:
                p.category_l2 = cat2
            if cat3:
                p.category_l3 = cat3
        else:
            p = Product(
                name=name, sku=sku, default_cost_price=cost,
                category_l1=cat1, category_l2=cat2, category_l3=cat3,
            )
            db.session.add(p)
        upserted += 1

    db.session.commit()
    return jsonify({
        "ok": True,
        "upserted": upserted,
        "skipped": skipped,
        "message": f"已同步 {upserted} 个商品，跳过 {skipped} 条无效数据",
    })
