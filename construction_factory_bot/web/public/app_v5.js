/*
 * app_v5.js — construction_factory_bot.md (TZ) bo'yicha qo'shimcha web sahifalar:
 *   💰 Sotuv (POS)      — buyurtma yaratish, nasiya/aralash to'lov, bekor qilish
 *   🏭 Ishlab chiqarish — buyurtma yaratish, holat, sifat nazorati aktlari
 *   🚚 Yetkazib berish — topshiriq yaratish, GPS, imzo, holat
 *   ↩️ Qaytarish        — qaytarish akti (pul/almashtirish/bonus)
 *   💵 Smena (kassa)    — ochish/yopish, farq
 *   🛒 Do'kon buyurtmalari — web-do'kon buyurtmalarini boshqarish
 *
 * app.js dagi global yordamchilardan foydalanadi: api/apiPost, esc, toast,
 * openModal, closeModal, navigate, PAGES, PAGE_MODULES, RENDERERS, ME.
 */
(function () {
  if (typeof PAGES === "undefined") return; // app.js yuklanmagan

  /* ---------- Sahifalarni ro'yxatga olish ---------- */
  PAGES.sales = "💰 Sotuv (POS)";
  PAGES.production = "🏭 Ishlab chiqarish";
  PAGES.deliveries = "🚚 Yetkazib berish";
  PAGES.returns = "↩️ Qaytarish";
  PAGES.cashshifts = "💵 Smena (kassa)";
  PAGES.shoporders = "🛒 Do'kon buyurtmalari";

  PAGE_MODULES.sales = "sales";
  PAGE_MODULES.production = "production";
  PAGE_MODULES.deliveries = "delivery";
  PAGE_MODULES.returns = "sales"; // API: sales|finance|crm
  PAGE_MODULES.cashshifts = "cash_shift";
  PAGE_MODULES.shoporders = "finance";

  const money = (n) => (Number(n) || 0).toLocaleString("uz-UZ") + " so'm";

  const sel = (name, options, extra = "") =>
    `<select id="v5-${name}" ${extra}>${options}</select>`;

  const productOptions = (products) =>
    products.map((p) =>
      `<option value="${p.id}" data-price="${p.selling_price || p.retail_price || 0}"
        data-wholesale="${p.wholesale_price || 0}">
        ${esc(p.name)} — ${money(p.selling_price)} (qoldiq: ${p.available_qty ?? "?"})</option>`
    ).join("");

  /* ================= 💰 SOTUV (POS) ================= */
  async function renderSales() {
    const [prod, orders, cust] = await Promise.all([
      api("/products"), api("/orders/sales"), api("/customers"),
    ]);
    const products = prod.products || [];
    const customers = cust.customers || [];
    const form = `
      <div class="panel">
        <div class="panel-header"><h3>🛒 Yangi sotuv (buyurtma)</h3></div>
        <div class="panel-body">
          <div class="form-grid">
            <label>Mahsulot
              ${sel("sale-product", `<option value="">— tanlang —</option>` + productOptions(products),
                `onchange="v5SetSalePrice(this)"`)}
            </label>
            <label>Miqdor <input id="v5-sale-qty" type="number" min="0" step="any" value="1"></label>
            <label>Narx (1 birlik) <input id="v5-sale-price" type="number" min="0" step="any"></label>
            <label>Chegirma (so'm) <input id="v5-sale-discount" type="number" min="0" value="0"></label>
            <label>Sotuv turi
              ${sel("sale-type", `<option value="retail">Chakana</option><option value="wholesale">Ulgurji (100+)</option>`)}
            </label>
            <label>To'lov usuli
              ${sel("sale-method", `<option value="cash">💵 Naqd</option><option value="card">💳 Karta</option>
                <option value="payme">Payme</option><option value="click">Click</option>
                <option value="credit">🧾 Nasiya (qarz)</option>`)}
            </label>
            <label>Mijoz
              <select id="v5-sale-customer">
                <option value="">— mijozsiz (jismoniy) —</option>
                ${customers.map((c) =>
                  `<option value="${c.id}" data-name="${esc(c.name)}" data-phone="${esc(c.phone || "")}">
                    ${esc(c.name)} (qarz: ${money(c.total_debt)})</option>`).join("")}
              </select>
            </label>
            <label>Yangi mijoz ismi <input id="v5-sale-cname" placeholder="(agar mavjud bo'lmasa)"></label>
            <label>Telefon <input id="v5-sale-cphone" placeholder="+998..."></label>
          </div>
          <div class="form-actions">
            <button class="btn btn-primary" onclick="v5CreateSale()">✅ Sotuvni rasmiylashtirish</button>
          </div>
        </div>
      </div>`;

    const rows = (orders.orders || []).map((o) => `
      <tr>
        <td>${esc(o.invoice_number)}</td>
        <td>${esc(o.product_name || "—")}</td>
        <td>${Number(o.quantity || 0).toLocaleString()} ${esc(o.product_name ? "" : "")}</td>
        <td>${money(o.total_amount)}</td>
        <td>${money(o.paid_amount)}</td>
        <td>${esc(o.customer_name || "—")}</td>
        <td>${esc(o.payment_method || "—")}${o.is_credit ? " 🧾" : ""}</td>
        <td>${badge(o.credit_status || o.status || "—", o.status === "cancelled" ? "red" : "green")}</td>
        <td>
          <button class="btn btn-small" data-v5-cancel-order="${esc(o.invoice_number)}"
            ${o.status === "cancelled" ? "disabled" : ""}>Bekor</button>
        </td>
      </tr>`).join("");

    return form + panel("📋 Oxirgi sotuvlar",
      `<div class="table-wrap"><table><thead><tr>
        <th>Chek №</th><th>Mahsulot</th><th>Miqdor</th><th>Summa</th><th>To'langan</th>
        <th>Mijoz</th><th>Usul</th><th>Holat</th><th></th></tr></thead>
        <tbody>${rows || `<tr><td colspan="9">${empty("Sotuvlar yo'q")}</td></tr>`}</tbody></table></div>`);
  }

  window.v5SetSalePrice = function (el) {
    const opt = el.selectedOptions[0];
    const type = $("#v5-sale-type").value;
    const price = type === "wholesale" && opt.dataset.wholesale
      ? opt.dataset.wholesale : opt.dataset.price;
    $("#v5-sale-price").value = price || 0;
  };

  window.v5CreateSale = async function () {
    const productId = $("#v5-sale-product").value;
    const qty = parseFloat($("#v5-sale-qty").value);
    const price = parseFloat($("#v5-sale-price").value);
    const discount = parseFloat($("#v5-sale-discount").value) || 0;
    const method = $("#v5-sale-method").value;
    const saleType = $("#v5-sale-type").value;
    if (!productId || !qty || qty <= 0 || !price) {
      toast("Mahsulot, miqdor va narxni kiriting", "error");
      return;
    }
    const cid = $("#v5-sale-customer").value;
    const payload = {
      product_id: Number(productId), quantity: qty, unit_price: price,
      discount_amount: discount, sale_type: saleType, payment_method: method,
      customer_id: cid ? Number(cid) : null,
      customer_name: cid ? null : ($("#v5-sale-cname").value.trim() || null),
      customer_phone: cid ? null : ($("#v5-sale-cphone").value.trim() || null),
    };
    const total = qty * price - discount;
    if (method === "credit") {
      payload.payments = [{ method: "credit", amount: Math.round(total) }];
    } else if (method === "cash" || method === "card" || method === "payme" || method === "click") {
      payload.payments = [{ method, amount: Math.round(total) }];
    }
    try {
      const r = await apiPost("/orders", payload);
      if (r.error) throw new Error(r.error);
      openModal("✅ Sotuv rasmiylashtirildi", `
        <p>Chek: <b>${esc(r.order.invoice_number)}</b></p>
        <p>Summa: <b>${money(r.order.total_amount)}</b></p>
        <p>To'langan: <b>${money(r.order.paid_amount)}</b></p>
        ${r.order.is_credit ? `<p class="muted">🧾 Qolgan qism mijoz qarziga yozildi (${esc(r.order.credit_status)})</p>` : ""}
        <div class="form-actions"><button class="btn btn-primary" onclick="closeModal(); navigate('sales')">Yopish</button></div>`);
      navigate("sales");
    } catch (e) { toast(e.message, "error"); }
  };

  /* ================= 🏭 ISHLAB CHIQARISH ================= */
  async function renderProduction() {
    const [prod, orders, qc] = await Promise.all([
      api("/products"), api("/production"), api("/production/quality"),
    ]);
    const products = prod.products || [];
    const form = `
      <div class="panel">
        <div class="panel-header"><h3>➕ Yangi ishlab chiqarish buyurtmasi</h3></div>
        <div class="panel-body">
          <div class="form-grid">
            <label>Mahsulot ${sel("prod-product", `<option value="">— tanlang —</option>` + productOptions(products))}</label>
            <label>Miqdor (dona) <input id="v5-prod-qty" type="number" min="1" value="1000"></label>
            <label>Ustuvorlik ${sel("prod-priority",
              `<option value="1">1 — past</option><option value="2">2</option>
               <option value="3" selected>3 — o'rtacha</option><option value="4">4</option>
               <option value="5">5 — yuqori</option>`)}</label>
          </div>
          <div class="form-actions">
            <button class="btn btn-primary" onclick="v5CreateProduction()">✅ Yaratish</button>
          </div>
        </div>
      </div>`;

    const rows = (orders.production_orders || []).map((o) => `
      <tr>
        <td>${esc(o.order_number)}</td>
        <td>${esc(o.product_name || "—")}</td>
        <td>${Number(o.quantity || 0).toLocaleString()}</td>
        <td>${badge(o.status || "—", o.status === "jarayonda" ? "blue" : o.status === "tayyor" ? "green" : o.status === "bekor" || o.status === "bekor_qilingan" ? "red" : "yellow")}</td>
        <td>${esc(o.qc_status || "—")}</td>
        <td>${money(o.total_cost)}</td>
        <td>
          ${o.status !== "tayyor" ? `<button class="btn btn-small" data-v5-prod-status="${o.id}|jarayonda">Boshlash</button>
          <button class="btn btn-small" data-v5-prod-status="${o.id}|tayyor">Tayyor</button>` : ""}
          ${o.status === "kutilmoqda" ? `<button class="btn btn-small" data-v5-prod-status="${o.id}|bekor">Bekor</button>` : ""}
        </td>
      </tr>`).join("");

    const qcRows = (qc.acts || qc.quality_acts || []).map((a) => `
      <tr><td>${esc(a.act_number || a.id)}</td><td>${esc(a.product_name || "—")}</td>
        <td>${esc(a.quantity_checked || "—")}</td><td>${esc(a.accepted_qty || "—")}</td>
        <td>${esc(a.rejected_qty || "—")}</td>
        <td>${badge(a.quality_status || a.qc_status || "—",
          (a.quality_status || a.qc_status) === "qabul_qilingan" ? "green" : "red")}</td></tr>`).join("");

    return form +
      panel("📋 Buyurtmalar",
        `<div class="table-wrap"><table><thead><tr>
          <th>Raqam</th><th>Mahsulot</th><th>Miqdor</th><th>Holat</th><th>QC</th><th>Narxi</th><th></th>
          </tr></thead><tbody>${rows || `<tr><td colspan="7">${empty("Buyurtmalar yo'q")}</td></tr>`}
          </tbody></table></div>`) +
      panel("🔬 Sifat nazorati aktlari",
        `<div class="table-wrap"><table><thead><tr>
          <th>Akt №</th><th>Mahsulot</th><th>Tekshirilgan</th><th>Qabul</th><th>Rad</th><th>Holat</th>
          </tr></thead><tbody>${qcRows || `<tr><td colspan="6">${empty("QC aktlar yo'q")}</td></tr>`}
          </tbody></table></div>`);
  }

  window.v5CreateProduction = async function () {
    const productId = $("#v5-prod-product").value;
    const qty = parseInt($("#v5-prod-qty").value, 10);
    const priority = parseInt($("#v5-prod-priority").value, 10);
    if (!productId || !qty) { toast("Mahsulot va miqdorni kiriting", "error"); return; }
    try {
      const r = await apiPost("/production", { product_id: Number(productId), quantity: qty, priority });
      if (r.error) throw new Error(r.error);
      toast(`✅ Buyurtma yaratildi: ${r.production_order.order_number}`);
      navigate("production");
    } catch (e) { toast(e.message, "error"); }
  };

  /* ================= 🚚 YETKAZIB BERISH ================= */
  async function renderDeliveries() {
    const [d, sales] = await Promise.all([
      api("/deliveries"), api("/deliveries/deliverable-sales"),
    ]);
    let drivers = [];
    try {
      // Haydovchilar ro'yxati admin huquqini talab qiladi — haydovchi/sotuvchi
      // rolida sahifa buzilmasligi uchun xatolikni yutamiz.
      const users = await api("/users");
      drivers = (users.users || []).filter((u) => u.role === "haydovchi");
    } catch (e) { /* ro'yxat ko'rinmaydi, yaratish tugmasi passiv bo'ladi */ }
    const deliveries = d.deliveries || [];
    const deliverable = sales.sales || [];
    const form = `
      <div class="panel">
        <div class="panel-header"><h3>➕ Yangi yetkazish topshirig'i</h3></div>
        <div class="panel-body">
          <div class="form-grid">
            <label>Sotuv (yetkazilmagan qoldiq)
              <select id="v5-del-sale">
                <option value="">— tanlang —</option>
                ${deliverable.map((s) => `<option value="${s.id}">
                  ${esc(s.invoice_number)} — ${esc(s.product_name)} (qoldiq: ${s.remaining} ${esc(s.unit || "")}) — ${esc(s.customer_name || "—")}</option>`).join("")}
              </select>
            </label>
            <label>Haydovchi
              <select id="v5-del-driver">
                <option value="">— tanlang —</option>
                ${drivers.map((u) => `<option value="${u.id}">${esc(u.full_name)} (${esc(u.phone_number)})</option>`).join("")}
              </select>
            </label>
          </div>
          <div class="form-actions">
            <button class="btn btn-primary" onclick="v5CreateDelivery()">✅ Biriktirish</button>
          </div>
        </div>
      </div>`;

    const rows = deliveries.map((x) => `
      <tr>
        <td>${esc(x.delivery_number || x.id)}</td>
        <td>${esc(x.customer_name || "—")}<br><span class="muted">${esc(x.customer_address || "")}</span></td>
        <td>${esc(x.product_name || "—")} × ${x.quantity} ${esc(x.unit || "")}</td>
        <td>${esc(x.driver_name || "—")}</td>
        <td>${badge(x.status_label || x.status || "—", x.status === "yetkazildi" ? "green" : x.status === "yo'lda" ? "blue" : "yellow")}</td>
        <td>
          ${x.status === "tayinlangan" ? `<button class="btn btn-small" data-v5-del-start="${x.id}">🚀 Boshlash</button>` : ""}
          ${x.status === "yo'lda" ? `<button class="btn btn-small" data-v5-del-done="${x.id}">✅ Yetkazildi</button>` : ""}
          ${x.status !== "bekor" && x.status !== "yetkazildi" ? `<button class="btn btn-small" data-v5-del-cancel="${x.id}">Bekor</button>` : ""}
          <button class="btn btn-small" data-v5-del-sign="${x.id}">✍️ Imzo</button>
          <button class="btn btn-small" data-v5-del-loc="${x.id}">📍 GPS</button>
        </td>
      </tr>`).join("");

    return form + panel("📋 Yetkazishlar",
      `<div class="table-wrap"><table><thead><tr>
        <th>Topshiriq</th><th>Mijoz</th><th>Yuk</th><th>Haydovchi</th><th>Holat</th><th></th>
        </tr></thead><tbody>${rows || `<tr><td colspan="6">${empty("Yetkazishlar yo'q")}</td></tr>`}
        </tbody></table></div>`);
  }

  window.v5CreateDelivery = async function () {
    const saleId = $("#v5-del-sale").value;
    const driverId = $("#v5-del-driver").value;
    if (!saleId || !driverId) { toast("Sotuv va haydovchini tanlang", "error"); return; }
    try {
      const r = await apiPost("/deliveries", { sale_id: Number(saleId), driver_id: Number(driverId) });
      if (r.error || r.detail) throw new Error(r.error || r.detail);
      toast("✅ Topshiriq haydovchiga biriktirildi");
      navigate("deliveries");
    } catch (e) { toast(e.message, "error"); }
  };

  window.v5DeliverySignature = function (id) {
    openModal("✍️ Mijoz imzosi", `
      <label>Imzo qoldiruvchi <input id="v5-sign-name" placeholder="Mijoz ismi"></label>
      <label>Usul ${sel("sign-type", `<option value="pin">PIN kod</option><option value="fingerprint">Barmoq izi</option>`)}</label>
      <div class="form-actions">
        <button class="btn btn-primary" onclick="v5SendSignature(${id})">Tasdiqlash</button>
        <button class="btn" onclick="closeModal()">Yopish</button>
      </div>`);
  };

  window.v5SendSignature = async function (id) {
    const name = $("#v5-sign-name").value.trim();
    const type = $("#v5-sign-type").value;
    if (!name) { toast("Imzo qoldiruvchi ismini kiriting", "error"); return; }
    try {
      const r = await apiPost(`/deliveries/${id}/signature`, { signature_name: name, signature_type: type });
      if (r.error) throw new Error(r.error);
      toast("✅ Imzo qabul qilindi");
      closeModal();
      navigate("deliveries");
    } catch (e) { toast(e.message, "error"); }
  };

  window.v5DeliveryLocation = function (id) {
    const lat = prompt("Kenglik (latitude), masalan 41.3111:");
    const lng = prompt("Uzunlik (longitude), masalan 69.2797:");
    if (lat === null || lng === null) return;
    apiPost(`/deliveries/${id}/location`, { latitude: parseFloat(lat), longitude: parseFloat(lng) })
      .then((r) => { if (r.error) throw new Error(r.error); toast("📍 GPS yangilandi"); navigate("deliveries"); })
      .catch((e) => toast(e.message, "error"));
  };

  /* ================= ↩️ QAYTARISH ================= */
  async function renderReturns() {
    const [cand, acts] = await Promise.all([api("/returns/candidates"), api("/returns")]);
    const candidates = cand.candidates || [];
    const returns = acts.returns || [];
    const form = `
      <div class="panel">
        <div class="panel-header"><h3>↩️ Yangi qaytarish akti (7 kun qoidasi)</h3></div>
        <div class="panel-body">
          <div class="form-grid">
            <label>Sotuv (qaytarishga yaroqli)
              <select id="v5-ret-sale">
                <option value="">— tanlang —</option>
                ${candidates.filter((c) => c.eligible).map((c) =>
                  `<option value="${c.id}" data-max="${c.remaining}" data-price="${c.unit_price}">
                    ${esc(c.invoice_number)} — ${esc(c.product_name)} (qoldiq: ${c.remaining})</option>`).join("")}
              </select>
            </label>
            <label>Miqdor <input id="v5-ret-qty" type="number" min="0" step="any" value="1"></label>
            <label>Qaytarish turi
              ${sel("ret-type", `<option value="pul">💵 Pul qaytarish</option>
                <option value="almashtirish">🔄 Boshqa mahsulotga almashtirish</option>
                <option value="bonus">🎁 Bonus balansga</option>`)}
            </label>
            <label>Sabab <input id="v5-ret-reason" placeholder="Sifatsiz / noto'g'ri / ..."></label>
          </div>
          <div class="form-actions">
            <button class="btn btn-primary" onclick="v5CreateReturn()">✅ Aktni rasmiylashtirish</button>
          </div>
        </div>
      </div>`;

    const rows = returns.map((a) => `
      <tr>
        <td>${esc(a.act_number || a.id)}</td>
        <td>${esc(a.product_name || "—")}</td>
        <td>${Number(a.quantity || 0).toLocaleString()}</td>
        <td>${money(a.amount)}</td>
        <td>${badge(a.return_type || "—", a.return_type === "pul" ? "blue" : a.return_type === "almashtirish" ? "green" : "purple")}</td>
        <td>${esc(a.sale_invoice || a.sale_id || "—")}</td>
        <td>${esc(a.created_at ? String(a.created_at).slice(0, 16) : "—")}</td>
      </tr>`).join("");

    return form + panel("📋 Qaytarish aktlari",
      `<div class="table-wrap"><table><thead><tr>
        <th>Akt №</th><th>Mahsulot</th><th>Miqdor</th><th>Summa</th><th>Tur</th><th>Sotuv</th><th>Sana</th>
        </tr></thead><tbody>${rows || `<tr><td colspan="7">${empty("Qaytarish aktlar yo'q")}</td></tr>`}
        </tbody></table></div>`);
  }

  window.v5CreateReturn = async function () {
    const saleId = $("#v5-ret-sale").value;
    const qty = parseFloat($("#v5-ret-qty").value);
    const type = $("#v5-ret-type").value;
    const reason = $("#v5-ret-reason").value.trim();
    if (!saleId || !qty) { toast("Sotuv va miqdorni kiriting", "error"); return; }
    try {
      const r = await apiPost("/returns", { sale_id: Number(saleId), quantity: qty, return_type: type, reason });
      if (r.error || r.detail) throw new Error(r.error || r.detail);
      openModal("✅ Qaytarish akti yaratildi", `
        <p>Akt: <b>${esc((r.return_act && r.return_act.act_number) || r.act_number || "—")}</b></p>
        <p>Summa: <b>${money((r.return_act && r.return_act.amount) || r.amount || 0)}</b></p>
        <div class="form-actions"><button class="btn btn-primary" onclick="closeModal(); navigate('returns')">Yopish</button></div>`);
      navigate("returns");
    } catch (e) { toast(e.message, "error"); }
  };

  /* ================= 💵 SMENA (KASSA) ================= */
  async function renderCashShifts() {
    const [cur, list] = await Promise.all([api("/cash-shifts/current"), api("/cash-shifts")]);
    const shift = cur.shift;
    const summary = cur.summary || {};
    let top = "";
    if (shift) {
      top = panel("💵 Joriy smena", `
        <div class="cards">
          <div class="card"><div class="card-label">Smena</div><div class="card-value">${esc(shift.shift_number)}</div></div>
          <div class="card"><div class="card-label">Kassir</div><div class="card-value">${esc(shift.cashier_name || "—")}</div></div>
          <div class="card"><div class="card-label">Boshlang'ich</div><div class="card-value">${money(shift.opening_balance)}</div></div>
          <div class="card"><div class="card-label">Kutilgan naqd</div><div class="card-value">${money(summary.expected_cash)}</div></div>
        </div>
        <div class="form-actions">
          <label>Haqiqiy naqd pul <input id="v5-shift-actual" type="number" min="0"></label>
          <button class="btn btn-primary" onclick="v5CloseShift(${shift.id})">🔒 Smenani yopish</button>
        </div>`);
    } else {
      top = panel("💵 Smena yopiq", `
        <div class="form-grid">
          <label>Boshlang'ich naqd pul <input id="v5-shift-open" type="number" min="0" value="0"></label>
        </div>
        <div class="form-actions">
          <button class="btn btn-primary" onclick="v5OpenShift()">🔓 Smenani ochish</button>
        </div>`);
    }
    const rows = (list.shifts || []).map((s) => `
      <tr>
        <td>${esc(s.shift_number)}</td>
        <td>${esc(s.cashier_name || "—")}</td>
        <td>${money(s.opening_balance)}</td>
        <td>${money(s.expected_cash)}</td>
        <td>${money(s.actual_cash)}</td>
        <td>${badge(String(s.difference || 0) === "0" || !s.difference ? "0" : money(s.difference),
          String(s.difference || 0) === "0" || !s.difference ? "green" : "red")}</td>
        <td>${badge(s.status_label || s.status || "—", s.status === "yopilgan" ? "green" : "blue")}</td>
        <td>${esc(String(s.opened_at || "").slice(0, 16))}</td>
      </tr>`).join("");
    return top + panel("📋 Smenalar tarixi",
      `<div class="table-wrap"><table><thead><tr>
        <th>Raqam</th><th>Kassir</th><th>Boshlang'ich</th><th>Kutilgan</th><th>Haqiqiy</th><th>Farq</th><th>Holat</th><th>Ochilgan</th>
        </tr></thead><tbody>${rows || `<tr><td colspan="8">${empty("Smenalar yo'q")}</td></tr>`}
        </tbody></table></div>`);
  }

  window.v5OpenShift = async function () {
    const balance = parseFloat($("#v5-shift-open").value) || 0;
    try {
      const r = await apiPost("/cash-shifts/open", { opening_balance: balance });
      if (r.error || r.detail) throw new Error(r.error || r.detail);
      toast(`✅ Smena ochildi: ${r.shift.shift_number}`);
      navigate("cashshifts");
    } catch (e) { toast(e.message, "error"); }
  };

  window.v5CloseShift = async function (id) {
    const actual = parseFloat($("#v5-shift-actual").value);
    if (isNaN(actual)) { toast("Haqiqiy naqd pulni kiriting", "error"); return; }
    try {
      const r = await apiPost(`/cash-shifts/${id}/close`, { actual_cash: actual });
      if (r.error || r.detail) throw new Error(r.error || r.detail);
      openModal("🔒 Smena yopildi", `
        <p>Farq: <b>${money(r.shift ? r.shift.difference : r.difference)}</b></p>
        <div class="form-actions"><button class="btn btn-primary" onclick="closeModal(); navigate('cashshifts')">Yopish</button></div>`);
      navigate("cashshifts");
    } catch (e) { toast(e.message, "error"); }
  };

  /* ================= 🛒 DO'KON BUYURTMALARI ================= */
  async function renderShopOrders() {
    const r = await api("/shop-orders");
    const orders = r.orders || [];
    const rows = orders.map((o) => `
      <tr>
        <td>${esc(o.order_number)}</td>
        <td>${esc(o.customer_name || "—")}<br><span class="muted">${esc(o.customer_phone || "")}</span></td>
        <td>${(o.items || []).map((i) => `${esc(i.product_name)} × ${i.quantity} ${esc(i.unit || "")}`).join("<br>") || "—"}</td>
        <td>${money(o.total_amount)}</td>
        <td>${esc(o.method_label || o.method || "—")}</td>
        <td>${badge(o.status_label || o.status || "—", o.status === "yangi" ? "blue" : o.status === "yakunlangan" ? "green" : "yellow")}</td>
        <td>
          <button class="btn btn-small" onclick="v5ShopOrderDetail(${o.id})">👁 Ko'rish</button>
          ${o.status === "yangi" || o.status === "kutilmoqda" ? `<button class="btn btn-small" data-v5-shop-cancel="${o.id}">Bekor</button>` : ""}
        </td>
      </tr>`).join("");
    return panel("🛒 Web-do'kon buyurtmalari",
      `<div class="table-wrap"><table><thead><tr>
        <th>Buyurtma</th><th>Mijoz</th><th>Mahsulotlar</th><th>Summa</th><th>To'lov</th><th>Holat</th><th></th>
        </tr></thead><tbody>${rows || `<tr><td colspan="7">${empty("Buyurtmalar yo'q")}</td></tr>`}
        </tbody></table></div>`);
  }

  window.v5ShopOrderDetail = function (id) {
    api("/shop-orders").then((r) => {
      const o = (r.orders || []).find((x) => x.id === id);
      if (!o) { toast("Buyurtma topilmadi", "error"); return; }
      const items = (o.items || []).map((i) =>
        `<tr><td>${esc(i.product_name)}</td><td>${i.quantity} ${esc(i.unit || "")}</td><td>${money(i.amount)}</td></tr>`).join("");
      openModal(`🛒 ${esc(o.order_number)}`, `
        <p><b>${esc(o.customer_name || "—")}</b> · ${esc(o.customer_phone || "—")}</p>
        <p class="muted">${esc(o.address || "")}</p>
        <table class="table"><thead><tr><th>Mahsulot</th><th>Miqdor</th><th>Summa</th></tr></thead>
          <tbody>${items || `<tr><td colspan="3">${empty("—")}</td></tr>`}</tbody></table>
        <p>Jami: <b>${money(o.total_amount)}</b> · ${esc(o.method_label || o.method || "—")}</p>
        <p>Holat: ${badge(o.status_label || o.status || "—", "blue")}</p>
        ${o.comment ? `<p class="muted">Izoh: ${esc(o.comment)}</p>` : ""}
        <div class="form-actions"><button class="btn btn-primary" onclick="closeModal()">Yopish</button></div>`);
    }).catch((e) => toast(e.message, "error"));
  };

  /* ---------- Renderer'larni ro'yxatga olish ---------- */
  RENDERERS.sales = renderSales;
  RENDERERS.production = renderProduction;
  RENDERERS.deliveries = renderDeliveries;
  RENDERERS.returns = renderReturns;
  RENDERERS.cashshifts = renderCashShifts;
  RENDERERS.shoporders = renderShopOrders;

  /* ---------- Delegatsiya: tugmalar (bindContentEvents'ga tegmasdan) ---------- */
  document.addEventListener("click", async (ev) => {
    const btn = ev.target.closest("[data-v5-cancel-order]");
    if (btn) {
      const num = btn.dataset.v5CancelOrder;
      if (!confirm(`Sotuv ${num} bekor qilinsinmi?`)) return;
      try {
        const r = await api(`/orders/${encodeURIComponent(num)}`, { method: "DELETE" });
        if (r.error) throw new Error(r.error);
        toast("✅ Bekor qilindi");
        navigate("sales");
      } catch (e) { toast(e.message, "error"); }
      return;
    }
    const ps = btn || ev.target.closest("[data-v5-prod-status]");
    if (ps) {
      const [id, status] = ps.dataset.v5ProdStatus.split("|");
      try {
        const r = await apiPost(`/production/${id}/status`, { status });
        if (r.error) throw new Error(r.error);
        toast(`✅ Holat: ${status}`);
        navigate("production");
      } catch (e) { toast(e.message, "error"); }
      return;
    }
    const ds = btn || ev.target.closest("[data-v5-del-start]");
    if (ds) {
      try {
        const r = await apiPost(`/deliveries/${ds.dataset.v5DelStart}/start`, {});
        if (r.error) throw new Error(r.error);
        toast("🚀 Yetkazish boshlandi");
        navigate("deliveries");
      } catch (e) { toast(e.message, "error"); }
      return;
    }
    const dd = btn || ev.target.closest("[data-v5-del-done]");
    if (dd) {
      try {
        const r = await apiPost(`/deliveries/${dd.dataset.v5DelDone}/complete`, {});
        if (r.error) throw new Error(r.error);
        toast("✅ Yetkazildi");
        navigate("deliveries");
      } catch (e) { toast(e.message, "error"); }
      return;
    }
    const dc = btn || ev.target.closest("[data-v5-del-cancel]");
    if (dc) {
      if (!confirm("Yetkazish bekor qilinsinmi?")) return;
      try {
        const r = await apiPost(`/deliveries/${dc.dataset.v5DelCancel}/cancel`, {});
        if (r.error) throw new Error(r.error);
        toast("Bekor qilindi");
        navigate("deliveries");
      } catch (e) { toast(e.message, "error"); }
      return;
    }
    const sg = btn || ev.target.closest("[data-v5-del-sign]");
    if (sg) { v5DeliverySignature(sg.dataset.v5DelSign); return; }
    const loc = btn || ev.target.closest("[data-v5-del-loc]");
    if (loc) { v5DeliveryLocation(loc.dataset.v5DelLoc); return; }
    const sc = btn || ev.target.closest("[data-v5-shop-cancel]");
    if (sc) {
      if (!confirm("Do'kon buyurtmasi bekor qilinsinmi?")) return;
      try {
        const r = await apiPost(`/shop-orders/${sc.dataset.v5ShopCancel}/cancel`, {});
        if (r.error) throw new Error(r.error);
        toast("✅ Bekor qilindi");
        navigate("shoporders");
      } catch (e) { toast(e.message, "error"); }
      return;
    }
  });
})();