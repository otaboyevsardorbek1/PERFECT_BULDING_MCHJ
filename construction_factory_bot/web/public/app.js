/* ===== Qurilish Korxonasi Dashboard v3 — app controller ===== */
"use strict";

const $ = (sel) => document.querySelector(sel);
const fmtMoney = (v) =>
  new Intl.NumberFormat("uz-UZ", { maximumFractionDigits: 0 }).format(Number(v || 0)) + " so'm";
const fmtNum = (v) => new Intl.NumberFormat("uz-UZ", { maximumFractionDigits: 0 }).format(Number(v || 0));
const fmtMb = (v) => new Intl.NumberFormat("uz-UZ", { maximumFractionDigits: 2 }).format(Number(v || 0));
const fmtDate = (iso) => {
  if (!iso) return "-";
  const d = new Date(iso);
  return d.toLocaleString("uz-UZ", { dateStyle: "short", timeStyle: "short" });
};
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[c]));

const state = { page: "overview" };
const PAGES = {
  overview: "📊 Umumiy ko'rsatkichlar",
  warehouse: "📦 Ombor holati",
  products: "🏭 Mahsulotlar",
  customers: "👥 Mijozlar (CRM)",
  suppliers: "🚚 Yetkazib beruvchilar",
  receipts: "📦 Qabul aktlari",
  reservations: "🔒 Rezervatsiya",
  transfers: "🔄 Ko'chirish",
  inventory: "📋 Inventarizatsiya",
  finance: "💰 Moliya",
  roles: "🔐 Rollar",
  backup: "💾 Backup va tiklash",
  fuel: "⛽ Yoqilg'i nazorati",
  expenses: "🧾 Avans hisobotlari",
  picking: "📦 Yig'ish varaqalari",
  security: "🚨 Shubhali harakatlar",
  ratings: "🏆 Sotuvchilar reytingi",
};
/* Sahifa -> rol matritsasi moduli */
const PAGE_MODULES = {
  overview: "reports", warehouse: "warehouse", products: "production",
  customers: "crm", suppliers: "supplier", receipts: "supplier",
  reservations: "stock_ops", transfers: "stock_ops", inventory: "stock_ops",
  finance: "finance", roles: "admin", backup: "admin",
  fuel: "fuel", expenses: "expenses", picking: "picking",
  security: "security", ratings: "ratings",
};

/* ---------- Auth ---------- */
let TOKEN = localStorage.getItem("wb_token") || "";
let REFRESH = localStorage.getItem("wb_refresh") || "";
let ME = null; // { full_name, role, role_label, permissions: {can_view, can_edit, see_cost} }

const canViewModule = (m) => !!ME && (ME.permissions.can_view || []).includes(m);
const canEditModule = (m) => !!ME && (ME.permissions.can_edit || []).includes(m);
const allowedPages = () => Object.keys(PAGES).filter((p) => canViewModule(PAGE_MODULES[p]));

function saveTokens(t, r) {
  TOKEN = t || "";
  REFRESH = r || "";
  if (t) localStorage.setItem("wb_token", t); else localStorage.removeItem("wb_token");
  if (r) localStorage.setItem("wb_refresh", r); else localStorage.removeItem("wb_refresh");
}

function clearSession() {
  saveTokens("", "");
  ME = null;
}

function showLogin(msg) {
  $("#login-view").classList.remove("hidden");
  const errEl = $("#login-error");
  if (msg) { errEl.textContent = msg; errEl.classList.remove("hidden"); }
}
function hideLogin() { $("#login-view").classList.add("hidden"); }

/* ---------- API helper ---------- */
async function _fetch(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (TOKEN) headers["Authorization"] = "Bearer " + TOKEN;
  return await fetch("/api" + path, { ...options, headers });
}

async function tryRefresh() {
  /* Refresh token bilan yangi access olish (sliding sessiya) */
  if (!REFRESH) return false;
  try {
    const res = await fetch("/api/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: REFRESH }),
    });
    const body = await res.json().catch(() => null);
    if (!res.ok || !body || !body.token) return false;
    saveTokens(body.token, body.refresh_token);
    ME = body.user;
    return true;
  } catch (e) {
    return false;
  }
}

async function api(path, options = {}, retried = false) {
  const res = await _fetch(path, options);
  let body = null;
  try { body = await res.json(); } catch (e) { /* body bo'lmasa ham bo'ladi */ }
  if (res.status === 401 && !retried) {
    // Access muddati o'tgan bo'lishi mumkin — bir marta refresh qilib qayta urinamiz
    if (await tryRefresh()) {
      return await api(path, options, true);
    }
    clearSession();
    showLogin((body && (body.error || body.detail)) || "Iltimos, qayta kiring");
    throw new Error("401");
  }
  if (!res.ok) throw new Error((body && (body.error || body.detail)) || `HTTP ${res.status}`);
  return body;
}
const apiGet = (p) => api(p);
const apiPost = (p, data) =>
  api(p, { method: "POST", body: JSON.stringify(data) });

async function doLogin(phone, password, otpCode) {
  // Login'da 401 = noto'g'ri parol, refresh qilish shart emas — to'g'ridan-to'g'ri so'raladi
  const payload = { phone, password };
  if (otpCode) payload.otp_code = otpCode;
  const res = await _fetch("/login", { method: "POST", body: JSON.stringify(payload) });
  const body = await res.json().catch(() => null);
  if (res.status === 428) {
    // 2FA yoqilgan xodim: parol to'g'ri, endi Google Authenticator kodi kerak.
    // OTP formani ko'rsatamiz va applyUser() chaqirilishini to'xtatamiz.
    showOtpStep();
    throw new Error("Google Authenticator kodi talab qilinadi");
  }
  if (!res.ok) throw new Error((body && (body.error || body.detail)) || `HTTP ${res.status}`);
  saveTokens(body.token, body.refresh_token);
  ME = body.user;
  return ME;
}

/* ---------- 2FA (Google Authenticator) login bosqichi ---------- */
// Login paroli to'g'ri chiqqanda, 2FA yoqilgan xodimlar uchun kod so'raladi.
// OTP formasi index.html'dagi #otp-form; telefon+parol login formada qoladi.
function showOtpStep() {
  const otpCode = $("#otp-code");
  const errEl = $("#otp-error");
  if (otpCode) otpCode.value = "";
  if (errEl) errEl.classList.add("hidden");
  $("#login-form").classList.add("hidden");
  $("#otp-form").classList.remove("hidden");
  if (otpCode) otpCode.focus();
}

function hideOtpStep() {
  $("#otp-form").classList.add("hidden");
  $("#login-form").classList.remove("hidden");
  const errEl = $("#otp-error");
  if (errEl) errEl.classList.add("hidden");
}

/* DOM tayyor bo'lgach OTP formani ulaymiz (script body oxirida, DOM mavjud). */
(function () {
  const otpForm = document.getElementById("otp-form");
  if (!otpForm) return;
  otpForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const otpEl = document.getElementById("otp-code");
    const errEl = document.getElementById("otp-error");
    errEl.classList.add("hidden");
    const code = otpEl.value.trim();
    if (!/^\d{6}$/.test(code)) {
      errEl.textContent = "6 xonali raqamli kodni kiriting";
      errEl.classList.remove("hidden");
      return;
    }
    const submitBtn = document.getElementById("otp-submit");
    submitBtn.disabled = true;
    try {
      const user = await doLogin(
        document.getElementById("login-phone").value.trim(),
        document.getElementById("login-password").value,
        code
      );
      if (user && user.twoFaRequired) {
        errEl.textContent = "Kod noto'g'ri yoki muddati o'tgan";
        errEl.classList.remove("hidden");
        return;
      }
      hideOtpStep();
      applyUser();
    } catch (err) {
      errEl.textContent = (err.message && err.message !== "401") ? err.message : "Kod noto'g'ri";
      errEl.classList.remove("hidden");
    } finally {
      submitBtn.disabled = false;
    }
  });
  const backBtn = document.getElementById("btn-otp-back");
  if (backBtn) backBtn.addEventListener("click", hideOtpStep);
})();

/* ---------- 2FA (Google Authenticator) boshqaruv (security sahifasi) ---------- */
function open2faSetupModal() {
  apiPost("/auth/2fa/setup", {}).then((r) => {
    openModal("🔢 2FA yoqish — Google Authenticator", `
      <p>Telefoningizdagi <b>Google Authenticator</b> ilovasida <b>+</b> → <b>QR skanerlash</b>:</p>
      ${r.qr_data_url ? `<img src="${r.qr_data_url}" style="width:190px;height:190px;display:block;margin:10px auto;border-radius:8px" alt="2FA QR">` : ""}
      <p class="muted" style="text-align:center">Yoki kalitni qo'lda kiriting:<br><code style="word-break:break-all;user-select:all">${esc(r.secret)}</code></p>
      <div class="form-group"><label>🔢 Ilovadagi 6 xonali kod</label>
        <input id="2fa-code" class="form-control" inputmode="numeric" maxlength="6" placeholder="000000"></div>
      <div class="form-actions">
        <button class="btn btn-outline" onclick="closeModal()">Bekor</button>
        <button class="btn btn-primary" onclick="window.submit2faEnable()">✅ Yoqish</button>
      </div>`);
  }).catch((e) => toast(e.message, "error"));
}

window.submit2faEnable = async function () {
  const code = (document.getElementById("2fa-code").value || "").trim();
  if (!/^\d{6}$/.test(code)) return toast("6 xonali kodni kiriting", "error");
  try {
    await apiPost("/auth/2fa/enable", { code });
    if (ME) ME.two_fa_enabled = true;
    toast("✅ 2FA yoqildi — endi har kirishda kod talab qilinadi");
    closeModal();
    navigate("security");
  } catch (e) { toast(e.message, "error"); }
};

