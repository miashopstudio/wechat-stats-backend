# 微信商城小程序 · 独立数据统计后台

独立于微信小程序的 Web 后台，拉取小程序订单、围绕「活动商品」做成本 / 利润 / 销量分析。
纯前端（原生 HTML/CSS/JS）+ Flask 后端，极简商务风，无图标库（全部纯文字按钮）。

---

## 一、目录结构

```
wechat-stats-backend/
├── backend/                 # Flask 后端
│   ├── app.py               # 入口，托管前端静态文件
│   ├── config.py            # 全部配置（环境变量驱动）
│   ├── db.py / models.py    # 数据库与 5 张业务表模型
│   ├── schema.sql           # MySQL 建表脚本
│   ├── .env.example         # 环境变量示例（复制为 .env 填真实值）
│   ├── requirements.txt
│   ├── routes/              # 各 API 蓝图（auth/products/campaigns/sync/dashboard/stats/archive）
│   ├── services/            # wechat_pay.py（v3 账单拉取）、sync_service.py（解析匹配）
│   └── smoke_test.py        # 本地冒烟测试
├── frontend/                # 前端（原生 JS）
│   ├── index.html
│   ├── css/style.css
│   └── js/{api.js, app.js}  # 含 hash 路由与各页面
└── docker-compose.yml       # 一键起本地/云 MySQL
```

---

## 二、你需要提供的资料（部署前准备）

1. **数据库（云端 MySQL，多端实时同步）**
   - 一台 MySQL 8（可用云厂商 RDS、或 Docker 起在服务器上）。
   - 建库后执行 `backend/schema.sql`。
   - 给我：主机地址、端口、用户名、密码、库名 → 写入 `.env` 的 `MYSQL_*`。

2. **微信支付 API v3 凭证**（用于自动拉取订单，直接对接）
   - `WX_APPID`（小程序 AppID）、`WX_APPSECRET`
   - `WX_MCHID`（微信支付商户号）
   - `WX_API_V3_KEY`（APIv3 密钥，用于解密资金账单）
   - `WX_MERCHANT_SERIAL`（商户 API 证书序列号）
   - `WX_PRIVATE_KEY_PATH`（商户平台下载的 `apiclient_key.pem` 绝对路径）
   - 没有凭证也不影响使用：可用「CSV 导入」兜底（上传微信官方导出的交易报表）。

3. **管理员账号**
   - `ADMIN_USERNAME` / `ADMIN_PASSWORD`（默认 admin/admin123，请务必改掉）。

> 没有上述任何一项都不影响先把系统跑起来：不填 `MYSQL_*` 时自动用本地 SQLite 兜底；不填微信凭证时走 CSV 导入。

---

## 三、本地运行（验证用）

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # 可按需填写，留空则 SQLite 兜底
python app.py               # 默认 http://127.0.0.1:5000
```

打开浏览器访问 `http://127.0.0.1:5000`，用 admin/admin123 登录。
冒烟测试：`python smoke_test.py`（覆盖登录、商品、活动、CSV 同步、看板、统计、导出）。

---

## 四、部署到公网 / 云（多端实时同步）

### 方案 A：腾讯云 CloudBase 云托管（推荐，给公网网址、可免自定义域名费）

> 云托管 = 把本项目的 Flask 容器跑在腾讯云，自动给一个免费子域名（如 `xxx.ap-shanghai.run.tcloudbase.com`）。
> 小程序**商品本身存在「云开发」数据库**里，由云函数读取后推给这里的统计后台（见第六节）。

**步骤（控制台点几下即可，无需本地 Docker）：**

