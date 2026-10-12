const $ = (id) => document.getElementById(id);

function applyTheme(theme) {
  const next = theme === "light" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("quake-theme", next);
  document.querySelectorAll(".theme-switch button").forEach((btn) => {
    btn.classList.toggle("on", btn.dataset.theme === next);
  });
}

applyTheme(document.documentElement.dataset.theme || "dark");
document.querySelector(".theme-switch").onclick = (e) => {
  const btn = e.target.closest("button");
  if (btn?.dataset.theme) applyTheme(btn.dataset.theme);
};
const chips = [
  'domain:"example.com"',
  'ip:"1.1.1.1"',
  "port:443",
  'app:"nginx"',
  'title:"登录"',
  'body:"管理"',
  'country_cn:"中国"',
];

const handbook = [
  {
    title: "写法",
    note: "采用 Quake 官方 Query String。含中文或空格的取值须使用双引号，逻辑运算符须大写。",
    items: [
      ["AND", "同时满足"],
      ["OR", "任一满足"],
      ["NOT", "排除"],
      ['"奇虎科技"', "中文/空格要加双引号"],
      ["port:[80 TO 1024]", "区间"],
      ["port:>=80", "大于等于"],
      ["(A OR B) AND C", "括号优先"],
    ],
  },
  {
    title: "基本信息",
    items: [
      ['ip:"1.1.1.1"', "单个 IP"],
      ['ip:"1.1.1.0/24"', "CIDR 网段"],
      ['ip:"2001:db8::1"', "IPv6"],
      ["is_ipv6:true", "仅 IPv6"],
      ["is_ipv6:false", "仅 IPv4"],
      ["port:443", "端口"],
      ["port:[80 TO 1024]", "端口区间"],
      ['ports:"80,443,8080"', "同时开过这些端口"],
      ['transport:"tcp"', "tcp"],
      ['transport:"udp"', "udp"],
      ["is_latest:true", "仅最新数据"],
      ["is_domain:false", "只要 IP 不要域名"],
    ],
  },
  {
    title: "主机与域名",
    items: [
      ['domain:"360.cn"', "域名"],
      ['domain:*.360.cn', "子域通配"],
      ['hostname:"www.example.com"', "主机名 / rDNS"],
      ['os:"Windows"', "操作系统"],
    ],
  },
  {
    title: "ASN 与组织",
    items: [
      ['asn:"4134"', "自治域号"],
      ['org:"Tencent"', "自治域组织"],
      ['isp:"联通"', "运营商"],
      ['owner:"清华大学"', "IP 归属单位", true],
    ],
  },
  {
    title: "服务与网页",
    items: [
      ['service:"http"', "协议 / 服务名"],
      ['app:"Apache"', "产品指纹"],
      ['version:"1.2.1"', "产品版本"],
      ['title:"登录"', "网页标题"],
      ['body:"管理后台"', "网页正文"],
      ['header:"nginx"', "HTTP 头"],
      ['server:"nginx"', "Server 头"],
      ["status_code:200", "HTTP 状态码"],
    ],
  },
  {
    title: "证书与响应",
    items: [
      ['cert:"360.cn"', "证书内容"],
      ['favicon:"d41d8cd98f00b204e9800998ecf8427e"', "图标 MD5"],
      ['response:"220 ProFTPD"', "端口原始响应"],
    ],
  },
  {
    title: "地理位置",
    items: [
      ['country:"CN"', "国家代码 / 英文"],
      ['country_cn:"中国"', "国家中文"],
      ['province:"Beijing"', "省份英文，按省拆分可扩大覆盖"],
      ['province_cn:"北京"', "省份中文"],
      ['city:"Shanghai"', "城市英文"],
      ['city_cn:"上海"', "城市中文"],
    ],
  },
  {
    title: "备案",
    note: "需会员权限。基础会员将返回「暂不支持该字段查询」。",
    vip: true,
    items: [
      ['icp:"京ICP"', "备案号"],
      ['icp_keywords:"腾讯"', "备案主体关键词"],
      ['icp:"*"', "有备案"],
      ['NOT icp:"*"', "没有备案"],
    ],
  },
  {
    title: "精细化识别",
    note: "需会员权限。基础会员将返回「暂不支持该字段查询」。",
    vip: true,
    items: [
      ['catalog:"IoT物联网"', "应用大类"],
      ['type:"防火墙"', "应用类型"],
      ['level:"硬件设备层"', "应用层级"],
      ['vendor:"微软"', "厂商"],
    ],
  },
  {
    title: "图像与场景",
    note: "需会员权限。基础会员将返回「暂不支持该字段查询」。",
    vip: true,
    items: [
      ['img_tag:"windows"', "图片标签"],
      ['img_ocr:"admin"', "图片文字"],
      ['sys_tag:"CDN"', "应用场景"],
    ],
  },
  {
    title: "常用组合",
    items: [
      ['port:443 AND country_cn:"中国"', "国内 443"],
      ['app:"nginx" AND port:443 AND country:"CN"', "国内 Nginx HTTPS"],
      ['title:"登录" AND NOT port:8888', "登录页并排除端口"],
      ['service:"http" AND country_cn:"中国" AND NOT province_cn:"香港"', "国内 Web 排除香港"],
    ],
  },
];

