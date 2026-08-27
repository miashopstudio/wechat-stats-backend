"""活动利润统计：单活动详细报表 + 每日趋势。"""
from datetime import datetime, timedelta
from flask import Blueprint, jsonify
from db import db
from models import Campaign, CampaignItem, OrderSync
from utils import login_required
from services.sync_service import units_of

stats_bp = Blueprint("stats", __name__, url_prefix="/api/campaigns")


def _item_stats(ci: CampaignItem):
    orders = OrderSync.query.filter_by(campaign_item_id=ci.id).all()
    income = 0.0
    units = 0
    for o in orders:
        u = units_of(o.quantity, ci)
        units += u
        income += o.pay_price
    cost = ci.cost_price * units
    profit = income - cost
    rate = (profit / income * 100) if income else 0.0
    return {
        "units": units,                       # 实际售出「组/件」数
        "bundle_sold": units if ci.is_bundle else 0,  # 捆绑按组计
        "income": round(income, 2),
        "cost": round(cost, 2),
        "profit": round(profit, 2),
        "profit_rate": round(rate, 2),
    }


@stats_bp.route("/<int:cid>/stats", methods=["GET"])
@login_required
def campaign_stats(cid):
    c = db.session.get(Campaign, cid)
    if not c:
        return jsonify({"error": "活动不存在"}), 404

    items = []
    total_income = total_cost = total_profit = 0.0
    for it in c.items:
        s = _item_stats(it)
        row = it.to_dict(with_product=True)
        row.update(s)
        items.append(row)
        total_income += s["income"]
        total_cost += s["cost"]
        total_profit += s["profit"]

    # 每日趋势（销售额 / 销量）
    start = c.start_date
    end = c.end_date if c.end_date < datetime.now() else datetime.now()
    trend = []
    day = start
    while day <= end:
        nxt = day + timedelta(days=1)
        day_orders = OrderSync.query.filter(
            OrderSync.campaign_item_id.in_([i.id for i in c.items]),
            OrderSync.order_time >= day,
            OrderSync.order_time < nxt,
        ).all()
        d_income = sum(o.pay_price for o in day_orders)
        d_qty = sum(
            units_of(o.quantity, it)
            for o in day_orders for it in c.items if it.id == o.campaign_item_id
        )
        trend.append({
            "date": day.strftime("%Y-%m-%d"),
            "income": round(d_income, 2),
            "qty": d_qty,
        })
        day = nxt

    archived = c.status == 0
    total_units = sum(i.total_sold_count for i in c.items)

    return jsonify({
        "campaign": c.to_dict(),
        "items": items,
        "total": {
            "income": round(total_income, 2),
            "cost": round(total_cost, 2),
            "profit": round(total_profit, 2),
            "profit_rate": round((total_profit / total_income * 100) if total_income else 0, 2),
            "units": total_units,
        },
        "trend": trend,
        "archived": archived,
        "archived_summary": (
            {"total_sold": total_units, "total_profit": round(total_profit, 2)}
            if archived else None
        ),
    })