function open2faDisableModal() {
  openModal("🔢 2FA o'chirish", `
    <p>O'chirish uchun Google Authenticator'dagi joriy <b>6 xonali kod</b>ni kiriting:</p>
    <div class="form-group"><label>🔢 Kod</label>
      <input id="2fa-code" class="form-control" inputmode="numeric" maxlength="6" placeholder="000000"></div>
    <div class="form-actions">
      <button class="btn btn-outline" onclick="closeModal()">Bekor</button>
      <button class="btn btn-danger" onclick="window.submit2faDisable()">❌ O'chirish</button>
    </div>`);
}

window.submit2faDisable = async function () {
  const code = (document.getElementById("2fa-code").value || "").trim();
  if (!/^\d{6}$/.test(code)) return toast("6 xonali kodni kiriting", "error");
  try {
    await apiPost("/auth/2fa/disable", { code });
    if (ME) ME.two_fa_enabled = false;
    toast("✅ 2FA o'chirildi — sessiyalar yangilandi, qayta kiring");
    closeModal();
    navigate("security");
  } catch (e) { toast(e.message, "error"); }
};

async function doLogout() {
  /* Server tomonda sessiyani revoke qilamiz (access ham refresh ham o'ladi) */
  const headers = { "Content-Type": "application/json" };
  if (TOKEN) headers["Authorization"] = "Bearer " + TOKEN;
  const body = REFRESH ? JSON.stringify({ refresh_token: REFRESH }) : undefined;
  try {
    await fetch("/api/logout", { method: "POST", headers, body });
  } catch (e) { /* best-effort */ }
  clearSession();
}

