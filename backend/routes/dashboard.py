"""数据看板：今日 / 本月 / 上月 收入、成本、利润 + 进行中活动概况。"""
from datetime import datetime, date
from flask import Blueprint, jsonify
from db import db
from models import OrderSync, CampaignItem, Campaign
from utils import login_required
from services.sync_service import units_of

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


def _period_totals(start: datetime, end: datetime):
    """统计某时间段内「活动订单」的收入/成本/利润。"""
    orders = (
        OrderSync.query.filter(
            OrderSync.campaign_item_id.isnot(None),
            OrderSync.order_time >= start,
            OrderSync.order_time < end,
        ).all()
    )
    income = 0.0
    cost = 0.0
    for o in orders:
        ci = db.session.get(CampaignItem, o.campaign_item_id)
        if not ci:
            continue
        units = units_of(o.quantity, ci)
        income += o.pay_price
        cost += ci.cost_price * units
    return {
        "income": round(income, 2),
        "cost": round(cost, 2),
        "profit": round(income - cost, 2),
        "order_count": len(orders),
    }


@dashboard_bp.route("/summary", methods=["GET"])
@login_required
def summary():
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day)
    month_start = datetime(now.year, now.month, 1)
    # 上月
    if now.month == 1:
        last_month_start = datetime(now.year - 1, 12, 1)
    else:
        last_month_start = datetime(now.year, now.month - 1, 1)
    if now.month == 12:
        this_month_next = datetime(now.year + 1, 1, 1)
    else:
        this_month_next = datetime(now.year, now.month + 1, 1)

    active = Campaign.query.filter_by(status=1).all()
    active_sold = 0
    for c in active:
        active_sold += sum(it.total_sold_count for it in c.items)

    return jsonify({
        "today": _period_totals(today_start, now),
        "month": _period_totals(month_start, this_month_next),
        "last_month": _period_totals(last_month_start, month_start),
        "active_campaigns": len(active),
        "active_total_sold": active_sold,
        "generated_at": now.isoformat(),
    })
