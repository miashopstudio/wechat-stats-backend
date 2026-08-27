"""应用入口：初始化 Flask、注册蓝图、托管前端静态文件。"""
import os
from flask import Flask, send_from_directory, jsonify
from config import Config
from db import db
from models import Product, Campaign  # 确保模型被导入

# 蓝图
from routes import auth, products, campaigns, sync, dashboard, stats, archive, sync_goods


def create_app():
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)

    db.init_app(app)

    # 注册 API
    app.register_blueprint(auth.auth_bp)
    app.register_blueprint(products.products_bp)
    app.register_blueprint(campaigns.campaigns_bp)
    app.register_blueprint(sync.sync_bp)
    app.register_blueprint(dashboard.dashboard_bp)
    app.register_blueprint(stats.stats_bp)
    app.register_blueprint(archive.archive_bp)
    app.register_blueprint(sync_goods.sync_goods_bp)

    frontend_dir = os.path.abspath(Config.FRONTEND_DIR)

    @app.route("/api/health")
    def health():
        return jsonify({"ok": True})

    # 前端静态资源
    @app.route("/", defaults={"path": "index.html"})
    @app.route("/<path:path>")
    def serve_frontend(path):
        full = os.path.join(frontend_dir, path)
        if os.path.isfile(full):
            return send_from_directory(frontend_dir, path)
        # SPA：未知路径回退到 index.html（使用 hash 路由时基本用不到）
        return send_from_directory(frontend_dir, "index.html")

    with app.app_context():
        db.create_all()  # SQLite 兜底时自动建表；MySQL 请用 schema.sql 建表
        _migrate_columns()  # 为已有库补齐分类列（幂等）

    return app


def _migrate_columns():
    """为已存在的 products 表补齐分类列（SQLite / MySQL 通用，幂等）。"""
    from sqlalchemy import inspect, text
    try:
        insp = inspect(db.engine)
        existing = {c["name"] for c in insp.get_columns("products")}
        for col, ddl in [
            ("category_l1", "VARCHAR(128)"),
            ("category_l2", "VARCHAR(128)"),
            ("category_l3", "VARCHAR(128)"),
        ]:
            if col not in existing:
                with db.engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE products ADD COLUMN {col} {ddl}"))
    except Exception as e:  # 表尚不存在等情况，忽略
        app.logger.warning("migrate columns skipped: %s", e)


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=Config.DEBUG)