/* ---------- Toast ---------- */
let toastTimer;
function toast(msg, type = "success") {
  const el = $("#toast");
  el.textContent = msg;
  el.className = `toast ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), 3500);
}

/* ---------- Modal ---------- */
function openModal(title, html) {
  $("#modal-title").textContent = title;
  $("#modal-body").innerHTML = html;
  $("#modal").classList.remove("hidden");
}
function closeModal() { $("#modal").classList.add("hidden"); }

/* ---------- Render helpers ---------- */
function cards(items) {
  return `<div class="cards">${items
    .map((c) => `
      <div class="card">
        <div class="card-icon">${c.icon}</div>
        <div class="card-label">${esc(c.label)}</div>
        <div class="card-value">${c.value}</div>
        ${c.note ? `<div class="card-note">${esc(c.note)}</div>` : ""}
      </div>`)
    .join("")}</div>`;
}
function panel(title, inner, actions = "") {
  return `<div class="panel">
    <div class="panel-header"><h3>${esc(title)}</h3><div class="section-actions">${actions}</div></div>
    <div class="panel-body">${inner}</div>
  </div>`;
}
function empty(text) { return `<div class="muted" style="padding:16px">${esc(text)}</div>`; }
function badge(text, color = "gray") {
  const map = {
    green: "badge-green", red: "badge-red", yellow: "badge-yellow",
    blue: "badge-blue", gray: "badge-gray", purple: "badge-purple",
  };
  return `<span class="badge ${map[color] || "badge-gray"}">${esc(text)}</span>`;
}

/* ---------- PAGE RENDERERS ---------- */

async function renderOverview() {
  const [stats, pl] = await Promise.all([
    apiGet("/stats").catch(() => ({})),
    apiGet("/finance/pl").catch(() => ({ report: {} })),
  ]);
  const report = pl.report || {};
  const content = `
    ${cards([
      { icon: "🏭", label: "Mahsulotlar", value: fmtNum(stats.products), note: "faol" },
      { icon: "📦", label: "Xom ashyo", value: fmtNum(stats.materials), note: `${fmtNum(stats.low_stock)} ta kamaymoqda` },
      { icon: "👥", label: "Xodimlar", value: fmtNum(stats.employees), note: "faol" },
      { icon: "📋", label: "Buyurtmalar", value: fmtNum(stats.orders) },
      { icon: "💰", label: "Ombor qiymati", value: fmtMoney(stats.warehouse_value) },
      { icon: "💎", label: `Sof foyda (oy)`, value: fmtMoney(report.net_profit), note: report.profit_margin != null ? `marja ${report.profit_margin}%` : "" },
    ])}
    <div class="row">
      ${panel("💎 Foyda/Zarar — bu oy", `
        <table>
          <tr><td>Daromad</td><td>${fmtMoney(report.revenue)}</td></tr>
          <tr><td>Chegirmalar</td><td>${fmtMoney(report.discounts)}</td></tr>
          <tr><td>Tannarx (COGS)</td><td>${fmtMoney(report.cogs)}</td></tr>
          <tr><td>Ishlab chiqarish</td><td>${fmtMoney(report.production_cost)}</td></tr>
          <tr><td>Maosh</td><td>${fmtMoney(report.salary_cost)}</td></tr>
          <tr><td><b>Sof foyda</b></td><td><b>${fmtMoney(report.net_profit)}</b></td></tr>
        </table>`) }
    </div>
    ${panel("📦 Eng past zaxira (tugayotgan xom ashyo)", "", `
      <button class="btn btn-outline btn-sm" data-go="warehouse">📦 Ombor paneli</button>`) }
  `;
  return content;
}

async function renderWarehouse() {
  const w = await apiGet("/warehouse").catch(() => ({ materials: [] }));
  const materials = w.materials || [];
  const seeCost = ME ? ME.permissions.see_cost : true;
  const totalValue = materials.reduce((s, m) => s + Number(m.value || 0), 0);
  const low = materials.filter((m) => Number(m.current_stock) <= Number(m.min_stock)).length;
  const valueCols = seeCost ? "<th>Narx</th><th>Qiymat</th>" : "";
  const valueCells = (m) => seeCost
    ? `<td>${fmtMoney(m.price_per_unit)}</td><td>${fmtMoney(m.value)}</td>`
    : "";

  const content = `
    ${cards([
      { icon: "🧱", label: "Xom ashyo turlari", value: fmtNum(materials.length) },
      { icon: "⚠️", label: "Tugayotganlar", value: fmtNum(low) },
      ...(seeCost ? [{ icon: "💰", label: "Umumiy qiymat", value: fmtMoney(totalValue) }] : []),
    ])}
    ${panel("Xom ashyo qoldiqlari", materials.length ? `
      <table>
        <thead><tr><th>Nomi</th><th>Birlik</th><th>Qoldiq</th><th>Min.</th>${valueCols}<th>Holat</th></tr></thead>
        <tbody>
        ${materials.map((m) => `
          <tr>
            <td>${esc(m.name)}</td><td>${esc(m.unit)}</td>
            <td>${fmtNum(m.current_stock)}</td><td>${fmtNum(m.min_stock)}</td>
            ${valueCells(m)}
            <td>${Number(m.current_stock) <= Number(m.min_stock) ? badge("Kam", "red") : badge("Yetarli", "green")}</td>
          </tr>`).join("")}
        </tbody>
      </table>` : empty("Xom ashyo yo'q"))}
  `;
  return content;
}

async function renderProducts() {
  const data = await apiGet("/products").catch(() => ({ products: [] }));
  const products = data.products || [];
  const seeCost = ME ? ME.permissions.see_cost : true;
  const costCols = seeCost ? "<th>Tannarx</th><th>Foyda</th>" : "";
  const costCells = (p) => {
    if (!seeCost) return "";
    const profit = Number(p.selling_price) - Number(p.production_cost || 0);
    return `<td>${fmtMoney(p.production_cost)}</td>` +
      `<td>${profit >= 0 ? badge("foydali", "green") : badge("zarar", "red")} (${fmtNum(Number(p.profit_margin || 0) * 100)}%)</td>`;
  };
  const content = `
    ${cards([
      { icon: "🏭", label: "Faol mahsulotlar", value: fmtNum(products.length) },
    ])}
    ${panel("Mahsulot katalogi", products.length ? `
      <table>
        <thead><tr><th>Nomi</th><th>Birlik</th><th>Sotuv narxi</th>${costCols}</tr></thead>
        <tbody>
        ${products.map((p) => `
          <tr>
            <td>${esc(p.name)}</td><td>${esc(p.unit)}</td>
            <td>${fmtMoney(p.selling_price)}</td>
            ${costCells(p)}
          </tr>`).join("")}
        </tbody>
      </table>` : empty("Mahsulotlar yo'q"))}
    <div class="row" style="gap:8px">
      ${panel("💱 O'lchov birliklari konvertatsiyasi", `
        <div class="form-group">
          <label>1 qop = 50 kg kabi konvertatsiyani tekshirish uchun /api/convert so'rovidan foydalaning.<br>
          Botda: 💱 Konvertatsiya bo'limi orqali amalga oshiriladi.</label>
        </div>`) }
    </div>
  `;
  return content;
}

function tierBadge(t) {
  if (t === "gold") return badge("🏅 Oltin", "gold");
  if (t === "silver") return badge("🥈 Kumush", "silver");
  return badge("🥉 Bronza", "bronze");
}

async function renderCustomers() {
  const [data, seg] = await Promise.all([
    apiGet("/customers?limit=100").catch(() => ({ customers: [] })),
    apiGet("/customers/segmentation").catch(() => ({ segmentation: { gold: 0, silver: 0, bronze: 0 } })),
  ]);
  const customers = data.customers || [];
  const totalDebt = customers.reduce((s, c) => s + Number(c.total_debt || 0), 0);
  const debtors = customers.filter((c) => Number(c.total_debt) > 0).length;
  const s = seg.segmentation || {};

  const content = `
    ${cards([
      { icon: "👥", label: "Mijozlar", value: fmtNum(customers.length) },
      { icon: "🔴", label: "Qarzdorlar", value: fmtNum(debtors) },
      { icon: "💰", label: "Umumiy qarz", value: fmtMoney(totalDebt) },
    ])}
    ${panel("🏅 Mijoz triaji (segmentatsiya)", `
      <div class="btn-row" style="gap:8px">
        <span>🏅 Oltin: <b>${fmtNum(s.gold || 0)}</b></span>
        <span>🥈 Kumush: <b>${fmtNum(s.silver || 0)}</b></span>
        <span>🥉 Bronza: <b>${fmtNum(s.bronze || 0)}</b></span>
      </div>`)}
    ${panel("Mijozlar ro'yxati", customers.length ? `
      <table>
        <thead><tr><th>Ism</th><th>Telefon</th><th>Kompaniya</th><th>Kredit limiti</th><th>Qarz</th><th>Xarid</th><th>Ballar</th><th>Toifa</th><th>Holat</th><th></th></tr></thead>
        <tbody>
        ${customers.map((c) => `
          <tr>
            <td>${esc(c.name)}</td><td>${esc(c.phone || "-")}</td><td>${esc(c.company || "-")}</td>
            <td>${fmtMoney(c.credit_limit)}</td>              <td>${Number(c.total_debt) > 0 ? `<b style="color:var(--danger)">${fmtMoney(c.total_debt)}</b>` : fmtMoney(0)}</td>
            <td>${fmtMoney(c.total_purchases)}</td><td>${fmtNum(c.loyalty_points)}</td>
            <td>${tierBadge(c.tier)}</td>
            <td>${c.status === "bloklangan" ? badge("Bloklangan", "red") : c.status === "vip" ? badge("VIP", "purple") : badge("Faol", "green")}</td>
            <td><div class="btn-row">
              ${(canEditModule("crm") || canEditModule("finance")) && Number(c.total_debt) > 0 ? `<button class="btn btn-success btn-sm" data-pay-customer="${c.id}" data-name="${esc(c.name)}">🧾 Qarz</button>` : ""}
              <button class="btn btn-outline btn-sm" data-view-customer="${c.id}">Karta</button>
            </div></td>
          </tr>`).join("")}
        </tbody>
      </table>` : empty("Mijozlar yo'q"))}
  `;
  return content;
}

async function renderSuppliers() {
  const [s, sugg] = await Promise.all([
    apiGet("/suppliers").catch(() => ({ suppliers: [] })),
    apiGet("/suppliers/reorder-suggestions").catch(() => ({ suggestions: [] })),
  ]);
  const suppliers = s.suppliers || [];
  const suggestions = sugg.suggestions || [];

  const content = `
    ${panel("🚚 Yetkazib beruvchilar", suppliers.length ? `
      <table>
        <thead><tr><th>Nomi</th><th>Telefon</th><th>Aloqa</th><th>Reyting</th><th>O'z vaqtida</th><th>Kechikkan</th><th>Qarz</th></tr></thead>
        <tbody>
        ${suppliers.map((sup) => `
          <tr>
            <td>${esc(sup.name)}</td><td>${esc(sup.phone || "-")}</td><td>${esc(sup.contact_person || "-")}</td>
            <td>${"⭐".repeat(Math.max(1, Math.round(Number(sup.rating || 5))))}</td>
            <td>${fmtNum(sup.on_time_count)}</td><td>${fmtNum(sup.late_count)}</td>
            <td>${fmtMoney(sup.total_debt)}</td>
          </tr>`).join("")}
        </tbody>
      </table>` : empty("Yetkazib beruvchilar yo'q"))}
    ${panel("🛒 Avtomatik qayta buyurtma tavsiyalari", suggestions.length ? `
      <table>
        <thead><tr><th>Xom ashyo</th><th>Qoldiq</th><th>Min.</th><th>Tavsiya</th><th>Yetkazib beruvchi</th></tr></thead>
        <tbody>
        ${suggestions.map((sg) => `
          <tr><td>${esc(sg.raw_material_name)}</td><td>${fmtNum(sg.current_stock)} ${esc(sg.unit)}</td>
          <td>${fmtNum(sg.min_stock)}</td><td><b>${fmtNum(sg.suggested_order)}</b></td>
          <td>${esc(sg.supplier_name)}</td></tr>`).join("")}
        </tbody>
      </table>` : empty("Hammasi yetarli — tavsiya yo'q ✅"))}
  `;
  return content;
}

async function renderReceipts() {
  const data = await apiGet("/receipts").catch(() => ({ receipts: [] }));
  const receipts = data.receipts || [];
  const content = panel("📦 Qabul qilish aktlari (sifat nazorati)", receipts.length ? `
    <table>
      <thead><tr><th>Akt</th><th>Yetkazib beruvchi</th><th>Xom ashyo</th><th>Buyurtma</th><th>Qabul</th><th>Sifat</th><th>Kamomad</th><th>Sana</th></tr></thead>
      <tbody>
      ${receipts.map((r) => `
        <tr>
          <td class="mono">${esc(r.act_number)}</td><td>${esc(r.supplier_name)}</td><td>${esc(r.material_name)}</td>
          <td>${fmtNum(r.quantity_ordered)}</td><td>${fmtNum(r.quantity_received)}</td>
          <td>${r.quality_status === "qabul_qilingan" ? badge("Qabul", "green") : r.quality_status === "qisman" ? badge("Qisman", "yellow") : badge("Rad", "red")}</td>
          <td>${fmtMoney(r.deficiency_amount)}</td><td>${fmtDate(r.created_at)}</td>
        </tr>`).join("")}
      </tbody>
    </table>` : empty("Qabul aktlari yo'q"));
  return content;
}

async function renderReservations() {
  const data = await apiGet("/reservations").catch(() => ({ reservations: [] }));
  const reservations = data.reservations || [];
  const active = reservations.filter((r) => r.status === "faol").length;
  const content = `
    ${cards([
      { icon: "🔒", label: "Jami", value: fmtNum(reservations.length) },
      { icon: "🟢", label: "Faol", value: fmtNum(active) },
    ])}
    ${panel("Rezervatsiyalar", reservations.length ? `
      <table>
        <thead><tr><th>Kod</th><th>Mahsulot</th><th>Miqdor</th><th>Mijoz</th><th>Tugaydi</th><th>Holat</th><th></th></tr></thead>
        <tbody>
        ${reservations.map((r) => `
          <tr>
            <td class="mono">${esc(r.reservation_code)}</td><td>${esc(r.product_name)}</td><td>${fmtNum(r.quantity)}</td>
            <td>${esc(r.customer_name || "-")}</td><td>${fmtDate(r.expires_at)}</td>
            <td>${r.status === "faol" ? badge("Faol", "green") : r.status === "yechilgan" ? badge("Avto-yechilgan", "gray") : badge(r.status, "blue")}</td>
            <td>${r.status === "faol" ? `<div class="btn-row">
              <button class="btn btn-success btn-sm" data-complete-rsv="${r.id}">✅</button>
              <button class="btn btn-danger btn-sm" data-cancel-rsv="${r.id}">✕</button>
            </div>` : ""}</td>
          </tr>`).join("")}
        </tbody>
      </table>` : empty("Rezervatsiyalar yo'q"))}
  `;
  return content;
}

async function renderTransfers() {
  const data = await apiGet("/transfers").catch(() => ({ transfers: [] }));
  const transfers = data.transfers || [];
  const content = panel("🔄 Omborlararo ko'chirishlar", transfers.length ? `
    <table>
      <thead><tr><th>Sana</th><th>Narsa</th><th>Miqdor</th><th>Manba</th><th>Maqsad</th><th>Foydalanuvchi</th></tr></thead>
      <tbody>
      ${transfers.map((t) => `
        <tr><td>${fmtDate(t.created_at)}</td><td>${esc(t.name)}</td><td>${fmtNum(t.quantity)}</td>
        <td>${badge(t.source || "-", "yellow")}</td><td>${badge(t.target || "-", "blue")}</td>
        <td>${esc(t.user_name || "-")}</td></tr>`).join("")}
      </tbody>
    </table>` : empty("Ko'chirishlar yo'q"));
  return content;
}

async function renderInventory() {
  const data = await apiGet("/inventory-checks").catch(() => ({ checks: [] }));
  const checks = data.checks || [];
  const shortages = checks.filter((c) => c.difference < 0).length;
  const content = `
    ${cards([
      { icon: "📋", label: "Tekshiruvlar", value: fmtNum(checks.length) },
      { icon: "⚠️", label: "Yetishmovchilik", value: fmtNum(shortages), note: "dalolatnoma tayyorlanadi" },
    ])}
    ${panel("Inventarizatsiya varaqalari", checks.length ? `
      <table>
        <thead><tr><th>Raqam</th><th>Narsa</th><th>Tizimda</th><th>Haqiqiy</th><th>Farq</th><th>Dalolatnoma</th></tr></thead>
        <tbody>
        ${checks.map((c) => `
          <tr>
            <td class="mono">${esc(c.check_number)}</td><td>${esc(c.name)}</td>
            <td>${fmtNum(c.system_quantity)}</td><td>${fmtNum(c.actual_quantity)}</td>
            <td>${Number(c.difference) < 0 ? `<b style="color:var(--danger)">${fmtNum(c.difference)}</b>` : `<b style="color:var(--success)">+${fmtNum(c.difference)}</b>`}</td>
            <td>${c.act_created ? badge("Tayyor", "yellow") : badge("Yo'q", "gray")}</td>
          </tr>`).join("")}
        </tbody>
      </table>` : empty("Inventarizatsiya o'tkazilmagan"))}
  `;
  return content;
}

async function renderFinance() {
  const [pl, debts, tax] = await Promise.all([
    apiGet("/finance/pl").catch(() => ({ report: {} })),
    apiGet("/finance/debts").catch(() => ({})),
    apiGet("/finance/tax?start=&end=&amount=0").catch(() => ({ tax: {} })),
  ]);
  const report = pl.report || {};
  const taxInfo = tax.tax || {};
  const creditSales = debts.credit_sales || [];
  const totalRemaining = creditSales.reduce((s, x) => s + Number(x.remaining || 0), 0);

  const content = `
    ${cards([
      { icon: "📈", label: "Daromad (oy)", value: fmtMoney(report.revenue) },
      { icon: "💎", label: "Sof foyda", value: fmtMoney(report.net_profit), note: `marja ${report.profit_margin || 0}%` },
      { icon: "📝", label: "Qarzdorlar", value: fmtNum(debts.debtor_count || 0) },
      { icon: "🔴", label: "Kechiktirilgan", value: fmtNum(debts.overdue_count || 0) },
    ])}
    <div class="row">
      ${panel("💎 P&L (bu oy)", `
        <table>
          <tr><td>Daromad</td><td>${fmtMoney(report.revenue)}</td></tr>
          <tr><td>Chegirma</td><td>${fmtMoney(report.discounts)}</td></tr>
          <tr><td>COGS</td><td>${fmtMoney(report.cogs)}</td></tr>
          <tr><td>Xarajat</td><td>${fmtMoney(report.total_expenses)}</td></tr>
          <tr><td><b>Sof foyda</b></td><td><b>${fmtMoney(report.net_profit)}</b></td></tr>
        </table>`) }
      ${panel("🧾 Soliq hisobi", `
        <table>
          <tr><td>Aylanma</td><td>${fmtMoney(report.revenue)}</td></tr>
          <tr><td>QQS 12%</td><td>${fmtMoney(taxInfo.qqs)}</td></tr>
          <tr><td>Soliqsiz</td><td>${fmtMoney(taxInfo.net)}</td></tr>
        </table>`)}
    </div>
    ${panel(`📝 Nasiya qarzlari — jami qoldiq: ${fmtMoney(totalRemaining)}`, creditSales.length ? `
      <table>
        <thead><tr><th>Invoice</th><th>Mijoz</th><th>Summa</th><th>To'langan</th><th>Qoldiq</th><th>Muddat</th><th>Holat</th></tr></thead>
        <tbody>
        ${creditSales.map((x) => `
          <tr>
            <td class="mono">${esc(x.invoice_number)}</td><td>${esc(x.customer_name || "-")}</td>
            <td>${fmtMoney(x.total_amount)}</td><td>${fmtMoney(x.paid_amount)}</td>
            <td><b>${fmtMoney(x.remaining)}</b></td><td>${fmtDate(x.due_date)}</td>
            <td>${x.credit_status === "toliq_tolangan" ? badge("To'langan", "green") : x.credit_status === "muddati_otgan" ? badge("Muddati o'tgan", "red") : badge("Qarzdor", "yellow")}</td>
          </tr>`).join("")}
        </tbody>
      </table>` : empty("Nasiya sotuvlari yo'q"))}
  `;
  return content;
}

async function renderRoles() {
  const [data, resets] = await Promise.all([
    apiGet("/roles").catch(() => ({ roles: [] })),
    apiGet("/password-reset/requests").catch(() => ({ requests: [] })),
  ]);
  const roles = data.roles || [];
  const resetRequests = resets.requests || [];
  const roleNames = { direktor: "👑 Direktor", sotuvchi: "🛒 Sotuvchi", kassir: "💵 Kassir",
    omborchi: "📦 Omborchi", haydovchi: "🚚 Haydovchi", buxgalter: "🧮 Buxgalter", ishchi: "🔧 Ishchi" };
  const canManage = canEditModule("admin");
  const statusBadge = (s) => ({
    pending: badge("Kutilmoqda", "yellow"),
    approved: badge("Tasdiqlangan", "blue"),
    rejected: badge("Rad etilgan", "red"),
    done: badge("Bajarilgan", "green"),
  }[s] || badge(s, "gray"));
  const pending = resetRequests.filter((x) => x.status === "pending");
  const content = `
    ${canManage && pending.length ? panel("🔑 Parol tiklash so'rovlari (yangi)", `
      <table>
        <thead><tr><th>Xodim</th><th>Telefon</th><th>Sabab</th><th>Vaqt</th><th></th></tr></thead>
        <tbody>
        ${pending.map((r) => `
          <tr>
            <td>${esc(r.full_name)}</td><td>${esc(r.phone_number)}</td>
            <td>${esc(r.reason || "-")}</td><td>${fmtDate(r.requested_at)}</td>
            <td style="white-space:nowrap">
              <button class="btn btn-success btn-sm" data-approve-reset="${r.id}" data-name="${esc(r.full_name)}">✅ Tasdiqlash</button>
              <button class="btn btn-outline btn-sm" data-reject-reset="${r.id}">✖ Rad etish</button>
            </td>
          </tr>`).join("")}
        </tbody>
      </table>`) : ""}
    ${panel("🔐 Xodimlar, rollar va web parollar", roles.length ? `
    <table>
      <thead><tr><th>Ism</th><th>Telefon</th><th>Rol</th><th>Admin</th><th>Web parol</th>${canManage ? "<th></th>" : ""}</tr></thead>
      <tbody>
      ${roles.map((r) => `
        <tr><td>${esc(r.full_name)}</td><td>${esc(r.phone_number || "-")}</td>
        <td>${badge(roleNames[r.role] || r.role || "ishchi", r.role === "direktor" ? "purple" : "blue")}</td>
        <td>${r.is_admin ? badge("Ha", "green") : badge("Yo'q", "gray")}</td>
        <td>${r.has_password ? badge("O'rnatilgan", "green") : badge("Yo'q", "red")}</td>
        ${canManage ? `<td><button class="btn btn-outline btn-sm" data-set-password="${r.id}" data-name="${esc(r.full_name)}">🔑 Parol</button></td>` : ""}
      </tr>`).join("")}
      </tbody>
    </table>
    <p class="muted">💡 Web parol — dashboardga kirish uchun. Rollar bot orqali boshqariladi.</p>`
    : empty("Xodimlar yo'q"))}
    ${canManage && resetRequests.length ? panel("🗂 Parol tiklash tarixi", `
      <table>
        <thead><tr><th>Xodim</th><th>Telefon</th><th>Holat</th><th>So'ralgan</th></tr></thead>
        <tbody>
        ${resetRequests.slice(0, 10).map((r) => `
          <tr><td>${esc(r.full_name)}</td><td>${esc(r.phone_number)}</td>
          <td>${statusBadge(r.status)}</td><td>${fmtDate(r.requested_at)}</td></tr>`).join("")}         </tbody>
       </table>`) : ""}
   `;
   return content;
}


async function renderBackup() {
  const data = await apiGet("/backups").catch(() => ({ backups: [], settings: {} }));
  const files = data.backups || [];
  const settings = data.settings || {};
  const canManage = canEditModule("admin");
  const targetNames = { telegram: "Telegram", s3: "S3" };
  const uploadTargets = settings.upload_targets || [];
  const uploadVal = uploadTargets.length
    ? uploadTargets.map((t) => (targetNames[t] || t) + (t === "s3" && settings.s3_bucket ? ` (${settings.s3_bucket})` : "")).join(" + ")
    : "O'chiq";
  const uploadNote = uploadTargets.length
    ? (settings.encryption_enabled ? "🔐 shifrlangan holda" : "🔓 shifrlanmagan — BACKUP_ENCRYPTION_PASSWORD o'rnating")
    : "BACKUP_UPLOAD=telegram,s3 sozlang";
  const sched = settings.schedule === "weekly" ? "Dushanba" : settings.schedule === "monthly" ? "Oy 1-kuni" : "Har kuni";
  const table = files.length ? `
      <table>
        <thead><tr><th>Fayl</th><th>Hajmi</th><th>Yaratilgan</th>${canManage ? "<th></th>" : ""}</tr></thead>
        <tbody>
        ${files.map((f) => `
          <tr>
            <td class="mono">${esc(f.filename)}</td>
            <td>${fmtMb(f.size_mb)} MB <span class="muted">(${fmtNum(f.size_bytes)} B)</span></td>
            <td>${fmtDate(f.created_at)}</td>
            ${canManage ? `<td><button class="btn btn-danger btn-sm" data-restore-file="${esc(f.filename)}">♻️ Tiklash</button></td>` : ""}
          </tr>`).join("")}
        </tbody>
      </table>` : empty("Hozircha backup yo'q — «Backup olish» tugmasini bosing");
  const note = `
    <p class="muted" style="padding:4px 0 0 2px">
      ⚙️ Rejali backup: ${esc(sched)} soat ${esc(settings.time || "02:00")} da · ${fmtNum(settings.keep_days || 30)} kun saqlanadi
      ${uploadTargets.length && settings.remote_keep_days ? ` · ☁️ uzoq joyda ${fmtNum(settings.remote_keep_days)} kun saqlanadi` : ""}
      ${settings.enabled === false ? " · <b style='color:var(--danger)'>O'chirilgan (BACKUP_ENABLED=false)</b>" : ""}
    </p>`;
  const uploadLogs = data.upload_logs || [];
  const srcLabels = { scheduled: "Rejali", manual_bot: "Bot", web: "Web" };
  const uploadRows = uploadLogs.length ? `
      <table>
        <thead><tr><th>Vaqt</th><th>Manba</th><th>Fayl</th><th>Telegram</th><th>S3</th><th>Izoh</th></tr></thead>
        <tbody>
        ${uploadLogs.map((lg) => {
          const up = lg.uploads || {};
          const cell = (t) => {
            const s = up[t];
            if (!s) return `<span class="muted">—</span>`;
            if (s.status === "ok") return `<span class="badge badge-green">✅ Yuklandi</span>`;
            const err = s.error ? ` — ${esc(s.error)}` : "";
            return `<span class="badge badge-red">❌ Yuklanmadi</span><div class="muted" style="font-size:11px">${err}</div>`;
          };
          const okCount = Object.values(up).filter((s) => s && s.status === "ok").length;
          const notes = [];
          if (lg.encrypted) notes.push("🔐 shifrlangan");
          if (lg.created === false) notes.push("⚠️ backup olinmadi");
          if (okCount && lg.uploads && okCount < Object.keys(lg.uploads).length) notes.push("qisman");
          return `<tr>
            <td>${fmtDate(lg.created_at)}</td>
            <td>${srcLabels[lg.source] || esc(lg.source || "")}</td>
            <td class="mono">${esc(lg.filename || "—")}</td>
            <td>${cell("telegram")}</td>
            <td>${cell("s3")}</td>
            <td class="muted">${notes.length ? notes.join(" · ") : ""}</td>
          </tr>`;
        }).join("")}
        </tbody>
      </table>` : empty("Hozircha yuklash qaydlari yo'q — backup olinganda Telegram/S3 holati shu yerda ko'rinadi");
  const s3data = await apiGet("/backups/s3").catch(() => ({ enabled: false, objects: [] }));
  const s3objs = s3data.objects || [];
  const s3Rows = s3data.enabled
    ? (s3objs.length ? `
      <table>
        <thead><tr><th>Ob'ekt</th><th>Hajmi</th><th>Yaratilgan</th>${canManage ? "<th></th>" : ""}</tr></thead>
        <tbody>
        ${s3objs.map((o) => `
          <tr>
            <td class="mono">${esc(o.name)}${o.encrypted ? " <span class=\"badge badge-purple\">🔐 shifrlangan</span>" : ""}</td>
            <td>${fmtMb(o.size_mb)} MB</td>
            <td>${esc((o.last_modified || "").slice(0, 16).replace("T", " "))}</td>
            ${canManage ? `<td><button class="btn btn-danger btn-sm" data-s3-restore="${esc(btoa(unescape(encodeURIComponent(o.key))))}" data-s3-name="${esc(o.name)}">♻️ Tiklash</button></td>` : ""}
          </tr>`).join("")}
        </tbody>
      </table>` : empty("S3 bucket'da backup ob'ekti yo'q"))
    : empty("S3 yoqilmagan — BACKUP_UPLOAD=s3 va BACKUP_S3_* sozlang");

  const content = `
    ${cards([
      { icon: "🗄️", label: "Backup nusxalar", value: fmtNum(data.count || 0) },
      { icon: "📦", label: "Jami hajm", value: fmtMb(data.total_size_mb) + " MB" },
      { icon: "☁️", label: "Uzoq joyga yuklash", value: uploadVal, note: uploadNote },
    ])}
    ${panel("💾 Zaxira nusxalar (tarix va hajmlar)", table + note,
      canManage ? `<button class="btn btn-primary" data-backup-now="1">💾 Backup olish</button>` : "")}
    ${panel("☁️ Bulutdagi nusxalar (S3)", s3Rows)}
    ${panel("☁️ Yuklash holati (SystemLog)", uploadRows)}
  `;
  return content;
}

/* ---------- Operations module (TZ: yoqilg'i / avans / yig'ish / xavfsizlik / reyting) ---------- */

async function renderFuel() {
  const [logs, eff] = await Promise.all([
    apiGet("/fuel/logs?limit=50").catch(() => []),
    apiGet("/fuel/efficiency?days=30").catch(() => ({})),
  ]);
  const canEdit = canEditModule("fuel");
  const effLines = [
    `Quyishlar: <b>${fmtNum(eff.logs_count)}</b>`,
    `Jami yoqilg'i: <b>${fmtNum(eff.total_liters)} L</b>`,
    `Jami xarajat: <b>${fmtMoney(eff.total_cost)}</b>`,
  ];
  if (eff.avg_liters_per_100km != null) {
    effLines.push(`O'rtacha sarf: <b>${fmtNum(eff.avg_liters_per_100km)} L/100km</b>` +
      ` (me'yor: ${fmtNum(eff.norm_liters_per_100km)})`);
    effLines.push(eff.over_norm
      ? badge(`Me'yordan ${fmtNum(eff.over_norm_pct)}% oshgan`, "red")
      : badge("Me'yor doirasida", "green"));
  } else {
    effLines.push(badge("Samaradorlik uchun spidometr kerak", "gray"));
  }
  const table = logs.length ? `
    <table>
      <thead><tr><th>Sana</th><th>Haydovchi</th><th>Mashina</th><th>Litr</th><th>Narx/L</th><th>Jami</th><th>Spidometr</th><th>Izoh</th></tr></thead>
      <tbody>
      ${logs.map((l) => `
        <tr>
          <td>${fmtDate(l.created_at)}</td>
          <td>${esc(l.driver_name || "-")}</td>
          <td>${esc(l.vehicle || "-")}</td>
          <td>${fmtNum(l.liters)} L</td>
          <td>${l.price_per_liter ? fmtMoney(l.price_per_liter) : "-"}</td>
          <td>${fmtMoney(l.total_cost)}</td>
          <td>${l.odometer_km != null ? fmtNum(l.odometer_km) + " km" : "-"}</td>
          <td>${esc(l.note || "")}</td>
        </tr>`).join("")}
      </tbody>
    </table>` : empty("Yoqilg'i qaydlari yo'q");
  return `
    ${cards([
      { icon: "⛽", label: "30 kunlik sarf", value: fmtNum(eff.avg_liters_per_100km ?? 0) + " L/100km" },
      { icon: "⛽", label: "Jami quyilgan (30 kun)", value: fmtNum(eff.total_liters) + " L" },
      { icon: "💰", label: "Jami xarajat (30 kun)", value: fmtMoney(eff.total_cost) },
    ])}
    ${panel("⛽ Samaradorlik (30 kun)", `<div class="row">${effLines.map((l) => `<span>${l}</span>`).join("")}</div>`)}
    ${panel("⛽ Quyish tarixi", table, canEdit ? `<button class="btn btn-primary btn-sm" data-add-fuel="1">➕ Yangi quyish</button>` : "")}
  `;
}

