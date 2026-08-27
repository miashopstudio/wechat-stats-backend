// 极简 API 封装：同源 + session cookie，无需手动带 token
const API = "/api";

async function request(path, opts = {}) {
  opts.credentials = "same-origin";
  opts.headers = Object.assign({}, opts.headers || {});
  if (opts.body && !(opts.body instanceof FormData)) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.body);
  }
  const res = await fetch(API + path, opts);
  if (res.status === 401) {
    location.hash = "#/login";
    throw new Error("未登录或登录已失效");
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    const j = await res.json();
    if (!res.ok) throw new Error(j.error || "请求失败");
    return j;
  }
  // 非 JSON（HTML/空）：大概率是后端没起 / /api 在静态预览被拦了
  // 文件下载场景由调用方显式用 rawFetch
  if (!res.ok) {
    throw new Error(
      `后端未运行或地址不可达（${res.status} ${res.statusText}）。` +
      `如果你是从静态预览打开的，请先本地启动 Flask：cd backend && python app.py，然后访问 http://127.0.0.1:5000`
    );
  }
  throw new Error("后端返回的不是 JSON（可能后端未运行 / 当前是静态预览）");
}

async function rawFetch(path, opts = {}) {
  opts.credentials = "same-origin";
  return fetch(API + path, opts);
}

const api = {
  get: (p) => request(p, { method: "GET" }),
  post: (p, b) => request(p, { method: "POST", body: b || {} }),
  del: (p) => request(p, { method: "DELETE" }),
  upload: (p, formData) => request(p, { method: "POST", body: formData }),
  rawFetch, // 文件下载等需要直接拿到 Response 的场景
  login: (username, password) =>
    request("/auth/login", { method: "POST", body: { username, password } }),
  logout: () => request("/auth/logout", { method: "POST" }),
  me: () => request("/auth/me", { method: "GET" }),
};