function fieldOf(code) {
  const match = String(code).match(/^([a-zA-Z_][\w.]*)/);
  return match ? match[1].toLowerCase() : "";
}

const VIP_FIELDS = [
  ...new Set(
    handbook.flatMap((group) =>
      group.items
        .filter((item) => group.vip || item[2])
        .map(([code]) => fieldOf(code))
        .filter(Boolean)
    )
  ),
];

const state = {
  account: null,
  history: [],
  catalog: [],
  fields: [],
  unmask_ip: false,
  job: null,
  rows: [],
};

function toast(text) {
  const el = $("toast");
  el.textContent = text;
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => {
    el.hidden = true;
  }, 2200);
}

async function api(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const text = await res.text();
  let data = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }
  if (!res.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail || data));
  }
  return data;
}

function renderAccount() {
  const box = $("account-box");
  const c = state.account;
  $("btn-add").hidden = !!c;
  if (!c) {
    box.innerHTML = "";
    $("account-hint").hidden = false;
    return;
  }
  $("account-hint").hidden = true;
  const mark = c.ok === true ? "ok" : c.ok === false ? "bad" : "wait";
  const who = [c.username, c.role].filter(Boolean).join(" · ");
  const quota = [
    c.month != null ? `月度积分 ${c.month}` : "",
    c.persistent != null ? `长效积分 ${c.persistent}` : "",
    c.api != null ? `API 余量 ${c.api}` : "",
  ].filter(Boolean);
  box.innerHTML = `<article class="cookie">
    <div class="top">
      <span class="dot ${mark}"></span>
      <span class="name" title="${esc(c.name)}">${esc(c.name)}</span>
    </div>
    ${who ? `<div class="meta">${esc(who)}</div>` : ""}
    ${quota.length ? `<div class="quota">${quota.map((line) => `<div>${esc(line)}</div>`).join("")}</div>` : c.message ? `<div class="meta">${esc(c.message)}</div>` : ""}
    <div class="preview">${esc(c.preview || "")}</div>
    <div class="row">
      <button type="button" class="btn tiny" data-act="check">校验</button>
      <button type="button" class="btn tiny" data-act="edit">编辑</button>
      <button type="button" class="btn tiny danger" data-act="del">移除</button>
    </div>
  </article>`;
}

function renderHistory() {
  $("history").innerHTML = state.history
    .map(
      (h) =>
        `<button class="hist" data-query="${encodeURIComponent(h.query)}">${h.query}<small>${h.count ?? ""}</small></button>`
    )
    .join("");
}

function setStatus(text, ratio) {
  $("status").textContent = text;
  if (typeof ratio === "number") $("bar").style.width = `${Math.max(0, Math.min(100, ratio * 100))}%`;
}

function renderHead() {
  $("thead").innerHTML = state.fields.map((f) => `<th>${esc(f.label)}</th>`).join("");
}

function renderRows(filter = "") {
  const key = filter.trim().toLowerCase();
  const cols = state.fields;
  const rows = key
    ? state.rows.filter((row) => Object.values(row).some((v) => String(v).toLowerCase().includes(key)))
    : state.rows;
  renderHead();
  $("tbody").innerHTML = rows
    .map((row) => {
      const cells = cols
        .map((f) => {
          const val = row[f.id] ?? "";
          return `<td title="${esc(val)}">${esc(val)}</td>`;
        })
        .join("");
      return `<tr data-i="${row._i}">${cells}</tr>`;
    })
    .join("");
  $("empty").hidden = rows.length > 0;
  $("pane-json").textContent = JSON.stringify(
    rows.map(({ _i, _url, ...rest }) => rest),
    null,
    2
  );
}

