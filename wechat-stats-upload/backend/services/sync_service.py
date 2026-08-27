"""
订单解析与匹配：把微信账单/CSV 解析为 orders_sync，并匹配到活动商品，
增量更新 campaign_items.total_sold_count。

匹配策略（best-effort）：
  - 用账单里的「商品名称」匹配 products.name 得到 product_id；
  - 再在订单时间命中的「进行中活动」里找该商品的 campaign_item，写入 campaign_item_id。
若匹配不上，product_id / campaign_item_id 留空，仍保留原始订单（仅做总量汇总）。
"""
import csv
import io
from datetime import datetime
from db import db
from models import OrderSync, Product, CampaignItem, Campaign


# 微信交易账单常见列名 -> 我们的字段
COLUMN_MAP = {
    "微信订单号": "order_id",
    "交易单号": "order_id",
    "商户订单号": "out_trade_no",
    "交易时间": "order_time",
    "付款时间": "order_time",
    "总金额": "pay_price",
    "订单金额": "pay_price",
    "商品名称": "goods_name",
    "商品": "goods_name",
    "交易状态": "trade_state",
    "金额": "pay_price",
}


def units_of(quantity, ci) -> int:
    """
    把订单「件数」折算为统计用的销量单位：
      - 非捆绑：按件计（= quantity）。
      - 捆绑：按「组」计。微信交易账单每行通常 quantity=1（一个订单=一组），
        因此 quantity < bundle_quantity 时计为 1 组，否则 quantity // bundle_quantity。
    """
    q = max(1, int(quantity or 1))
    if ci.is_bundle and ci.bundle_quantity:
        if q < ci.bundle_quantity:
            return 1
        return q // ci.bundle_quantity
    return q


def _parse_dt(s: str):
    s = (s or "").strip().replace("/", "-")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _to_float(s):
    try:
        return float(str(s).replace(",", "").replace("¥", "").strip() or 0)
    except ValueError:
        return 0.0


def _split_line(line: str):
    """微信交易账单：数据行字段以「逗号+反引号」(,`) 分隔、且每个字段前带反引号；
    表头为普通 CSV（可能带 BOM）。统一处理为干净单元格列表。"""
    line = line.replace("\ufeff", "").strip()
    if not line:
        return None
    if line.startswith("`"):
        cells = line.split(",`")
        return [c.strip("`").strip() for c in cells]
    return [c.strip("`").strip() for c in line.split(",")]


def parse_and_import(csv_text: str, source: str = "csv") -> dict:
    raw_lines = [l for l in csv_text.splitlines()]
    rows = [r for r in (_split_line(l) for l in raw_lines) if r]
    if not rows:
        return {"imported": 0, "skipped": 0, "message": "空文件"}

    # 定位表头
    header = [c.strip() for c in rows[0]]
    idx = {}
    for i, h in enumerate(header):
        if h in COLUMN_MAP:
            idx[COLUMN_MAP[h]] = i
    # 模糊匹配列（兼容带「（元）」等后缀）
    def col(name):
        for cand in [name, name + "（元）", name + "(元)"]:
            if cand in idx:
                return idx[cand]
        return None

    oi = col("order_id")
    ti = col("order_time")
    pi = col("pay_price")
    gi = col("goods_name")
    si = col("trade_state")

    imported = 0
    skipped = 0
    # 商品名 -> product 快速查表
    products = Product.query.all()
    name_to_product = {p.name: p for p in products}

    for r in rows[1:]:
        # 跳过汇总行（微信账单结尾的「总交易单数,...」）
        if oi is None or (len(r) > oi and ("总交易" in r[oi] or "交易单数" in r[oi])):
            continue
        if oi is None or oi >= len(r):
            continue
        order_id = r[oi].strip()
        # 微信订单号为纯数字；非数字（汇总尾行/表头残留）直接跳过
        if not order_id or not order_id.isdigit():
            skipped += 1
            continue
        order_time = _parse_dt(r[ti]) if ti is not None and ti < len(r) else None
        if order_time is None:
            skipped += 1
            continue
        pay_price = _to_float(r[pi]) if pi is not None and pi < len(r) else 0.0
        goods_name = r[gi].strip() if gi is not None and gi < len(r) else ""
        state = r[si].strip() if si is not None and si < len(r) else ""

        # 跳过退款 / 已撤销等反向状态行（不计入销量与收入）
        REFUND_STATES = ("REFUND", "退款", "已退款", "REVOKED", "已撤销", "CLOSED", "关闭")
        if state and state in REFUND_STATES:
            skipped += 1
            continue

        # 去重
        if OrderSync.query.filter_by(order_id=order_id).first():
            skipped += 1
            continue

        product = name_to_product.get(goods_name)
        product_id = product.id if product else None
        campaign_item_id = None
        if product:
            # 找命中时间窗口的活动商品
            ci = (
                CampaignItem.query.join(Campaign)
                .filter(
                    CampaignItem.product_id == product.id,
                    Campaign.start_date <= order_time,
                    Campaign.end_date >= order_time,
                )
                .first()
            )
            if ci:
                campaign_item_id = ci.id

        rec = OrderSync(
            order_id=order_id,
            product_id=product_id,
            quantity=1,  # 微信账单按订单行计 1 件；捆绑按组在统计层用 units_of 折算
            pay_price=pay_price,
            order_time=order_time,
            campaign_item_id=campaign_item_id,
        )
        db.session.add(rec)
        imported += 1

    db.session.commit()
    # 重新统计所有活动商品销量
    recompute_all_sold()
    return {"imported": imported, "skipped": skipped, "source": source}


def recompute_all_sold():
    """依据 orders_sync 重新累加每个活动商品的销量。"""
    items = CampaignItem.query.all()
    for ci in items:
        total = 0
        for o in OrderSync.query.filter_by(campaign_item_id=ci.id).all():
            total += units_of(o.quantity, ci)
        ci.total_sold_count = total
    db.session.commit()
