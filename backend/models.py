"""数据模型：与需求文档第五节一一对应。"""
from datetime import datetime
from sqlalchemy import (
    Integer, String, Float, Boolean, DateTime, Text, ForeignKey, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db import db


class Product(db.Model):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    default_cost_price: Mapped[float] = mapped_column(Float, default=0.0)
    # 分类层级：来自小程序云开发同步（大分类 / 中分类 / 小分类）
    category_l1: Mapped[str] = mapped_column(String(128), default="")
    category_l2: Mapped[str] = mapped_column(String(128), default="")
    category_l3: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    cost_logs: Mapped[list["CostChangeLog"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "sku": self.sku,
            "default_cost_price": self.default_cost_price,
            "category_l1": self.category_l1 or "",
            "category_l2": self.category_l2 or "",
            "category_l3": self.category_l3 or "",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Campaign(db.Model):
    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # 1=进行中 0=已结束(-1=已隐藏/归档)
    status: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    items: Mapped[list["CampaignItem"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CampaignItem(db.Model):
    __tablename__ = "campaign_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    activity_price: Mapped[float] = mapped_column(Float, default=0.0)   # 该期活动售价
    cost_price: Mapped[float] = mapped_column(Float, default=0.0)       # 该期成本
    is_bundle: Mapped[bool] = mapped_column(Boolean, default=False)     # 是否捆绑特价
    bundle_quantity: Mapped[int] = mapped_column(Integer, default=1)    # 捆绑数量
    total_sold_count: Mapped[int] = mapped_column(Integer, default=0)  # 统计字段

    campaign: Mapped["Campaign"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()

    def to_dict(self, with_product=False):
        d = {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "product_id": self.product_id,
            "activity_price": self.activity_price,
            "cost_price": self.cost_price,
            "is_bundle": self.is_bundle,
            "bundle_quantity": self.bundle_quantity,
            "total_sold_count": self.total_sold_count,
        }
        if with_product and self.product:
            d["product"] = self.product.to_dict()
        return d


class OrderSync(db.Model):
    __tablename__ = "orders_sync"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[str] = mapped_column(String(64), nullable=False)      # 微信订单号
    product_id: Mapped[int] = mapped_column(Integer, nullable=True)        # 匹配到的活动商品 id（可为空）
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    pay_price: Mapped[float] = mapped_column(Float, default=0.0)           # 实付金额
    order_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sync_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    campaign_item_id: Mapped[int] = mapped_column(Integer, nullable=True)  # 关联的活动商品行

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "product_id": self.product_id,
            "quantity": self.quantity,
            "pay_price": self.pay_price,
            "order_time": self.order_time.isoformat() if self.order_time else None,
            "sync_date": self.sync_date.isoformat() if self.sync_date else None,
            "campaign_item_id": self.campaign_item_id,
        }


class CostChangeLog(db.Model):
    __tablename__ = "cost_change_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    old_cost: Mapped[float] = mapped_column(Float, default=0.0)
    new_cost: Mapped[float] = mapped_column(Float, default=0.0)
    operator: Mapped[str] = mapped_column(String(64), default="admin")
    change_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    product: Mapped["Product"] = relationship(back_populates="cost_logs")

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "old_cost": self.old_cost,
            "new_cost": self.new_cost,
            "operator": self.operator,
            "change_time": self.change_time.isoformat() if self.change_time else None,
        }