async function renderExpenses() {
  const [reports, totals] = await Promise.all([
    apiGet("/expenses?limit=100").catch(() => []),
    apiGet("/expenses/totals?days=30").catch(() => ({})),
  ]);
  const canEdit = canEditModule("expenses");
  const canReview = canEditModule("finance");
  const statusBadge = (s) =>
    s === "tasdiqlangan" ? badge("✅ Tasdiqlangan", "green") :
    s === "rad_etilgan" ? badge("❌ Rad etilgan", "red") : badge("⏳ Kutilmoqda", "yellow");
  const rows = reports.length ? reports.map((r) => `
    <tr>
      <td class="mono">${esc(r.report_number)}</td>
      <td>${esc(r.employee_name || "-")}</td>
      <td>${esc(r.category)}</td>
      <td>${fmtMoney(r.amount)}</td>
      <td>${esc(r.description || "-")}</td>
      <td>${statusBadge(r.status)}</td>
      <td>${fmtDate(r.created_at)}</td>
      <td>${canReview && r.status === "kutilmoqda" ? `
        <div class="btn-row">
          <button class="btn btn-success btn-sm" data-expense-review="${r.id}" data-status="tasdiqlangan">✅ Tasdiqlash</button>
          <button class="btn btn-danger btn-sm" data-expense-review="${r.id}" data-status="rad_etilgan">❌ Rad etish</button>
        </div>` : "-"}</td>
    </tr>`).join("") : "";
  return `
    ${cards([
      { icon: "✅", label: "Tasdiqlangan (30 kun)", value: fmtMoney(totals.approved_total) },
      { icon: "⏳", label: "Kutilayotgan", value: fmtNum((reports || []).filter((r) => r.status === "kutilmoqda").length) },
      { icon: "📑", label: "Jami hisobotlar", value: fmtNum(reports.length) },
    ])}
    ${panel("🧾 Avans hisobotlari (xodim xarajatlari)",
      reports.length ? `<table><thead><tr><th>Raqam</th><th>Xodim</th><th>Tur</th><th>Summa</th><th>Izoh</th><th>Holat</th><th>Sana</th><th>Harakat</th></tr></thead><tbody>${rows}</tbody></table>` : empty("Avans hisobotlari yo'q"),
      canEdit ? `<button class="btn btn-primary btn-sm" data-add-expense="1">➕ Yangi xarajat</button>` : "")}
  `;
}

