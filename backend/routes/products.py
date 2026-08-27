"""商品管理：增删改查 + 成本修改日志。"""
from flask import Blueprint, request, jsonify
from db import db
from models import Product, CostChangeLog
from utils import login_required, get_operator

products_bp = Blueprint("products", __name__, url_prefix="/api/products")


@products_bp.route("", methods=["GET"])
@login_required
def list_products():
    keyword = (request.args.get("q") or "").strip()
    cat = (request.args.get("cat") or "").strip()  # 按分类筛选（大/中/小任一匹配）
    query = Product.query
    if keyword:
        query = query.filter(
            db.or_(
                Product.name.ilike(f"%{keyword}%"),
                Product.sku.ilike(f"%{keyword}%"),
            )
        )
    if cat:
        query = query.filter(
            db.or_(
                Product.category_l1.ilike(f"%{cat}%"),
                Product.category_l2.ilike(f"%{cat}%"),
                Product.category_l3.ilike(f"%{cat}%"),
            )
        )
    items = query.order_by(Product.id.desc()).all()
    return jsonify([p.to_dict() for p in items])


@products_bp.route("", methods=["POST"])
@login_required
def save_product():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    sku = (data.get("sku") or "").strip()
    cost = float(data.get("default_cost_price") or 0)
    if not name or not sku:
        return jsonify({"error": "商品名称和 SKU 必填"}), 400

    cat1 = (data.get("category_l1") or "").strip()
    cat2 = (data.get("category_l2") or "").strip()
    cat3 = (data.get("category_l3") or "").strip()

    pid = data.get("id")
    if pid:  # 修改
        p = db.session.get(Product, pid)
        if not p:
            return jsonify({"error": "商品不存在"}), 404
        # 成本变化记录日志
        if abs(float(p.default_cost_price) - cost) > 1e-9:
            db.session.add(CostChangeLog(
                product_id=p.id, old_cost=float(p.default_cost_price),
                new_cost=cost, operator=get_operator()
            ))
        p.name = name
        p.sku = sku
        p.default_cost_price = cost
        p.category_l1 = cat1
        p.category_l2 = cat2
        p.category_l3 = cat3
    else:  # 新增
        if Product.query.filter_by(sku=sku).first():
            return jsonify({"error": "SKU 已存在"}), 400
        p = Product(
            name=name, sku=sku, default_cost_price=cost,
            category_l1=cat1, category_l2=cat2, category_l3=cat3,
        )
        db.session.add(p)

    db.session.commit()
    return jsonify(p.to_dict())


@products_bp.route("/<int:pid>", methods=["DELETE"])
@login_required
def delete_product(pid):
    p = db.session.get(Product, pid)
    if not p:
        return jsonify({"error": "商品不存在"}), 404
    db.session.delete(p)
    db.session.commit()
    return jsonify({"ok": True})


@products_bp.route("/<int:pid>/cost-logs", methods=["GET"])
@login_required
def cost_logs(pid):
    logs = CostChangeLog.query.filter_by(product_id=pid).order_by(
        CostChangeLog.change_time.desc()
    ).all()
    return jsonify([l.to_dict() for l in logs])
