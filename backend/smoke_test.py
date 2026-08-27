"""本地冒烟测试：用 SQLite 跑通核心流程（不依赖 MySQL / 微信凭证）。"""
import io
from app import app
from db import db
from models import Product, Campaign, CampaignItem, OrderSync

CSV = """交易时间,微信订单号,总金额,商品名称,交易状态
2026-08-20 10:00:00,WX0001,30.00,测试冰淇淋,支付成功
2026-08-20 11:00:00,WX0002,30.00,测试冰淇淋,支付成功
2026-08-21 09:00:00,WX0003,15.00,测试面包,支付成功
"""

with app.app_context():
    db.create_all()
    # 清空便于重复测试
    OrderSync.query.delete(); CampaignItem.query.delete()
    Campaign.query.delete(); Product.query.delete(); db.session.commit()

c = app.test_client()

def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + ("  " + extra if extra else ""))
    assert cond, name

# 1) 登录
r = c.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
check("login", r.status_code == 200, str(r.get_json()))

# 2) 未登录保护（新 client 无 cookie）
r2 = app.test_client().get("/api/products")
check("auth_guard", r2.status_code == 401)

# 3) 商品 CRUD
r = c.post("/api/products", json={"name": "测试冰淇淋", "sku": "ICE-001", "default_cost_price": 10})
check("create_product", r.status_code == 200)
pid = r.get_json()["id"]
r = c.post("/api/products", json={"name": "测试面包", "sku": "BRD-001", "default_cost_price": 5})
pid2 = r.get_json()["id"]

# 4) 成本修改日志
c.post("/api/products", json={"id": pid, "name": "测试冰淇淋", "sku": "ICE-001", "default_cost_price": 12})
r = c.get(f"/api/products/{pid}/cost-logs")
check("cost_log", r.get_json() and r.get_json()[0]["new_cost"] == 12, str(r.get_json()))

# 5) 活动 + 添加商品
r = c.post("/api/campaigns", json={"name": "8月冰爽季", "start_date": "2026-08-01 00:00", "end_date": "2026-09-30 23:59"})
check("create_campaign", r.status_code == 200)
cid = r.get_json()["id"]
r = c.post(f"/api/campaigns/{cid}/items", json={"items": [
    {"product_id": pid, "activity_price": 15, "cost_price": 12, "is_bundle": True, "bundle_quantity": 2},
    {"product_id": pid2, "activity_price": 15, "cost_price": 5, "is_bundle": False},
]})
check("add_items", r.status_code == 200, str(r.get_json()))

# 6) 订单同步（CSV 兜底解析 + 匹配）
r = c.post("/api/sync/orders/import", data={"file": (io.BytesIO(CSV.encode("utf-8-sig")), "bill.csv")},
           content_type="multipart/form-data")
check("csv_import", r.status_code == 200 and r.get_json().get("imported") == 3, str(r.get_json()))

# 7) 看板
r = c.get("/api/dashboard/summary")
d = r.get_json()
check("dashboard", d["active_campaigns"] == 1, str(d))

# 8) 活动统计
r = c.get(f"/api/campaigns/{cid}/stats")
s = r.get_json()
check("stats_total", s["total"]["income"] == 75.0, str(s["total"]))  # 30+30+15
# 捆绑(2件/组)：两个冰淇淋订单各算 1 组 -> 2*12；面包 1 件 ->5；成本=29
check("stats_profit", s["total"]["profit"] == (75 - 29), str(s["total"]))
check("trend_len", len(s["trend"]) > 0)

# 9) 存档导出（活动仍进行中，应返回空表文件且不报错）
r = c.get("/api/archive/export")
check("export", r.status_code == 200 and "spreadsheetml" in r.headers.get("Content-Type", ""))

print("\nALL SMOKE TESTS PASSED")
