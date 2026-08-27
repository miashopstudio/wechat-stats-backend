"""历史存档查询 + Excel 导出。"""
from io import BytesIO
from datetime import datetime
from flask import Blueprint, jsonify, request, send_file
from db import db
from models import Campaign, CampaignItem, OrderSync
from utils import login_required
from services.sync_service import units_of

archive_bp = Blueprint("archive", __name__, url_prefix="/api/archive")


def _campaign_total(c: Campaign):
    total_income = total_cost = total_profit = 0.0
    units = 0
    for it in c.items:
        orders = OrderSync.query.filter_by(campaign_item_id=it.id).all()
        inc = sum(o.pay_price for o in orders)
        u = sum(units_of(o.quantity, it) for o in orders)
        cost = it.cost_price * u
        total_income += inc
        total_cost += cost
        total_profit += inc - cost
        units += it.total_sold_count
    return {
        "income": round(total_income, 2),
        "cost": round(total_cost, 2),
        "profit": round(total_profit, 2),
        "profit_rate": round((total_profit / total_income * 100) if total_income else 0, 2),
        "units": units,
    }


@archive_bp.route("", methods=["GET"])
@login_required
def list_archive():
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    q = Campaign.query.filter_by(status=0)  # 仅已结束
    camps = q.order_by(Campaign.end_date.desc()).all()
    out = []
    for c in camps:
        if year and c.end_date.year != year:
            continue
        if month and c.end_date.month != month:
            continue
        t = _campaign_total(c)
        d = c.to_dict()
        d.update(t)
        out.append(d)
    return jsonify(out)


@archive_bp.route("/export", methods=["GET"])
@login_required
def export_excel():
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)

    camps = Campaign.query.filter_by(status=0).order_by(Campaign.end_date.desc()).all()
    rows_summary = []
    rows_detail = []
    for c in camps:
        if year and c.end_date.year != year:
            continue
        if month and c.end_date.month != month:
            continue
        t = _campaign_total(c)
        rows_summary.append({
            "活动名称": c.name,
            "开始": c.start_date.strftime("%Y-%m-%d"),
            "结束": c.end_date.strftime("%Y-%m-%d"),
            "总销量": t["units"],
            "总收入": t["income"],
            "总成本": t["cost"],
            "总利润": t["profit"],
            "利润率(%)": t["profit_rate"],
        })
        for it in c.items:
            orders = OrderSync.query.filter_by(campaign_item_id=it.id).all()
            inc = sum(o.pay_price for o in orders)
            u = sum(units_of(o.quantity, it) for o in orders)
            cost = it.cost_price * u
            rows_detail.append({
                "活动名称": c.name,
                "商品": it.product.name if it.product else "",
                "SKU": it.product.sku if it.product else "",
                "活动售价": it.activity_price,
                "该期成本": it.cost_price,
                "是否捆绑": "是" if it.is_bundle else "否",
                "销量(组/件)": u,
                "收入": round(inc, 2),
                "成本": round(cost, 2),
                "利润": round(inc - cost, 2),
            })

    from openpyxl import Workbook
    wb = Workbook()
    ws1 = wb.active
    ws1.title = "活动盈亏汇总"
    headers1 = ["活动名称", "开始", "结束", "总销量", "总收入", "总成本", "总利润", "利润率(%)"]
    ws1.append(headers1)
    for r in rows_summary:
        ws1.append([r[h] for h in headers1])

    ws2 = wb.create_sheet("活动商品明细")
    headers2 = ["活动名称", "商品", "SKU", "活动售价", "该期成本", "是否捆绑", "销量(组/件)", "收入", "成本", "利润"]
    ws2.append(headers2)
    for r in rows_detail:
        ws2.append([r[h] for h in headers2])

    # 简单列宽
    for ws in (ws1, ws2):
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = 16

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname = f"活动存档_{year or '全部'}{('_'+str(month)) if month else ''}.xlsx"
    return send_file(
        buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True, download_name=fname
    )