async function renderPicking() {
  const items = await apiGet("/picking?limit=100").catch(() => []);
  const canEdit = canEditModule("picking");
  const statusBadge = (s) =>
    s === "tayyor" ? badge("✅ Tayyor", "green") :
    s === "yuborilgan" ? badge("🚚 Yuborilgan", "blue") : badge("🆕 Yangi", "yellow");
  const rows = items.length ? items.map((p) => `
    <tr>
      <td class="mono">${esc(p.picking_number)}</td>
      <td>${esc(p.product_name || "-")}</td>
      <td>${fmtNum(p.quantity)} ${esc(p.unit || "")}</td>
      <td>${esc(p.sector || "-")}</td>
      <td>${statusBadge(p.status)}</td>
      <td>${esc(p.picked_by || "-")}</td>
      <td>${fmtDate(p.created_at)}</td>
      <td>${canEdit && p.status === "yangi" ? `
        <button class="btn btn-success btn-sm" data-picking-done="${p.id}">✅ Tayyor</button>` : "-"}</td>
    </tr>`).join("") : "";
  return `
    ${cards([{ icon: "📦", label: "Yig'ish varaqalari", value: fmtNum(items.length) }])}
    ${panel("📦 Yig'ish varaqalari (picking list)",
      items.length ? `<table><thead><tr><th>Raqam</th><th>Mahsulot</th><th>Miqdor</th><th>Sektor</th><th>Holat</th><th>Yig'uvchi</th><th>Sana</th><th>Harakat</th></tr></thead><tbody>${rows}</tbody></table>` : empty("Yig'ish varaqalari yo'q"))}
  `;
}

async function renderSecurity() {
  const alerts = await apiGet("/security/alerts?limit=100").catch(() => []);
  const canEdit = canEditModule("security");
  const sevBadge = (s) =>
    s === "high" ? badge("🔴 Yuqori", "red") :
    s === "medium" ? badge("🟠 O'rtacha", "yellow") : badge("🟡 Past", "gray");
  const statusBadge = (s) =>
    s === "hal_qilingan" ? badge("✅ Hal qilingan", "green") :
    s === "ko'rib_chiqilgan" ? badge("👀 Ko'rib chiqilgan", "blue") : badge("🆕 Yangi", "red");
  const rows = alerts.length ? alerts.map((a) => `
    <tr>
      <td>${sevBadge(a.severity)}</td>
      <td class="mono">${esc(a.activity_type)}</td>
      <td>${esc(a.description || "-")}</td>
      <td>${esc(a.user_name || "-")}</td>
      <td>${statusBadge(a.status)}</td>
      <td>${fmtDate(a.created_at)}</td>
      <td>${canEdit && a.status !== "hal_qilingan" ? `
        <button class="btn btn-success btn-sm" data-security-done="${a.id}">✅ Hal qilindi</button>` : "-"}</td>
    </tr>`).join("") : "";
  const twoFaEnabled = !!(ME && ME.two_fa_enabled);
  const twoFaPanel = panel("🔢 2FA (Google Authenticator)", `
    <div class="row">
      <span>Holat: ${twoFaEnabled ? badge("✅ Yoqilgan", "green") : badge("O'chirilgan", "gray")}</span>
      <span class="muted" style="font-size:0.9em">Parol bilan birga 6 xonali kod talab qilinadi — direktor va kassir uchun tavsiya etiladi.</span>
    </div>
    <div class="btn-row" style="margin-top:10px">
      ${twoFaEnabled
        ? `<button class="btn btn-outline btn-sm" data-2fa-disable="1">❌ 2FA o'chirish</button>`
        : `<button class="btn btn-primary btn-sm" data-2fa-enable="1">🔢 2FA yoqish</button>`}
    </div>`);
  return `
    ${cards([{ icon: "🚨", label: "Shubhali harakatlar", value: fmtNum(alerts.length) }])}
    ${twoFaPanel}
    ${panel("🚨 Shubhali harakat detektori",
      alerts.length ? `<table><thead><tr><th>Daraja</th><th>Tur</th><th>Tavsif</th><th>Foydalanuvchi</th><th>Holat</th><th>Sana</th><th>Harakat</th></tr></thead><tbody>${rows}</tbody></table>` : empty("Shubhali harakatlar yo'q — hammasi tinch ✅"))}
  `;
}

async function renderRatings() {
  const ratings = await apiGet("/sellers/ratings?days=30&limit=20").catch(() => []);
  const medals = { 1: "🥇", 2: "🥈", 3: "🥉" };
  const rows = ratings.length ? ratings.map((r) => `
    <tr>
      <td>${medals[r.rank] || `${r.rank}.`}</td>
      <td><b>${esc(r.seller)}</b></td>
      <td>${fmtMoney(r.total_sales)}</td>
      <td>${fmtNum(r.sales_count)}</td>
      <td>${fmtMoney(r.avg_check)}</td>
    </tr>`).join("") : "";
  return `
    ${cards([{ icon: "🏆", label: "Sotuvchilar (30 kun)", value: fmtNum(ratings.length) }])}
    ${panel("🏆 Sotuvchilar reytingi (30 kun)",
      ratings.length ? `<table><thead><tr><th>O'rin</th><th>Sotuvchi</th><th>Jami savdo</th><th>Sotuvlar</th><th>O'rtacha chek</th></tr></thead><tbody>${rows}</tbody></table>` : empty("Hozircha savdo qaydlari yo'q"))}
  `;
}

const RENDERERS = {
  overview: renderOverview, warehouse: renderWarehouse, products: renderProducts,
  customers: renderCustomers, suppliers: renderSuppliers, receipts: renderReceipts,
  reservations: renderReservations, transfers: renderTransfers, inventory: renderInventory,
  finance: renderFinance, roles: renderRoles, backup: renderBackup,
  fuel: renderFuel, expenses: renderExpenses, picking: renderPicking,
  security: renderSecurity, ratings: renderRatings,
};

/* ---------- Routing ---------- */
async function navigate(page) {
  const allowed = allowedPages();
  if (!allowed.includes(page)) page = allowed[0] || "";
  if (!page || !ME) {
    showLogin();
    return;
  }
  state.page = page;
  document.querySelectorAll(".nav-item[data-page]").forEach((b) =>
    b.classList.toggle("active", b.dataset.page === page));
  $("#page-title").textContent = PAGES[page] || page;
  $("#content").innerHTML = `<div class="loading">Yuklanmoqda…</div>`;
  try {
    const renderer = RENDERERS[page];
    if (!renderer) throw new Error("Noma'lum sahifa");
    $("#content").innerHTML = await renderer();
    bindContentEvents();
  } catch (e) {
    console.error(e);
    $("#content").innerHTML = panel("⚠️ Xatolik", `
      <div style="padding:12px">
        <p>Ma'lumotlarni yuklab bo'lmadi.</p>
        <p class="muted">${esc(e.message)}</p>
        <p style="margin-top:10px">💡 Python backend ishlayotganini tekshiring: <code>uvicorn dashboard.app:app --port 8000</code></p>
      </div>`);
  }
}

/* ---------- Modal forms ---------- */
function bindContentEvents() {
  document.querySelectorAll("[data-go]").forEach((b) =>
    b.addEventListener("click", () => navigate(b.dataset.go)));

  // 2FA (Google Authenticator) boshqaruv
  document.querySelectorAll("[data-2fa-enable]").forEach((b) =>
    b.addEventListener("click", () => open2faSetupModal()));
  document.querySelectorAll("[data-2fa-disable]").forEach((b) =>
    b.addEventListener("click", () => open2faDisableModal()));

  // Qarz to'lash
  document.querySelectorAll("[data-pay-customer]").forEach((b) =>
    b.addEventListener("click", () => openPayModal(b.dataset.payCustomer, b.dataset.name)));

  // Mijoz kartasi
  document.querySelectorAll("[data-view-customer]").forEach((b) =>
    b.addEventListener("click", async () => {
      try {
        const data = await apiGet(`/customers/${b.dataset.viewCustomer}`);
        const c = data.customer || {};
        const sales = data.sales || [];
        const payments = data.payments || [];
        openModal(`👤 ${c.name} — karta`, `
          <div class="form-group">
            <table>
              <tr><td>Toifa</td><td>${tierBadge(c.tier)}</td></tr>
              <tr><td>Telefon</td><td>${esc(c.phone || "-")}</td></tr>
              <tr><td>Kompaniya</td><td>${esc(c.company || "-")}</td></tr>
              <tr><td>Kredit limiti</td><td>${fmtMoney(c.credit_limit)}</td></tr>
              <tr><td>Joriy qarz</td><td>${fmtMoney(c.total_debt)}</td></tr>
              <tr><td>Jami xarid</td><td>${fmtMoney(c.total_purchases)}</td></tr>
              <tr><td>Ballar</td><td>${fmtNum(c.loyalty_points)}</td></tr>
            </table>
            <h4 style="margin-top:10px">📋 Oxirgi sotuvlar</h4>
            ${sales.length ? `<table><tbody>${sales.map((s) => `<tr><td class="mono">${esc(s.invoice_number)}</td><td>${fmtMoney(s.total_amount)}</td><td>${s.is_credit ? badge("Nasiya", "yellow") : badge(s.payment_method === "mixed" ? "Aralash" : s.payment_method, "blue")}</td><td>${fmtDate(s.sale_date)}</td></tr>`).join("")}</tbody></table>` : "Yo'q"}
            <h4 style="margin-top:10px">💳 To'lovlar</h4>
            ${payments.length ? `<table><tbody>${payments.map((p) => `<tr><td>${fmtMoney(p.amount)}</td><td>${esc(p.method)}</td><td>${esc(p.payment_type)}</td><td>${fmtDate(p.created_at)}</td></tr>`).join("")}</tbody></table>` : "Yo'q"}
          </div>
          <div class="form-actions"><button class="btn btn-outline" onclick="closeModal()">Yopish</button></div>`);
      } catch (e) { toast(e.message, "error"); }
    }));

  document.querySelectorAll("[data-complete-rsv]").forEach((b) =>
    b.addEventListener("click", async () => {
      await apiPost(`/reservations/${b.dataset.completeRsv}/complete`, {});
      toast("✅ Rezervatsiya yakunlandi"); navigate("reservations");
    }));
  document.querySelectorAll("[data-cancel-rsv]").forEach((b) =>
    b.addEventListener("click", async () => {
      await apiPost(`/reservations/${b.dataset.cancelRsv}/cancel`, {});
      toast("Rezervatsiya bekor qilindi"); navigate("reservations");
    }));

  // Xodimga web parol o'rnatish (admin)
  document.querySelectorAll("[data-set-password]").forEach((b) =>
    b.addEventListener("click", async () => {
      const pwd = prompt(`🔑 ${b.dataset.name} uchun yangi parol (kamida 8 belgi):`);
      if (!pwd) return;
      try {
        const r = await apiPost(`/roles/${b.dataset.setPassword}/password`, { password: pwd });
        if (r.error) throw new Error(r.error);
        toast(`✅ ${b.dataset.name} uchun parol o'rnatildi`);
        navigate("roles");
      } catch (e) { toast(e.message, "error"); }
    }));

  // Parol tiklash so'rovini tasdiqlash (admin) — kod ko'rsatiladi
  document.querySelectorAll("[data-approve-reset]").forEach((b) =>
    b.addEventListener("click", async () => {
      try {
        const r = await apiPost(`/password-reset/${b.dataset.approveReset}/approve`, {});
        if (r.error) throw new Error(r.error);
        openModal(`✅ Tasdiqlandi — ${b.dataset.name}`, `
          <p>Xodimga quyidagi <b>bir martalik kod</b>ni yetkazing (kod ${r.expires_in_hours || 2} soat amal qiladi):</p>
          <div style="font-size:1.6em; font-weight:bold; letter-spacing:4px; text-align:center; background:#f0f4ff; border-radius:8px; padding:16px; margin:14px 0; font-family:monospace">${esc(r.reset_code)}</div>
          <p class="muted" style="font-size:0.9em">Xodim: Login ekranida «Parolni unutdingizmi?» → kodni kiritib yangi parol o'rnatadi.</p>
          <div class="form-actions"><button class="btn btn-primary" onclick="closeModal(); navigate('roles')">Yopish</button></div>`);
      } catch (e) { toast(e.message, "error"); }
    }));

  // Parol tiklash so'rovini rad etish (admin)
  document.querySelectorAll("[data-reject-reset]").forEach((b) =>
    b.addEventListener("click", async () => {
      if (!confirm("So'rovni rad etasizmi?")) return;
      try {
        const r = await apiPost(`/password-reset/${b.dataset.rejectReset}/reject`, {});
        if (r.error) throw new Error(r.error);
        toast("So'rov rad etildi");
        navigate("roles");
      } catch (e) { toast(e.message, "error"); }
    }));

  // Backup olish (admin)
  document.querySelectorAll("[data-backup-now]").forEach((b) =>
    b.addEventListener("click", async () => {
      b.disabled = true;
      b.textContent = "⏳ Olinmoqda…";
      try {
        const r = await apiPost("/backups", {});
        if (r.error) throw new Error(r.error);
        toast(`✅ Backup olindi: ${r.filename} (${r.size_mb} MB)`);
        navigate("backup");
      } catch (e) { toast(e.message, "error"); b.disabled = false; b.textContent = "💾 Backup olish"; }
    }));

  // S3 bucket'dan tiklash (faqat direktor/admin)
  document.querySelectorAll("[data-s3-restore]").forEach((b) =>
    b.addEventListener("click", async () => {
      let key = "";
      try { key = decodeURIComponent(escape(atob(b.dataset.s3Restore))); } catch (e) { key = b.dataset.s3Restore; }
      const name = b.dataset.s3Name || key.split("/").pop();
      const ok = confirm(
        `⚠️ DIQQAT!\n\nDatabase S3 dagi «${name}» nusxasi bilan ALMASHTIRILADI.\n` +
        "Nusxa S3'dan yuklab olinadi, joriy holatning xavfsizlik nusxasi avtomatik olinadi (backups/).\n\n" +
        "Davom etasizmi?");
      if (!ok) return;
      b.disabled = true;
      try {
        const r = await apiPost("/backups/restore/s3", { key });
        if (r.error) throw new Error(r.error);
        openModal("✅ Database S3'dan tiklandi", `
          <p><b>${esc(name)}</b> nusxasi S3'dan yuklab olinib, database muvaffaqiyatli tiklandi.</p>
          ${r.safety_backup ? `<p class="muted">💾 Joriy holat xavfsizlik nusxasi: <code>${esc(r.safety_backup)}</code></p>` : ""}
          <p class="muted">⚠️ Bot ham ishlayotgan bo'lsa, tiklangan ma'lumot to'liq ko'rinishi uchun botni ham qayta ishga tushiring.</p>
          <div class="form-actions"><button class="btn btn-primary" onclick="closeModal(); navigate('backup')">Yopish</button></div>`);
      } catch (e) {
        toast(e.message, "error");
        b.disabled = false;
      }
    }));

  // Backup'dan tiklash (faqat direktor/admin)
  document.querySelectorAll("[data-restore-file]").forEach((b) =>
    b.addEventListener("click", async () => {
      const fname = b.dataset.restoreFile;
      const ok = confirm(
        `⚠️ DIQQAT!\n\nDatabase «${fname}» nusxasi bilan ALMASHTIRILADI.\n` +
        "Joriy holatning xavfsizlik nusxasi avtomatik olinadi (backups/ papkasida).\n\n" +
        "Davom etasizmi?");
      if (!ok) return;
      b.disabled = true;
      try {
        const r = await apiPost("/backups/restore", { filename: fname });
        if (r.error) throw new Error(r.error);
        openModal("✅ Database tiklandi", `
          <p><b>${esc(fname)}</b> nusxasidan database muvaffaqiyatli tiklandi.</p>
          ${r.safety_backup ? `<p class="muted">💾 Joriy holat xavfsizlik nusxasi: <code>${esc(r.safety_backup)}</code></p>` : ""}
          <p class="muted">⚠️ Bot ham ishlayotgan bo'lsa, tiklangan ma'lumot to'liq ko'rinishi uchun botni ham qayta ishga tushiring (ochiq ulanishlar eski ma'lumotni ko'rsatishi mumkin).</p>
          <div class="form-actions"><button class="btn btn-primary" onclick="closeModal(); navigate('backup')">Yopish</button></div>`);
      } catch (e) {
        toast(e.message, "error");
        b.disabled = false;
      }
    }));

  // ---------- Operations module (TZ: yoqilg'i / avans / yig'ish / xavfsizlik) ----------

  // Yangi yoqilg'i quyish
  document.querySelectorAll("[data-add-fuel]").forEach((b) =>
    b.addEventListener("click", () => openAddFuelModal()));

  // Yangi avans hisoboti (xodim xarajati)
  document.querySelectorAll("[data-add-expense]").forEach((b) =>
    b.addEventListener("click", () => openAddExpenseModal()));

  // Avans hisobotini tasdiqlash/rad etish (direktor/buxgalter)
  document.querySelectorAll("[data-expense-review]").forEach((b) =>
    b.addEventListener("click", async () => {
      try {
        const r = await apiPost(`/expenses/${b.dataset.expenseReview}/review`, {
          status: b.dataset.status,
        });
        if (r.error) throw new Error(r.error);
        toast(`✅ ${b.dataset.status === "tasdiqlangan" ? "Tasdiqlandi" : "Rad etildi"}`);
        navigate("expenses");
      } catch (e) { toast(e.message, "error"); }
    }));

  // Yig'ish varaqasini tayyor deb belgilash (omborchi/yuklovchi)
  document.querySelectorAll("[data-picking-done]").forEach((b) =>
    b.addEventListener("click", async () => {
      try {
        const r = await apiPost(`/picking/${b.dataset.pickingDone}/status`, { status: "tayyor" });
        if (r.error) throw new Error(r.error);
        toast("✅ Yig'ish tayyor deb belgilandi");
        navigate("picking");
      } catch (e) { toast(e.message, "error"); }
    }));

  // Shubhali harakatni hal qilindi deb belgilash (direktor)
  document.querySelectorAll("[data-security-done]").forEach((b) =>
    b.addEventListener("click", async () => {
      try {
        const r = await apiPost(`/security/alerts/${b.dataset.securityDone}/status`, { status: "hal_qilingan" });
        if (r.error) throw new Error(r.error);
        toast("✅ Hal qilindi deb belgilandi");
        navigate("security");
      } catch (e) { toast(e.message, "error"); }
    }));
}

