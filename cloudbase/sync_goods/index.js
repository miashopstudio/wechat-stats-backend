// ============================================================
// 微信云开发云函数：sync_goods
// 作用：读取云数据库里的商品（含大/中/小分类），推送到统计后台。
// 触发方式：
//   1) 主动推送 —— 在你「商品管理」的云函数（新增/修改/删除商品后）里加一句
//                  await cloud.callFunction({ name: 'sync_goods' })
//   2) 兜底定时  —— 部署时配上 config.json 的定时触发器，每小时自动同步一次。
// 依赖：wx-server-sdk（在 package.json 里已声明）
// ============================================================

const cloud = require('wx-server-sdk')
const https = require('https')

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })

// ====================== 需要你改的配置 ======================
const CONFIG = {
  // 统计后台的公网地址（本地跑时云函数推不过来，必须部署到公网或内网穿透）
  STATS_API_URL: 'https://替换为你的统计后台地址', // 例如 https://stats.yourdomain.com
  // 必须与统计后台 .env 里的 GOODS_SYNC_TOKEN 完全一致
  STATS_SYNC_TOKEN: 'cloud_sync_2026',

  // 云数据库里商品集合的名字（在云开发控制台里看）
  GOODS_COLLECTION: 'goods',
  // 如果分类单独存在一个集合（商品里只存分类 id），填这里；否则留空，按商品自带分类字段解析
  CATEGORY_COLLECTION: '',

  // 字段映射：按你集合里真实的字段名调整（左边是标准名，右边填你集合的字段）
  FIELD: {
    sku: 'sku',          // 唯一编号；若集合没有 sku 字段，改成 '_id'（用文档 id 当编号）
    name: 'name',        // 商品名称
    cost: 'cost',        // 成本价（没有就填 0）
    categoryL1: 'categoryL1', // 大分类字段名（没有就留空字符串 ''）
    categoryL2: 'categoryL2', // 中分类字段名
    categoryL3: 'categoryL3', // 小分类字段名
  },

  PAGE_SIZE: 100, // 每次读取条数，云数据库单次上限 100
}
// ============================================================

// 从商品文档里取出分类（兼容多种写法：字符串 / 数组 / 单独分类集合）
function resolveCategory(doc) {
  const F = CONFIG.FIELD
  const pick = (key) => {
    const v = doc[key]
    return v == null ? '' : String(v).trim()
  }
  let l1 = F.categoryL1 ? pick(F.categoryL1) : ''
  let l2 = F.categoryL2 ? pick(F.categoryL2) : ''
  let l3 = F.categoryL3 ? pick(F.categoryL3) : ''

  // 兼容：商品里只有一个 category 字段，可能是字符串或数组
  if (!l1 && !l2 && !l3 && doc.category != null) {
    if (Array.isArray(doc.category)) {
      l1 = doc.category[0] || ''
      l2 = doc.category[1] || ''
      l3 = doc.category[2] || ''
    } else {
      l1 = String(doc.category).trim()
    }
  }
  return { l1, l2, l3 }
}

function mapProduct(doc) {
  const F = CONFIG.FIELD
  let sku = F.sku === '_id' ? String(doc._id) : (doc[F.sku] != null ? String(doc[F.sku]).trim() : '')
  let name = doc[F.name] != null ? String(doc[F.name]).trim() : ''
  let cost = 0
  if (F.cost && doc[F.cost] != null) {
    const n = parseFloat(doc[F.cost])
    if (!isNaN(n)) cost = n
  }
  const { l1, l2, l3 } = resolveCategory(doc)
  return { sku, name, default_cost_price: cost, category_l1: l1, category_l2: l2, category_l3: l3 }
}

// 简单 POST JSON（不依赖第三方库）
function postJson(url, data, token) {
  return new Promise((resolve, reject) => {
    const u = new URL(url)
    const body = JSON.stringify(data)
    const req = https.request(
      {
        hostname: u.hostname,
        port: u.port || 443,
        path: u.pathname + u.search,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Sync-Token': token,
          'Content-Length': Buffer.byteLength(body),
        },
      },
      (res) => {
        let buf = ''
        res.on('data', (c) => (buf += c))
        res.on('end', () => {
          try {
            resolve({ status: res.statusCode, body: buf ? JSON.parse(buf) : null })
          } catch (e) {
            resolve({ status: res.statusCode, body: buf })
          }
        })
      }
    )
    req.on('error', reject)
    req.write(body)
    req.end()
  })
}

// 分页读取整个商品集合
async function fetchAllGoods() {
  const db = cloud.database()
  const coll = db.collection(CONFIG.GOODS_COLLECTION)
  const count = await coll.count()
  const total = count.total
  const goods = []
  for (let skip = 0; skip < total; skip += CONFIG.PAGE_SIZE) {
    const res = await coll.skip(skip).limit(CONFIG.PAGE_SIZE).get()
    for (const doc of res.data) {
      const m = mapProduct(doc)
      if (m.sku && m.name) goods.push(m)
    }
  }
  return goods
}

exports.main = async (event, context) => {
  try {
    const goods = await fetchAllGoods()
    if (!goods.length) {
      return { ok: true, upserted: 0, message: '云数据库里没有可读的商品' }
    }
    // 分批推送（每批 100 条），避免单个请求过大
    let upserted = 0
    for (let i = 0; i < goods.length; i += CONFIG.PAGE_SIZE) {
      const batch = goods.slice(i, i + CONFIG.PAGE_SIZE)
      const r = await postJson(
        CONFIG.STATS_API_URL.replace(/\/$/, '') + '/api/sync/goods',
        { goods: batch },
        CONFIG.STATS_SYNC_TOKEN
      )
      if (r.status !== 200) {
        return { ok: false, status: r.status, detail: r.body, message: '推送失败，请检查 STATS_API_URL 与 STATS_SYNC_TOKEN' }
      }
      upserted += (r.body && r.body.upserted) || batch.length
    }
    return { ok: true, upserted, total: goods.length, message: `已同步 ${upserted} 个商品（含大/小分类）到统计后台` }
  } catch (e) {
    return { ok: false, error: String(e), message: '读取云数据库失败，请检查集合名与字段映射' }
  }
}