function esc(v) {
  return String(v ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function openModal(html) {
  $("modal").classList.remove("wide", "fields");
  $("modal").onclick = null;
  $("modal").innerHTML = html;
  $("overlay").hidden = false;
}

function closeModal() {
  $("overlay").hidden = true;
  $("modal").classList.remove("wide", "fields");
}

function accountForm(edit) {
  openModal(`
    <h2>${edit ? "编辑账号" : "添加账号"}</h2>
    <label>名称</label>
    <input id="f-name" value="${esc(edit ? state.account?.name || "" : "")}" placeholder="可选" />
    <label>Cookie</label>
    <textarea id="f-cookie" placeholder="${edit ? "留空表示不修改" : "粘贴浏览器请求头中的 Cookie"}"></textarea>
    <div class="actions">
      <button class="btn" id="f-cancel">取消</button>
      <button class="btn primary" id="f-save">保存</button>
    </div>
  `);
  $("f-cancel").onclick = closeModal;
  $("f-save").onclick = async () => {
    const payload = { name: $("f-name").value.trim() };
    const cookie = $("f-cookie").value.trim();
    if (cookie) payload.cookie = cookie;
    if (edit) {
      if (!payload.name && !payload.cookie) return toast("没有需要更新的内容");
      await api("/api/account", { method: "PATCH", body: JSON.stringify(payload) });
    } else {
      if (!payload.cookie) return toast("请粘贴 Cookie");
      await api("/api/account", { method: "PUT", body: JSON.stringify(payload) });
    }
    closeModal();
    await boot();
    toast("已保存");
  };
}

const FIELD_GROUPS = [
  { title: "基础", ids: ["ip", "port", "transport", "service", "version", "domain", "hostname", "host"] },
  { title: "服务", ids: ["title", "server", "status_code", "x_powered_by", "url", "cert"] },
  { title: "归属", ids: ["country", "province", "city", "isp", "scene", "org", "asn", "asname"] },
  { title: "识别", ids: ["components", "sys_tag", "time", "os"] },
];

function openFields() {
  openModal(`
    <div class="fields-head">
      <div>
        <h2>字段</h2>
        <p class="hb-note">选择并排列表格与导出列</p>
      </div>
      <div class="fields-count" id="fields-count"></div>
    </div>
    <div class="fields-board">
      <section class="fields-pane">
        <header>当前列</header>
        <div class="fields-order" id="field-picked"></div>
      </section>
      <section class="fields-pane">
        <header>
          <span>添加列</span>
          <input id="f-search" type="search" placeholder="筛选" />
        </header>
        <div class="fields-catalog" id="field-list"></div>
        <div class="field-add">
          <input id="f-path" placeholder="自定义路径，例如 service.http.server" />
          <input id="f-label" placeholder="列名" />
          <button type="button" class="btn" id="f-add-path">添加</button>
        </div>
      </section>
    </div>
    <div class="fields-foot">
      <label class="field-easter">
        <input type="checkbox" id="f-unmask" ${state.unmask_ip ? "checked" : ""} />
        去 IP 码
      </label>
      <div class="actions">
        <button type="button" class="btn ghost" id="f-reset">恢复默认</button>
        <button type="button" class="btn" id="f-cancel">取消</button>
        <button type="button" class="btn primary" id="f-save">保存</button>
      </div>
    </div>
  `);
  $("modal").classList.add("fields");
  const draft = state.fields.map((f) => ({ ...f }));

  function paint() {
    $("fields-count").innerHTML = `已选 <b>${draft.length}</b> 列`;
    $("field-picked").innerHTML = draft
      .map(
        (f, i) => `<article class="fields-order-item" data-i="${i}">
          <span class="idx">${String(i + 1).padStart(2, "0")}</span>
          <div>
            <div class="name">${esc(f.label)}</div>
            ${f.path ? `<div class="path">${esc(f.path)}</div>` : ""}
          </div>
          <div class="fields-ops">
            <button type="button" data-act="up" title="上移">↑</button>
            <button type="button" data-act="down" title="下移">↓</button>
            <button type="button" class="del" data-act="del" title="移除">×</button>
          </div>
        </article>`
      )
      .join("");
    const ids = new Set(draft.map((f) => f.id));
    const q = ($("f-search").value || "").trim().toLowerCase();
    const grouped = FIELD_GROUPS.map((group) => {
      const items = group.ids
        .map((id) => state.catalog.find((f) => f.id === id))
        .filter(Boolean)
        .filter((f) => !q || `${f.label} ${f.id} ${f.path || ""}`.toLowerCase().includes(q));
      if (!items.length) return "";
      return `<div class="fields-group">
        <h3>${group.title}</h3>
        <div class="fields-pills">${items
          .map(
            (f) => `<button type="button" class="field-pill ${ids.has(f.id) ? "on" : ""}" data-id="${esc(f.id)}">
              <span>${esc(f.label)}</span>
              ${f.path ? `<small>${esc(f.path)}</small>` : ""}
            </button>`
          )
          .join("")}</div>
      </div>`;
    }).join("");
    const extras = draft.filter((f) => !state.catalog.some((c) => c.id === f.id));
    const extraHtml =
      extras.length && extras.some((f) => !q || `${f.label} ${f.id} ${f.path || ""}`.toLowerCase().includes(q))
        ? `<div class="fields-group"><h3>自定义</h3><div class="fields-pills">${extras
            .filter((f) => !q || `${f.label} ${f.id} ${f.path || ""}`.toLowerCase().includes(q))
            .map(
              (f) => `<button type="button" class="field-pill on" data-id="${esc(f.id)}">
                <span>${esc(f.label)}</span>
                ${f.path ? `<small>${esc(f.path)}</small>` : ""}
              </button>`
            )
            .join("")}</div></div>`
        : "";
    $("field-list").innerHTML = grouped + extraHtml || `<p class="hb-note">没有匹配字段</p>`;
  }

  paint();
  $("f-search").oninput = paint;
  $("field-picked").onclick = (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    const item = btn.closest(".fields-order-item");
    const i = Number(item.dataset.i);
    const act = btn.dataset.act;
    if (act === "del") draft.splice(i, 1);
    if (act === "up" && i > 0) draft.splice(i - 1, 0, draft.splice(i, 1)[0]);
    if (act === "down" && i < draft.length - 1) draft.splice(i + 1, 0, draft.splice(i, 1)[0]);
    paint();
  };
  $("field-list").onclick = (e) => {
    const pill = e.target.closest(".field-pill");
    if (!pill) return;
    const id = pill.dataset.id;
    const i = draft.findIndex((f) => f.id === id);
    if (i >= 0) draft.splice(i, 1);
    else {
      const spec = state.catalog.find((f) => f.id === id);
      if (spec) draft.push({ ...spec });
    }
    paint();
  };
  $("f-add-path").onclick = () => {
    const path = $("f-path").value.trim();
    if (!path) return toast("请输入字段路径");
    const label = $("f-label").value.trim() || path;
    if (draft.some((f) => f.path === path || f.id === path)) return toast("该字段已存在");
    draft.push({ id: path, label, path });
    $("f-path").value = "";
    $("f-label").value = "";
    paint();
  };
  $("f-reset").onclick = () => {
    draft.length = 0;
    for (const spec of state.catalog) {
      if (["ip", "port", "transport", "service", "domain", "title", "components", "country", "province", "city", "isp", "org", "asn", "time"].includes(spec.id)) {
        draft.push({ ...spec });
      }
    }
    paint();
  };
  $("f-cancel").onclick = closeModal;
  $("f-save").onclick = async () => {
    if (!draft.length) return toast("请至少保留一个字段");
    const data = await api("/api/fields", {
      method: "PUT",
      body: JSON.stringify({ fields: draft, unmask_ip: $("f-unmask").checked }),
    });
    state.fields = data.fields;
    state.unmask_ip = !!data.unmask_ip;
    closeModal();
    if (state.job) {
      const rows = await api(`/api/search/${state.job.id}/rows?limit=5000`);
      state.rows = rows.rows;
      if (rows.fields) state.fields = rows.fields;
    }
    renderRows($("filter").value);
    toast("字段已更新");
  };
}

async function boot() {
  const data = await api("/api/state");
  state.account = data.account;
  state.history = data.history;
  state.catalog = data.catalog || [];
  state.fields = data.settings?.fields || [];
  state.unmask_ip = !!data.settings?.unmask_ip;
  renderAccount();
  renderHistory();
  renderHead();
}

function vipFieldsIn(query) {
  const found = [];
  for (const field of VIP_FIELDS) {
    const re = new RegExp(`(?:^|\\s|\\()${field}\\s*:`, "i");
    if (re.test(query)) found.push(field);
  }
  return found;
}

function setSearching(on) {
  $("btn-search").disabled = on;
  $("btn-split").disabled = on;
  $("btn-cancel").hidden = !on;
}

async function search(split) {
  const query = $("query").value.trim();
  const size = Number($("size").value || 100);
  if (!query) return toast("请输入检索语句");
  if (!state.account) return toast("请先添加账号");
  if (split && /\bprovince(_cn|_en)?\s*:/i.test(query)) {
    return toast("语句已包含省份条件，直接检索即可");
  }
  const blocked = vipFieldsIn(query);
  const basic = /基础|注册|basic/i.test(`${state.account.role || ""}`);
  if (blocked.length && basic) {
    const msg = `当前账号权限不足，无法使用字段：${blocked.join("、")}`;
    setStatus(msg);
    return toast(msg);
  }
  setSearching(true);
  setStatus(split ? "正在按地区拆分检索…" : "正在检索…", 0.04);
  try {
    const job = await api("/api/search", {
      method: "POST",
      body: JSON.stringify({ query, size, split: !!split }),
    });
    state.job = job;
    listen(job.id);
  } catch (err) {
    setStatus(err.message);
    setSearching(false);
    toast(err.message);
  }
}

async function listen(id) {
  while (state.job && state.job.id === id) {
    const job = await api(`/api/search/${id}`);
    state.job = job;
    const ratio = job.pages ? job.page / job.pages : 0;
    if (job.status === "running") {
      setStatus(`已获取 ${job.count} 条${job.using ? " · " + job.using : ""} · ${job.page}/${job.pages}`, ratio);
    }
    if (job.status === "done") {
      const data = await api(`/api/search/${id}/rows?limit=20000`);
      state.rows = data.rows;
      if (data.fields) state.fields = data.fields;
      renderRows($("filter").value);
      const s = data.stats;
      $("stats").textContent = `${s.count} 条 · ${s.ips} 个 IP · ${s.ports} 个端口`;
      setStatus(`检索完成，共 ${s.count} 条`, 1);
      setSearching(false);
      boot();
      return;
    }
    if (job.status === "error" || job.status === "cancelled") {
      setStatus(job.error || "已取消");
      setSearching(false);
      if (job.error) toast(job.error);
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
}

$("chips").innerHTML = chips.map((c) => `<button class="chip">${c}</button>`).join("");
$("chips").onclick = (e) => {
  if (!e.target.classList.contains("chip")) return;
  insertQuery(e.target.textContent);
};

function insertQuery(piece) {
  const cur = $("query").value.trim();
  if (!piece) return;
  if (piece === "AND" || piece === "OR" || piece === "NOT") {
    $("query").value = cur ? `${cur} ${piece} ` : `${piece} `;
  } else {
    $("query").value = cur ? `${cur} AND ${piece}` : piece;
  }
  $("query").focus();
}

function renderHandbook(filter = "") {
  const key = filter.trim().toLowerCase();
  const groups = handbook
    .map((group) => {
      const items = group.items.filter(([code, label]) => {
        if (!key) return true;
        return `${group.title} ${code} ${label}`.toLowerCase().includes(key);
      });
      if (!items.length) return "";
      const html = items
        .map(([code, label, vip]) => {
          const member = group.vip || vip;
          return `<button type="button" class="hb-item${member ? " vip-item" : ""}" data-q="${esc(code)}"><code>${esc(code)}</code><span>${esc(label)}${member && !group.vip ? " · 会员" : ""}</span></button>`;
        })
        .join("");
      const note = group.note ? `<p class="hb-note">${esc(group.note)}</p>` : "";
      const tag = group.vip ? `<em class="vip">会员</em>` : "";
      return `<div class="hb-group"><h3>${esc(group.title)} ${tag}</h3>${note}<div>${html}</div></div>`;
    })
    .filter(Boolean)
    .join("");
  const box = $("handbook");
  if (box) box.innerHTML = groups || `<p class="hb-note">未找到匹配语法。</p>`;
}

function openHandbook() {
  openModal(`
    <h2>检索语法</h2>
    <p class="hb-note">语法与 Quake 官方检索一致。点击即可填入。会员字段仅对具备相应权限的账号生效。</p>
    <input id="hb-filter" type="search" placeholder="按字段筛选，例如 icp、title、证书" />
    <div class="handbook" id="handbook"></div>
    <div class="actions"><button type="button" class="btn primary" id="f-cancel">关闭</button></div>
  `);
  $("modal").classList.add("wide");
  renderHandbook();
  $("hb-filter").oninput = () => renderHandbook($("hb-filter").value);
  $("f-cancel").onclick = closeModal;
  $("modal").onclick = (e) => {
    const item = e.target.closest(".hb-item");
    if (!item) return;
    insertQuery(item.dataset.q);
    closeModal();
  };
}

$("btn-syntax").onclick = openHandbook;
$("btn-fields").onclick = openFields;
$("btn-add").onclick = () => accountForm(false);
$("btn-search").onclick = () => search(false);
$("btn-split").onclick = () => search(true);
$("query").addEventListener("keydown", (e) => {
  if (e.key === "Enter") search();
});
$("btn-cancel").onclick = async () => {
  if (state.job) await api(`/api/search/${state.job.id}/cancel`, { method: "POST" });
};

$("account-box").onclick = async (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  const act = btn.dataset.act;
  if (act === "del") {
    await api("/api/account", { method: "DELETE" });
    await boot();
    return;
  }
  if (act === "check") {
    btn.disabled = true;
    setStatus("正在读取账号配额…");
    try {
      const r = await api("/api/account/check", { method: "POST" });
      setStatus(r.message || "账号可用");
      toast(r.message || "账号可用");
    } catch (err) {
      setStatus(err.message);
      toast(err.message);
    }
    await boot();
    return;
  }
  if (act === "edit") accountForm(true);
};

$("history").onclick = (e) => {
  const btn = e.target.closest(".hist");
  if (!btn) return;
  $("query").value = decodeURIComponent(btn.dataset.query);
  $("query").focus();
};

document.querySelectorAll(".tab").forEach((tab) => {
  tab.onclick = () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("on"));
    tab.classList.add("on");
    $("pane-table").classList.toggle("on", tab.dataset.tab === "table");
    $("pane-json").classList.toggle("on", tab.dataset.tab === "json");
  };
});

$("filter").oninput = () => renderRows($("filter").value);

$("exports").onclick = (e) => {
  const btn = e.target.closest("button");
  if (!btn || !state.job) return;
  window.location = `/api/search/${state.job.id}/export?fmt=${btn.dataset.fmt}`;
};

async function openDetail(index) {
  if (!state.job) return;
  const item = await api(`/api/search/${state.job.id}/item/${index}`);
  openModal(`
    <h2>资产详情</h2>
    <pre class="json">${esc(JSON.stringify(item, null, 2))}</pre>
    <div class="actions"><button class="btn primary" id="f-cancel">关闭</button></div>
  `);
  $("f-cancel").onclick = closeModal;
}

function openRowUrl(index) {
  const row = state.rows.find((item) => String(item._i) === String(index));
  let url = row?._url || row?.url || "";
  if (!url) return toast("没有可打开的地址");
  if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(url)) url = "http://" + url;
  window.open(url, "_blank", "noopener,noreferrer");
}

let rowClickTimer = 0;
$("tbody").onclick = (e) => {
  const tr = e.target.closest("tr");
  if (!tr || !state.job) return;
  clearTimeout(rowClickTimer);
  rowClickTimer = setTimeout(() => openDetail(tr.dataset.i), 280);
};
$("tbody").ondblclick = (e) => {
  const tr = e.target.closest("tr");
  if (!tr || !state.job) return;
  e.preventDefault();
  clearTimeout(rowClickTimer);
  openRowUrl(tr.dataset.i);
};

$("overlay").addEventListener("click", (e) => {
  if (e.target.id === "overlay") closeModal();
});

boot().catch((err) => setStatus(err.message));