function openAddFuelModal() {
  openModal("⛽ Yangi yoqilg'i quyish", `
    <div class="form-group"><label>Litr *</label><input id="fuel-liters" type="number" step="0.01" class="form-control" placeholder="50"></div>
    <div class="form-row">
      <div class="form-group"><label>Narx (so'm/L)</label><input id="fuel-price" type="number" class="form-control" placeholder="6800"></div>
      <div class="form-group"><label>Spidometr (km)</label><input id="fuel-odo" type="number" class="form-control" placeholder="125400"></div>
    </div>
    <div class="form-group"><label>Mashina / raqam</label><input id="fuel-vehicle" class="form-control" placeholder="01A123BC"></div>
    <div class="form-group"><label>Izoh</label><input id="fuel-note" class="form-control"></div>
    <div class="form-actions">
      <button class="btn btn-outline" onclick="closeModal()">Bekor qilish</button>
      <button class="btn btn-primary" id="fuel-submit">✅ Saqlash</button>
    </div>`);
  $("#fuel-submit").addEventListener("click", async () => {
    const liters = parseFloat($("#fuel-liters").value);
    if (!liters || liters <= 0) return toast("Litrlar sonini kiriting", "error");
    try {
      const r = await apiPost("/fuel/logs", {
        liters,
        vehicle: $("#fuel-vehicle").value.trim() || null,
        odometer_km: parseFloat($("#fuel-odo").value) || null,
        price_per_liter: parseFloat($("#fuel-price").value) || null,
        note: $("#fuel-note").value.trim() || null,
      });
      if (r.error) throw new Error(r.error);
      closeModal();
      toast(`✅ Yoqilg'i qayd qilindi (${fmtMoney(r.total_cost)})`);
      navigate("fuel");
    } catch (e) { toast(e.message, "error"); }
  });
}

