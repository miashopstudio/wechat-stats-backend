// ============================================================
// 活动商品数据统计后台 · 前端（原生 JS，hash 路由，无图标库）
// ============================================================
let state = { loggedIn: false, user: null };

const CONTENT = () => document.getElementById("content");

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}
function fmt(n) {
  return Number(n || 0).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function money(n) {
  return "¥" + fmt(n);
}
function dtLocal(d) {
  // ISO -> datetime-local 输入框值
  if (!d) return "";
  const dt = new Date(d);
  const p = (x) => String(x).padStart(2, "0");
  return `${dt.getFullYear()}-${p(dt.getMonth() + 1)}-${p(dt.getDate())}T${p(dt.getHours())}:${p(dt.getMinutes())}`;
}

// ---------------- 弹窗 ----------------
function openModal(title, bodyHtml, actionsHtml) {
  const mask = document.createElement("div");
  mask.className = "modal-mask";
  mask.innerHTML = `<div class="modal">
    <h3>${esc(title)}</h3>
    <div class="modal-body">${bodyHtml}</div>
    <div class="modal-actions">${actionsHtml}</div>
  </div>`;
  document.body.appendChild(mask);
  mask.addEventListener("click", (e) => {
    if (e.target === mask) closeModal(mask);
  });
  return mask;
}
function closeModal(mask) {
  mask.remove();
}

// ---------------- 登录 ----------------
async function showLogin() {
  document.getElementById("app").innerHTML = `
  <div class="login-wrap">
    <div class="login-card">
      <h2>活动商品数据统计后台</h2>
      <label>账号</label>
      <input id="username" autocomplete="username" placeholder="请输入账号" />
      <label>密码</label>
      <input id="password" type="password" autocomplete="current-password" placeholder="请输入密码" />
      <div class="login-error" id="loginError"></div>
      <div class="modal-actions" style="margin-top:16px">
        <button class="primary" id="loginBtn" style="width:100%">登录</button>
      </div>
    </div>
  </div>`;
  const doLogin = async () => {
    const u = document.getElementById("username").value.trim();
    const p = document.getElementById("password").value;
    document.getElementById("loginError").textContent = "";
    try {
      await api.login(u, p);
      state.loggedIn = true;
      route();
    } catch (e) {
      document.getElementById("loginError").textContent = e.message;
    }
  };
  document.getElementById("loginBtn").onclick = doLogin;
  document.getElementById("password").addEventListener("keydown", (e) => {
    if (e.key === "Enter") doLogin();
  });
}

// ---------------- 外壳 ----------------
function shell(active) {
  const nav = [
    ["#/dashboard", "数据看板"],
    ["#/products", "商品管理"],
    ["#/campaigns", "活动管理"],
    ["#/archive", "历史存档"],
  ];
  return `<div class="layout">
    <div class="sidebar">
      <div class="brand">统计后台</div>
      <nav>
        ${nav
          .map(
            ([h, t]) =>
              `<a href="${h}" class="${h === "#/" + active ? "active" : ""}">${t}</a>`
          )
          .join("")}
      </nav>
      <div class="spacer"></div>
      <div class="foot">${esc(state.user || "")} · <a class="link" id="logoutBtn">退出</a></div>
    </div>
    <div class="content" id="content"></div>
  </div>`;
}

// ---------------- 数据看板 ----------------
async function dashboardView() {
  CONTENT().innerHTML = `<h1>数据看板</h1><div class="sub">实时汇总活动商品经营概况</div><div class="empty">加载中…</div>`;
  const s = await api.get("/dashboard/summary");
  const card = (label, v, cls) =>
    `<div class="card metric"><div class="label">${label}</div><div class="value ${cls || ""}">${v}</div></div>`;
  const periodBlock = (title, d) => `
    <div style="margin-bottom:8px;font-weight:600">${title}</div>
    <div class="cards-row">
      ${card("收入", money(d.income))}
      ${card("成本", money(d.cost))}
      ${card("利润", money(d.profit), d.profit >= 0 ? "profit" : "loss")}
      ${card("订单数", d.order_count)}
    </div>`;
  CONTENT().innerHTML = `
    <h1>数据看板</h1>
    <div class="sub">生成时间：${esc(s.generated_at)}</div>
    <div class="card">
      ${periodBlock("今日", s.today)}
      <div style="height:12px"></div>
      ${periodBlock("本月", s.month)}
      <div style="height:12px"></div>
      ${periodBlock("上月", s.last_month)}
    </div>
    <div class="cards-row">
      ${card("进行中活动数", s.active_campaigns)}
      ${card("进行中总销量", s.active_total_sold)}
    </div>
    <div class="card"><div id="dashChart" class="chart"></div></div>`;
  const chart = echarts.init(document.getElementById("dashChart"));
  chart.setOption({
    title: { text: "收入 / 成本 / 利润（近三周期）", left: "center", textStyle: { fontSize: 14 } },
    tooltip: { trigger: "axis" },
    legend: { bottom: 0, data: ["收入", "成本", "利润"] },
    xAxis: { type: "category", data: ["今日", "本月", "上月"] },
    yAxis: { type: "value" },
    series: [
      { name: "收入", type: "bar", data: [s.today.income, s.month.income, s.last_month.income] },
      { name: "成本", type: "bar", data: [s.today.cost, s.month.cost, s.last_month.cost] },
      { name: "利润", type: "bar", data: [s.today.profit, s.month.profit, s.last_month.profit] },
    ],
  });
}

// ---------------- 商品管理 ----------------
async function productsView() {
  CONTENT().innerHTML = `<h1>商品管理</h1><div class="sub">维护商品基础信息与成本价（成本修改自动留痕）。分类由小程序云开发同步带过来。</div><div class="empty">加载中…</div>`;
  let list = await api.get("/products");
  const render = (items) => {
    const rows = items
      .map(
        (p) => `<tr>
        <td>${esc(p.name)}</td>
        <td>${esc(p.sku)}</td>
        <td>${esc(p.category_l1 || "—")}</td>
        <td>${esc(p.category_l2 || "—")}</td>
        <td>${esc(p.category_l3 || "—")}</td>
        <td>${money(p.default_cost_price)}</td>
        <td class="row-actions">
          <button class="link" data-edit="${p.id}">编辑</button>
          <button class="link" data-log="${p.id}">成本日志</button>
          <button class="link danger" data-del="${p.id}">删除</button>
        </td>
      </tr>`
      )
      .join("");
    CONTENT().innerHTML = `
      <h1>商品管理</h1>
      <div class="sub">维护商品基础信息与成本价</div>
      <div class="btn-row">
        <input id="search" placeholder="搜索名称 / SKU / 分类" style="width:240px" />
        <button class="primary" id="addBtn">新增商品</button>
      </div>
      <div class="tbl-wrap"><table>
        <thead><tr><th>名称</th><th>SKU</th><th>大分类</th><th>中分类</th><th>小分类</th><th>默认成本价</th><th>操作</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="7" class="empty">暂无商品</td></tr>'}</tbody>
      </table></div>`;
    document.getElementById("addBtn").onclick = () => productForm(null);
    document.getElementById("search").oninput = async (e) => {
      const q = e.target.value.trim();
      const r = await api.get("/products" + (q ? "?q=" + encodeURIComponent(q) : ""));
      render(r);
    };
    CONTENT().querySelectorAll("[data-edit]").forEach((b) =>
      (b.onclick = () => productForm(items.find((x) => x.id == b.dataset.edit)))
    );
    CONTENT().querySelectorAll("[data-log]").forEach((b) =>
      (b.onclick = () => costLog(b.dataset.log))
    );
    CONTENT().querySelectorAll("[data-del]").forEach((b) =>
      (b.onclick = async () => {
        if (!confirm("确认删除该商品？关联的活动商品记录将一并删除。")) return;
        await api.del("/products/" + b.dataset.del);
        productsView();
      })
    );
  };
  render(list);
}

function productForm(p) {
  const isEdit = !!p;
  const mask = openModal(
    isEdit ? "编辑商品" : "新增商品",
    `<div class="form-grid">
      <div class="field"><label>商品名称</label><input id="f_name" value="${esc(p?.name || "")}"/></div>
      <div class="field"><label>SKU 编号</label><input id="f_sku" value="${esc(p?.sku || "")}" ${isEdit ? "readonly" : ""}/></div>
      <div class="field"><label>默认成本价</label><input id="f_cost" type="number" step="0.01" value="${esc(p?.default_cost_price || 0)}"/></div>
      <div class="field"><label>大分类</label><input id="f_cat1" value="${esc(p?.category_l1 || "")}" placeholder="如：食品"/></div>
      <div class="field"><label>中分类</label><input id="f_cat2" value="${esc(p?.category_l2 || "")}" placeholder="如：零食"/></div>
      <div class="field"><label>小分类</label><input id="f_cat3" value="${esc(p?.category_l3 || "")}" placeholder="如：坚果"/></div>
    </div>`,
    `<button id="cancel">取消</button><button class="primary" id="save">保存</button>`
  );
  mask.querySelector("#cancel").onclick = () => closeModal(mask);
  mask.querySelector("#save").onclick = async () => {
    const body = {
      name: mask.querySelector("#f_name").value.trim(),
      sku: mask.querySelector("#f_sku").value.trim(),
      default_cost_price: parseFloat(mask.querySelector("#f_cost").value || 0),
      category_l1: mask.querySelector("#f_cat1").value.trim(),
      category_l2: mask.querySelector("#f_cat2").value.trim(),
      category_l3: mask.querySelector("#f_cat3").value.trim(),
    };
    if (!body.name || !body.sku) return alert("名称和 SKU 必填");
    if (isEdit) body.id = p.id;
    try {
      await api.post("/products", body);
      closeModal(mask);
      productsView();
    } catch (e) {
      alert(e.message);
    }
  };
}

async function costLog(pid) {
  const logs = await api.get("/products/" + pid + "/cost-logs");
  const rows = logs
    .map(
      (l) => `<tr><td>${esc(l.change_time)}</td><td>${money(l.old_cost)}</td><td>${money(l.new_cost)}</td><td>${esc(l.operator)}</td></tr>`
    )
    .join("");
  openModal(
    "成本修改日志",
    `<div class="tbl-wrap"><table>
      <thead><tr><th>时间</th><th>旧成本</th><th>新成本</th><th>操作人</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="4" class="empty">暂无修改记录</td></tr>'}</tbody>
    </table></div>`,
    `<button class="primary" id="ok">关闭</button>`
  ).querySelector("#ok").onclick = (e) => closeModal(e.target.closest(".modal-mask"));
}

// ---------------- 活动管理 ----------------
async function campaignsView() {
  CONTENT().innerHTML = `<h1>活动管理</h1><div class="sub">创建活动并向活动添加商品（结束后自动存档）</div><div class="empty">加载中…</div>`;
  const list = await api.get("/campaigns");
  const tag = (st) =>
    st == 1
      ? '<span class="tag active">进行中</span>'
      : st == 0
      ? '<span class="tag ended">已结束</span>'
      : '<span class="tag hidden">已隐藏</span>';
  const rows = list
    .map(
      (c) => `<tr>
      <td><a class="link" href="#/campaign/${c.id}">${esc(c.name)}</a></td>
      <td>${esc(c.start_date)}</td>
      <td>${esc(c.end_date)}</td>
      <td>${tag(c.status)}</td>
      <td class="row-actions">
        <a class="link" href="#/campaign/${c.id}">查看详情</a>
        <button class="link" data-add="${c.id}">添加商品</button>
        ${c.status == 1 ? `<button class="link danger" data-hide="${c.id}">隐藏</button>` : ""}
      </td>
    </tr>`
    )
    .join("");
  CONTENT().innerHTML = `
    <h1>活动管理</h1>
    <div class="sub">创建活动并向活动添加商品（结束后自动存档）</div>
    <div class="btn-row"><button class="primary" id="newBtn">新建活动</button></div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>活动名称</th><th>开始</th><th>结束</th><th>状态</th><th>操作</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="5" class="empty">暂无活动</td></tr>'}</tbody>
    </table></div>`;
  document.getElementById("newBtn").onclick = () => campaignForm(null);
  CONTENT().querySelectorAll("[data-add]").forEach((b) =>
    (b.onclick = () => addItems(b.dataset.add))
  );
  CONTENT().querySelectorAll("[data-hide]").forEach((b) =>
    (b.onclick = async () => {
      if (!confirm("确认隐藏该活动？（数据永久保留，仅列表不显示）")) return;
      await api.post("/campaigns/" + b.dataset.hide + "/hide");
      campaignsView();
    })
  );
}

function campaignForm(c) {
  const isEdit = !!c;
  const mask = openModal(
    isEdit ? "编辑活动" : "新建活动",
    `<div class="form-grid">
      <div class="field"><label>活动名称</label><input id="f_name" value="${esc(c?.name || "")}"/></div>
      <div class="field"><label>开始时间</label><input id="f_start" type="datetime-local" value="${dtLocal(c?.start_date)}"/></div>
      <div class="field"><label>结束时间</label><input id="f_end" type="datetime-local" value="${dtLocal(c?.end_date)}"/></div>
    </div>`,
    `<button id="cancel">取消</button><button class="primary" id="save">保存</button>`
  );
  mask.querySelector("#cancel").onclick = () => closeModal(mask);
  mask.querySelector("#save").onclick = async () => {
    const body = {
      name: mask.querySelector("#f_name").value.trim(),
      start_date: mask.querySelector("#f_start").value,
      end_date: mask.querySelector("#f_end").value,
    };
    if (!body.name || !body.start_date || !body.end_date) return alert("请填写完整");
    if (isEdit) body.id = c.id;
    try {
      await api.post("/campaigns", body);
      closeModal(mask);
      campaignsView();
    } catch (e) {
      alert(e.message);
    }
  };
}

async function addItems(cid) {
  const products = await api.get("/products");
  const existing = await api.get("/campaigns/" + cid);
  const existIds = new Set((existing.items || []).map((i) => i.product_id));
  const rows = products
    .map((p) => {
      const it = (existing.items || []).find((x) => x.product_id == p.id);
      return `<tr>
      <td class="checkbox-cell"><input type="checkbox" data-pid="${p.id}" ${existIds.has(p.id) ? "checked" : ""}/></td>
      <td>${esc(p.name)} <span class="muted">(${esc(p.sku)})</span></td>
      <td class="inline-edit"><input type="number" step="0.01" data-price="${p.id}" placeholder="活动售价" value="${it ? it.activity_price : ""}"/></td>
      <td class="inline-edit"><input type="number" step="0.01" data-cost="${p.id}" placeholder="该期成本" value="${it ? it.cost_price : p.default_cost_price}"/></td>
      <td class="checkbox-cell"><input type="checkbox" data-bundle="${p.id}" ${it && it.is_bundle ? "checked" : ""}/> 捆绑</td>
      <td class="inline-edit"><input type="number" data-qty="${p.id}" value="${it ? it.bundle_quantity : 1}" style="width:60px"/></td>
    </tr>`;
    })
    .join("");
  const mask = openModal(
    "向活动添加商品",
    `<div class="tbl-wrap" style="max-height:60vh;overflow:auto"><table>
      <thead><tr><th>选</th><th>商品</th><th>活动售价</th><th>该期成本</th><th>捆绑</th><th>捆绑数量</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="6" class="empty">请先到商品管理添加商品</td></tr>'}</tbody>
    </table></div>`,
    `<button id="cancel">取消</button><button class="primary" id="save">保存</button>`
  );
  mask.querySelector("#cancel").onclick = () => closeModal(mask);
  mask.querySelector("#save").onclick = async () => {
    const items = [];
    mask.querySelectorAll("input[data-pid]").forEach((cb) => {
      if (!cb.checked) return;
      const pid = cb.dataset.pid;
      const price = mask.querySelector(`[data-price="${pid}"]`).value;
      const cost = mask.querySelector(`[data-cost="${pid}"]`).value;
      const bundle = mask.querySelector(`[data-bundle="${pid}"]`).checked;
      const qty = mask.querySelector(`[data-qty="${pid}"]`).value;
      items.push({
        product_id: parseInt(pid),
        activity_price: parseFloat(price || 0),
        cost_price: parseFloat(cost || 0),
        is_bundle: bundle,
        bundle_quantity: parseInt(qty || 1),
      });
    });
    try {
      await api.post("/campaigns/" + cid + "/items", { items });
      closeModal(mask);
      campaignsView();
    } catch (e) {
      alert(e.message);
    }
  };
}

// ---------------- 活动详情 ----------------
async function campaignDetailView(id) {
  CONTENT().innerHTML = `<h1>活动详情</h1><div class="empty">加载中…</div>`;
  const d = await api.get("/campaigns/" + id + "/stats");
  const c = d.campaign;
  const rows = d.items
    .map(
      (it) => `<tr>
      <td>${esc(it.product ? it.product.name : "")}</td>
      <td>${it.is_bundle ? "是(" + it.bundle_quantity + "件/组)" : "否"}</td>
      <td>${money(it.activity_price)}</td>
      <td>${money(it.cost_price)}</td>
      <td>${it.units}</td>
      <td>${it.bundle_sold}</td>
      <td>${money(it.income)}</td>
      <td>${money(it.cost)}</td>
      <td>${money(it.profit)}</td>
      <td>${it.profit_rate}%</td>
    </tr>`
    )
    .join("");
  const banner = d.archived
    ? `<div class="banner warn">该活动已下架，累计总销量：${d.archived_summary.total_sold}，总利润：${money(d.archived_summary.total_profit)}</div>`
    : `<div class="banner info">活动进行中</div>`;
  CONTENT().innerHTML = `
    <h1>${esc(c.name)}</h1>
    <div class="sub">${esc(c.start_date)} ~ ${esc(c.end_date)}</div>
    ${banner}
    <div class="cards-row" style="margin-bottom:20px">
      <div class="card metric"><div class="label">总收入</div><div class="value">${money(d.total.income)}</div></div>
      <div class="card metric"><div class="label">总成本</div><div class="value">${money(d.total.cost)}</div></div>
      <div class="card metric"><div class="label">总利润</div><div class="value ${d.total.profit >= 0 ? "profit" : "loss"}">${money(d.total.profit)}</div></div>
      <div class="card metric"><div class="label">利润率</div><div class="value">${d.total.profit_rate}%</div></div>
    </div>
    <div class="card">
      <h3 style="margin-top:0">商品明细</h3>
      <div class="tbl-wrap"><table>
        <thead><tr><th>商品</th><th>捆绑</th><th>售价</th><th>成本</th><th>销量</th><th>捆绑销量</th><th>收入</th><th>成本</th><th>利润</th><th>利润率</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="10" class="empty">未添加商品或无订单</td></tr>'}</tbody>
      </table></div>
    </div>
    <div class="card"><div id="trendChart" class="chart"></div></div>`;
  const chart = echarts.init(document.getElementById("trendChart"));
  chart.setOption({
    title: { text: "每日销售额 / 销量趋势", left: "center", textStyle: { fontSize: 14 } },
    tooltip: { trigger: "axis" },
    legend: { bottom: 0, data: ["销售额", "销量"] },
    xAxis: { type: "category", data: d.trend.map((t) => t.date) },
    yAxis: [
      { type: "value", name: "销售额" },
      { type: "value", name: "销量" },
    ],
    series: [
      { name: "销售额", type: "line", smooth: true, data: d.trend.map((t) => t.income) },
      { name: "销量", type: "line", smooth: true, yAxisIndex: 1, data: d.trend.map((t) => t.qty) },
    ],
  });
}

// ---------------- 历史存档 ----------------
async function archiveView() {
  CONTENT().innerHTML = `<h1>历史存档</h1><div class="sub">已结束活动的盈亏概况，支持按年/月筛选与 Excel 导出</div><div class="empty">加载中…</div>`;
  const year = new Date().getFullYear();
  const render = async (y, m) => {
    const q = [];
    if (y) q.push("year=" + y);
    if (m) q.push("month=" + m);
    const list = await api.get("/archive" + (q.length ? "?" + q.join("&") : ""));
    const rows = list
      .map(
        (c) => `<tr>
        <td><a class="link" href="#/campaign/${c.id}">${esc(c.name)}</a></td>
        <td>${esc(c.start_date)}</td>
        <td>${esc(c.end_date)}</td>
        <td>${c.units}</td>
        <td>${money(c.income)}</td>
        <td>${money(c.cost)}</td>
        <td>${money(c.profit)}</td>
        <td>${c.profit_rate}%</td>
      </tr>`
      )
      .join("");
    CONTENT().innerHTML = `
      <h1>历史存档</h1>
      <div class="sub">已结束活动的盈亏概况</div>
      <div class="btn-row">
        <select id="fYear" style="width:120px">
          ${Array.from({ length: 5 }, (_, i) => year - i)
            .map((yy) => `<option value="${yy}" ${yy == y ? "selected" : ""}>${yy}年</option>`)
            .join("")}
        </select>
        <select id="fMonth" style="width:120px">
          <option value="">全部月份</option>
          ${Array.from({ length: 12 }, (_, i) => i + 1)
            .map((mm) => `<option value="${mm}" ${mm == m ? "selected" : ""}>${mm}月</option>`)
            .join("")}
        </select>
        <button id="filter">筛选</button>
        <a class="btn right" id="export">导出 Excel</a>
      </div>
      <div class="tbl-wrap"><table>
        <thead><tr><th>活动</th><th>开始</th><th>结束</th><th>总销量</th><th>收入</th><th>成本</th><th>利润</th><th>利润率</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="8" class="empty">暂无已结束活动</td></tr>'}</tbody>
      </table></div>`;
    document.getElementById("filter").onclick = () => {
      const yy = document.getElementById("fYear").value;
      const mm = document.getElementById("fMonth").value;
      render(yy || null, mm || null);
    };
    document.getElementById("export").onclick = () => {
      const yy = document.getElementById("fYear").value;
      const mm = document.getElementById("fMonth").value;
      const q2 = [];
      if (yy) q2.push("year=" + yy);
      if (mm) q2.push("month=" + mm);
      window.location.href = "/api/archive/export" + (q2.length ? "?" + q2.join("&") : "");
    };
  };
  render(year, null);
}

// ---------------- 路由 ----------------
async function route() {
  if (!state.loggedIn) {
    await showLogin();
    return;
  }
  const hash = location.hash || "#/dashboard";
  const parts = hash.replace("#/", "").split("/");
  document.getElementById("app").innerHTML = shell(parts[0] || "dashboard");
  document.getElementById("logoutBtn").onclick = async () => {
    await api.logout();
    state.loggedIn = false;
    showLogin();
  };
  try {
    if (parts[0] === "dashboard") await dashboardView();
    else if (parts[0] === "products") await productsView();
    else if (parts[0] === "campaigns") await campaignsView();
    else if (parts[0] === "campaign") await campaignDetailView(parts[1]);
    else if (parts[0] === "archive") await archiveView();
    else await dashboardView();
  } catch (e) {
    CONTENT().innerHTML = `<div class="banner warn">加载失败：${esc(e.message)}</div>`;
  }
}

window.addEventListener("hashchange", route);

(async function init() {
  try {
    const me = await api.me();
    if (me.logged_in) {
      state.loggedIn = true;
      state.user = me.username;
    }
  } catch (e) {}
  await route();
})();