1. 打开 [CloudBase 控制台](https://console.cloud.tencent.com/tcb) → 进入你的环境 → **云托管** → 新建服务（服务名称随便，如 `stats-backend`）。
2. 新建**版本**：
   - 来源选「代码仓库 / 本地代码」→ 上传本项目根目录（含 `Dockerfile`、 `backend/`、`frontend/`）。
   - 构建：平台读根目录 `Dockerfile` 自动构建镜像。
   - 监听端口填 `80`（镜像内 `PORT` 默认 80，平台会注入 `PORT` 环境变量覆盖）。
3. 版本「环境变量」里填入（**不要写进代码**）：
   - `ADMIN_PASSWORD`（改复杂密码）、`ADMIN_USERNAME`
   - `MYSQL_HOST` / `MYSQL_USER` / `MYSQL_PASSWORD` / `MYSQL_DB`（建议用云数据库 MySQL；不填则容器内 SQLite，重启可能丢数据）
   - `GOODS_SYNC_TOKEN`（与云函数里 `STATS_SYNC_TOKEN` 一致，默认 `cloud_sync_2026`）
   - 微信凭证：`WX_APPID` / `WX_MCHID` / `WX_API_V3_KEY` / `WX_MERCHANT_SERIAL`
   - 私钥：用 `WX_PRIVATE_KEY_B64`（把 `apiclient_key.pem` 整个文件 base64 后粘进来），平台启动会自动解码写文件；或把 pem 随代码上传（注意镜像不外传）。
4. 部署完成后，平台给的「默认域名」即可在手机/电脑直接打开；如需 `你的店名.com`，在「自定义域名」绑定（域名需自备 + ICP 备案，绑定不收费）。

**本地用 Docker 自测镜像（可选）：**
```bash
docker build -t stats-backend .
docker run -p 5000:80 -e ADMIN_PASSWORD=xxx stats-backend
# 浏览器开 http://127.0.0.1:5000
```

### 方案 B：自有服务器 + gunicorn

1. 在服务器上起 MySQL（或 `docker compose up -d`），执行 `schema.sql`。
2. 把 `.env` 的 `MYSQL_*` 指向云数据库，填入微信凭证与管理员密码。
3. 用 gunicorn 运行后端（同源托管前端，免 CORS）：
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```
4. 前端已随 Flask 一起提供，无需单独部署；如需独立部署前端，开启 CORS 并把 `api.js` 的 `API` 改为后端域名。

---

## 六、小程序商品自动同步（云开发 → 统计后台）

小程序商品存在 **CloudBase 云开发** 的云数据库。由云函数 `cloudbase/sync_goods/index.js` 读取后，POST 到统计后台 `/api/sync/goods`：

1. 微信开发者工具 → 你的环境 → 新建云函数 `sync_goods`，把 `cloudbase/sync_goods/` 下 `index.js` + `package.json` 放进去。
2. 改 `index.js` 顶部 `CONFIG`：`ENV_ID`（云环境）、商品集合名、`STATS_API_URL`（= 上面云托管的默认域名 + `/api/sync/goods`）、`STATS_SYNC_TOKEN`（与后台 `GOODS_SYNC_TOKEN` 一致）。
3. 部署云函数。在云开发控制台「测试」跑一次，返回 `upserted: N` 即成功，统计后台「商品管理」即出现带大/小分类的全部商品。
4. 想"改动即同步"：在你小程序"新增/修改商品"的云函数末尾加一行 `await cloud.callFunction({ name: 'sync_goods' })`；或在 `config.json` 配每分钟/每小时定时触发兜底。

---

## 五、使用流程

1. **商品管理**：先录入商品（名称、SKU、默认成本价）。改成本价会自动留痕（成本日志）。
2. **活动管理**：新建活动（名称、起止时间）→「添加商品」勾选并逐条设活动售价 / 该期成本 / 是否捆绑 / 捆绑数量。活动结束后自动标记「已结束」（存档，数据永久保留，仅可隐藏）。
3. **数据同步**：
   - 自动对接：在「同步」处点「拉取」并选日期，调微信支付 v3 账单接口入库；
   - 兜底：上传微信导出的交易报表 CSV（字段按「微信订单号 / 交易时间 / 总金额 / 商品名称 / 交易状态」识别）。
   - 系统按「商品名称 + 下单时间命中活动窗口」匹配到活动商品并累计销量。
4. **数据看板**：今日 / 本月 / 上月收入、成本、利润，进行中活动数与总销量。
5. **活动详情**：每商品销量、捆绑销量、收入/成本/利润/利润率，以及每日趋势折线图（ECharts）。已下架活动顶部显示累计总销量与总利润。
6. **历史存档**：按年/月筛选已结束活动盈亏，一键导出 Excel。

---

## 六、API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/auth/login | 登录 |
| GET | /api/products | 商品列表（?q=搜索） |
| POST | /api/products | 新增/修改商品（含成本日志） |
| GET | /api/campaigns | 活动列表 |
| POST | /api/campaigns | 新建/更新活动 |
| POST | /api/campaigns/{id}/items | 向活动批量添加商品 |
| POST | /api/sync/orders | 按日期从微信拉取账单 |
| POST | /api/sync/orders/import | 上传 CSV 导入（兜底） |
| POST | /api/sync/goods | 接收小程序云开发推送的商品+分类（X-Sync-Token 校验） |
| GET | /api/dashboard/summary | 看板数据 |
| GET | /api/campaigns/{id}/stats | 单活动利润报表 + 趋势 |
| GET | /api/archive | 已结束活动列表（?year=&month=） |
| GET | /api/archive/export | 导出 Excel |

---

## 七、已知约定与边界

- **捆绑销量**：微信交易账单每行通常视作 1 单位；捆绑商品按「组」折算（组数 = 数量 // 捆绑数，不足一组计 1 组）。若你的订单数据能给出精确「件数」，调整 `services/sync_service.py` 的 `units_of` 即可。
- **订单匹配**：按「商品名称」关联，建议小程序下单时把商品 id 编码进「商户订单号」以便精准匹配（当前为名称 best-effort）。
- **成本口径**：利润 = 收入 − 该期成本 × 销量；非活动商品订单不计入统计。