function openAddExpenseModal() {
  openModal("🧾 Yangi avans hisoboti", `
    <div class="form-group"><label>Xarajat turi</label>
      <select id="exp-category" class="form-control">
        <option value="yoqilgi">⛽ Yoqilg'i</option>
        <option value="yol_hagi">🚗 Yo'l haqi</option>
        <option value="ovqat">🍽 Ovqat</option>
        <option value="boshqa">📦 Boshqa</option>
      </select></div>
    <div class="form-group"><label>Summa (so'm) *</label><input id="exp-amount" type="number" class="form-control" placeholder="150000"></div>
    <div class="form-group"><label>Izoh</label><input id="exp-desc" class="form-control" placeholder="Toshkentga yo'l"></div>
    <div class="form-actions">
      <button class="btn btn-outline" onclick="closeModal()">Bekor qilish</button>
      <button class="btn btn-primary" id="exp-submit">✅ Yuborish</button>
    </div>`);
  $("#exp-submit").addEventListener("click", async () => {
    const amount = parseFloat($("#exp-amount").value);
    if (!amount || amount <= 0) return toast("Summa kiriting", "error");
    try {
      const r = await apiPost("/expenses", {
        category: $("#exp-category").value,
        amount,
        description: $("#exp-desc").value.trim() || null,
      });
      if (r.error) throw new Error(r.error);
      closeModal();
      toast(`✅ Avans hisoboti yuborildi: ${r.report_number}`);
      navigate("expenses");
    } catch (e) { toast(e.message, "error"); }
  });
}

function openPayModal(customerId, customerName) {
  openModal(`🧾 Qarz to'lash — ${customerName}`, `
    <div class="form-group"><label>Summa (so'm)</label>
      <input id="pay-amount" type="number" class="form-control" placeholder="500000" min="0"></div>
    <div class="form-group"><label>To'lov usuli</label>
      <select id="pay-method" class="form-control">
        <option value="cash">💵 Naqd</option><option value="card">💳 Karta</option>
        <option value="payme">📱 Payme</option><option value="click">📱 Click</option>
        <option value="transfer">🏦 O'tkazma</option>
      </select></div>
    <div class="form-group"><label>Izoh</label><input id="pay-note" class="form-control" placeholder="ixtiyoriy"></div>
    <div class="form-actions">
      <button class="btn btn-outline" onclick="closeModal()">Bekor qilish</button>
      <button class="btn btn-success" id="pay-submit">✅ To'lash</button>
    </div>`);
  $("#pay-submit").addEventListener("click", async () => {
    const amount = parseFloat($("#pay-amount").value);
    if (!amount || amount <= 0) return toast("Summa kiriting", "error");
    try {
      const r = await apiPost(`/customers/${customerId}/pay`, {
        amount, method: $("#pay-method").value, note: $("#pay-note").value, created_by: "Web",
      });
      if (r.error) throw new Error(r.error);
      closeModal();
      toast(`✅ ${fmtMoney(r.paid)} qarz to'landi. Qoldiq: ${fmtMoney(r.new_debt)}`);
      navigate("customers");
    } catch (e) { toast(e.message, "error"); }
  });
}

