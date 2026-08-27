# 微信商城数据统计后台 —— CloudBase 云托管镜像
# 构建上下文：仓库根目录（backend/ 与 frontend/ 都在镜像内）
FROM python:3.11-slim

# 系统依赖（cryptography 在 slim 上用预编译 wheel，通常不需要 gcc；保留 gcc/libssl 以防万一）
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖（利用层缓存）
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# 复制代码
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

# 环境变量
ENV FRONTEND_DIR=/app/frontend
ENV PORT=80
# 容器外通过"云托管环境变量"注入 secrets（不要写进镜像）
# 例：MYSQL_HOST / MYSQL_USER / MYSQL_PASSWORD / MYSQL_DB / ADMIN_PASSWORD / GOODS_SYNC_TOKEN / WX_*
ENV FLASK_DEBUG=0

WORKDIR /app/backend
EXPOSE 80

# 云托管会用 PORT 环境变量覆盖监听端口；本地 docker 默认 80
CMD ["python", "app.py"]