function openNewCustomerModal() {
  openModal("➕ Yangi mijoz", `
    <div class="form-group"><label>Ism *</label><input id="nc-name" class="form-control" placeholder="Mijoz ismi"></div>
    <div class="form-row">
      <div class="form-group"><label>Telefon</label><input id="nc-phone" class="form-control" placeholder="+998901234567"></div>
      <div class="form-group"><label>Kompaniya</label><input id="nc-company" class="form-control" placeholder="MChJ ..."></div>
    </div>
    <div class="form-group"><label>Kredit limiti (so'm)</label><input id="nc-limit" type="number" class="form-control" value="0"></div>
    <div class="form-group"><label>Manzil</label><input id="nc-address" class="form-control"></div>
    <label><input type="checkbox" id="nc-wholesale"> Ulgurji mijoz</label>
    <div class="form-actions">
      <button class="btn btn-outline" onclick="closeModal()">Bekor qilish</button>
      <button class="btn btn-primary" id="nc-submit">✅ Saqlash</button>
    </div>`);
  $("#nc-submit").addEventListener("click", async () => {
    const name = $("#nc-name").value.trim();
    if (!name) return toast("Ismni kiriting", "error");
    try {
      const r = await apiPost("/customers", {
        name,
        phone: $("#nc-phone").value.trim() || null,
        company: $("#nc-company").value.trim() || null,
        address: $("#nc-address").value.trim() || null,
        credit_limit: parseFloat($("#nc-limit").value || 0),
        is_wholesale: $("#nc-wholesale").checked,
      });
      if (r.error) throw new Error(r.error);
      closeModal();
      toast(`✅ Mijoz qo'shildi: ${r.customer.name}`);
      navigate("customers");
    } catch (e) { toast(e.message, "error"); }
  });
}

function openNewSupplierModal() {
  openModal("➕ Yangi yetkazib beruvchi", `
    <div class="form-group"><label>Nomi *</label><input id="ns-name" class="form-control" placeholder="O'zbekiston Sement"></div>
    <div class="form-row">
      <div class="form-group"><label>Telefon</label><input id="ns-phone" class="form-control" placeholder="+998901234567"></div>
      <div class="form-group"><label>Aloqa shaxsi</label><input id="ns-contact" class="form-control"></div>
    </div>
    <div class="form-group"><label>Manzil</label><input id="ns-address" class="form-control"></div>
    <div class="form-actions">
      <button class="btn btn-outline" onclick="closeModal()">Bekor qilish</button>
      <button class="btn btn-primary" id="ns-submit">✅ Saqlash</button>
    </div>`);
  $("#ns-submit").addEventListener("click", async () => {
    const name = $("#ns-name").value.trim();
    if (!name) return toast("Nomni kiriting", "error");
    try {
      const r = await apiPost("/suppliers", {
        name,
        phone: $("#ns-phone").value.trim() || null,
        contact_person: $("#ns-contact").value.trim() || null,
        address: $("#ns-address").value.trim() || null,
      });
      if (r.error) throw new Error(r.error);
      closeModal();
      toast(`✅ Yetkazib beruvchi qo'shildi: ${r.supplier.name}`);
      navigate("suppliers");
    } catch (e) { toast(e.message, "error"); }
  });
}

/* ---------- Auth UI ---------- */
function applyUser() {
  hideLogin();
  const u = ME;
  const chip = $("#user-chip");
  chip.textContent = `${u.full_name} · ${u.role_label}`;
  chip.classList.remove("hidden");
  $("#btn-logout").classList.remove("hidden");
  // Sahifa tugmalarini rol bo'yicha chegaralash
  document.querySelectorAll(".nav-item[data-page]").forEach((b) => {
    b.style.display = canViewModule(PAGE_MODULES[b.dataset.page]) ? "" : "none";
  });
  $("#btn-new-customer").style.display = canEditModule("crm") ? "" : "none";
  $("#btn-new-supplier").style.display = canEditModule("supplier") ? "" : "none";
  const pages = allowedPages();
  navigate(pages.length ? pages[0] : "overview");
}

function bindUi() {
  document.querySelectorAll(".nav-item[data-page]").forEach((b) =>
    b.addEventListener("click", () => navigate(b.dataset.page)));
  $("#btn-refresh").addEventListener("click", () => navigate(state.page));
  $("#btn-new-customer").addEventListener("click", openNewCustomerModal);
  $("#btn-new-supplier").addEventListener("click", openNewSupplierModal);
  $("#modal-close").addEventListener("click", closeModal);
  $("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });
  $("#btn-logout").addEventListener("click", async () => {
    await doLogout();
    $("#user-chip").classList.add("hidden");
    $("#btn-logout").classList.add("hidden");
    document.querySelectorAll(".nav-item[data-page]").forEach((b) => { b.style.display = ""; });
    showLogin();
  });
  $("#login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const phone = $("#login-phone").value.trim();
    const password = $("#login-password").value;
    const errEl = $("#login-error");
    errEl.classList.add("hidden");
    if (!phone || !password) {
      errEl.textContent = "Telefon va parolni kiriting";
      errEl.classList.remove("hidden");
      return;
    }
    $("#login-submit").disabled = true;
    try {
      ME = await doLogin(phone, password);
      applyUser();
    } catch (err) {
      const msg = err.message && err.message !== "401" ? err.message : "Telefon yoki parol noto'g'ri";
      errEl.textContent = msg;
      errEl.classList.remove("hidden");
    } finally {
      $("#login-submit").disabled = false;
    }
  });

  // Parolni tiklash oynasini ochish/yopish
  const resetRequestNote = $("#reset-request-note");
  const showResetView = () => {
    $("#login-form").classList.add("hidden");
    $("#reset-view").classList.remove("hidden");
    $("#login-error").classList.add("hidden");
    $("#reset-error").classList.add("hidden");
    $("#reset-step-request").classList.remove("hidden");
    $("#reset-step-code").classList.add("hidden");
    resetRequestNote.textContent = "";
  };
  $("#btn-show-reset").addEventListener("click", showResetView);
  $("#btn-reset-to-login").addEventListener("click", () => {
    $("#reset-view").classList.add("hidden");
    $("#login-form").classList.remove("hidden");
    $("#reset-error").classList.add("hidden");
  });

  // So'rov yuborish
  $("#reset-request-btn").addEventListener("click", async () => {
    const phone = $("#reset-phone").value.trim();
    const reason = $("#reset-reason").value.trim();
    if (!phone) { resetRequestNote.textContent = "⚠️ Telefon raqamini kiriting"; return; }
    $("#reset-request-btn").disabled = true;
    try {
      const r = await apiPost("/password-reset/request", { phone, reason });
      if (r.error) throw new Error(r.error);
      resetRequestNote.textContent = "✅ So'rov yuborildi. Direktor tasdiqlagach, sizga kod beradi. Kod bo'lsa quyidagi qadamga o'ting.";
      $("#reset-step-request").classList.add("hidden");
      $("#reset-step-code").classList.remove("hidden");
      $("#reset-code").value = "";
      $("#reset-new-password").value = "";
    } catch (err) {
      resetRequestNote.textContent = "❌ " + (err.message || "Xatolik");
    } finally {
      $("#reset-request-btn").disabled = false;
    }
  });

  // Kod bilan parolni yangilash
  $("#reset-complete-btn").addEventListener("click", async () => {
    const errEl = $("#reset-error");
    errEl.classList.add("hidden");
    const phone = $("#reset-phone").value.trim();
    const code = $("#reset-code").value.trim();
    const newPassword = $("#reset-new-password").value;
    if (!code || !newPassword) {
      errEl.textContent = "Kod va yangi parolni kiriting";
      errEl.classList.remove("hidden");
      return;
    }
    $("#reset-complete-btn").disabled = true;
    try {
      const r = await apiPost("/password-reset/complete", { phone, code, new_password: newPassword });
      if (r.error) throw new Error(r.error);
      toast("✅ Parol yangilandi. Yangi parol bilan kiring.");
      $("#reset-view").classList.add("hidden");
      $("#login-form").classList.remove("hidden");
      $("#login-password").value = newPassword;
      $("#login-phone").value = phone;
    } catch (err) {
      errEl.textContent = err.message || "Xatolik";
      errEl.classList.remove("hidden");
    } finally {
      $("#reset-complete-btn").disabled = false;
    }
  });
}

/* ---------- Init ---------- */
async function init() {
  // API status
  try {
    const h = await fetch("/health").then((r) => r.json()).catch(() => null);
    const st = $("#api-status");
    if (h && h.python_api) {
      st.textContent = "✅ Node + Python API";
      st.className = "pill pill-ok";
    } else {
      st.textContent = "⚠️ Backend yo'q";
      st.className = "pill pill-bad";
    }
  } catch (e) {
    $("#api-status").textContent = "⚠️ Xatolik";
    $("#api-status").className = "pill pill-bad";
  }
  bindUi();

  if (!TOKEN) { showLogin(); return; }
  try {
    const me = await api("/me");
    ME = me.user;
    applyUser();
  } catch (e) {
    /* api() 401 bo'lsa login ekranini ko'rsatgan */
    if (e.message !== "401") {
      $("#login-error").textContent = "Server bilan bog'lanib bo'lmadi. Python API ishlayotganini tekshiring.";
      $("#login-error").classList.remove("hidden");
      showLogin();
    }
  }
}

window.closeModal = closeModal;
window.openPayModal = openPayModal;
window.addEventListener("DOMContentLoaded", init);
