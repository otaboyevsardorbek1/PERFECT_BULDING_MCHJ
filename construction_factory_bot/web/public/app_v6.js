/*
 * app_v6.js — Event Sourcing + CQRS web dashboard (v6.0)
 *
 * 📜 Event Sourcing — audit log, event tarixi, replay, integrity
 * 📊 CQRS Dashboard — read model, statistika, real-vaqt
 *
 * app.js dagi global yordamchilardan foydalanadi: api, apiPost, apiGet,
 * esc, toast, cards, panel, badge, empty, navigate, PAGES, PAGE_MODULES.
 */
(function () {
  if (typeof PAGES === "undefined") return;

  /* ---------- Sahifalarni ro'yxatga olish ---------- */
  PAGES.events = "📜 Event Sourcing";
  PAGES.cqrs = "📊 CQRS Dashboard";

  PAGE_MODULES.events = "admin";
  PAGE_MODULES.cqrs = "admin";

  const money = (n) => (Number(n) || 0).toLocaleString("uz-UZ") + " so'm";
  const fmtDate = (iso) => {
    if (!iso) return "-";
    const d = new Date(iso);
    return d.toLocaleString("uz-UZ", { dateStyle: "short", timeStyle: "short" });
  };
  const fmtNum = (n) => new Intl.NumberFormat("uz-UZ").format(Number(n || 0));
  const trunc = (s, len = 40) => {
    const t = String(s || "");
    return t.length > len ? t.slice(0, len) + "…" : t;
  };

  // Event type → rang xaritasi
  const EVENT_COLORS = {
    SaleCreated: "green", SaleCancelled: "red",
    PaymentReceived: "blue", ReturnCreated: "yellow",
    StockIncreased: "green", StockDecreased: "red",
    PriceChanged: "purple", CustomerCreated: "blue",
    ReservationCreated: "yellow", ReservationReleased: "gray",
  };

  /* ================= 📜 EVENT SOURCING ================= */

  async function renderEvents() {
    const [statsData, eventsData] = await Promise.all([
      apiGet("/events/stats?limit=5").catch(() => ({})),
      apiGet("/events?limit=30").catch(() => ({ events: [], count: 0 })),
    ]);

    // Umumiy kartochkalar
    const summary = cards([
      { icon: "📜", label: "Jami eventlar", value: fmtNum(statsData.total_events || 0) },
      { icon: "📸", label: "Snapshot'lar", value: fmtNum(statsData.snapshot_count || 0) },
      { icon: "📊", label: "Read modellar", value: fmtNum(statsData.read_model_count || 0) },
      { icon: "🔢", label: "So'nggi sequence", value: statsData.last_event ? `#${fmtNum(statsData.last_event.sequence)}` : "—" },
    ]);

    // Event turlari statistikasi
    const typeStatsHtml = (statsData.event_types || []).map(et =>
      `<tr>
        <td>${badge(et.type, EVENT_COLORS[et.type] || "gray")}</td>
        <td style="text-align:right">${fmtNum(et.count)}</td>
        <td>
          <div style="background:#1e293b;border-radius:4px;height:8px;width:100%;overflow:hidden">
            <div style="background:#3b82f6;height:100%;width:${Math.min(100, et.count * 100 / Math.max(statsData.total_events || 1, 1))}%"></div>
          </div>
        </td>
      </tr>`
    ).join("");

    // Aggregate'lar bo'yicha
    const aggStatsHtml = (statsData.aggregates || []).map(a =>
      `<tr>
        <td>${badge(a.type, "blue")}</td>
        <td style="text-align:right">${fmtNum(a.entities)}</td>
        <td style="text-align:right">${fmtNum(a.events)}</td>
      </tr>`
    ).join("");

    // Oxirgi event tarixi
    const eventsHtml = (eventsData.events || []).map(e => {
      const meta = e.metadata || {};
      const dataStr = trunc(JSON.stringify(e.event_data || {}));
      return `<tr>
        <td style="font-family:monospace;font-size:.8em">#${fmtNum(e.sequence)}</td>
        <td>${badge(e.event_type, EVENT_COLORS[e.event_type] || "gray")}</td>
        <td>${badge(e.aggregate_type, "blue")}</td>
        <td>${fmtNum(e.aggregate_id)}</td>
        <td style="font-size:.85em" title="${esc(JSON.stringify(e.event_data || {}))}">${esc(dataStr)}</td>
        <td style="font-size:.85em">${esc(meta.user_name || "—")}</td>
        <td style="font-size:.85em">${fmtDate(e.occurred_at)}</td>
        <td>
          <button class="btn btn-small btn-outline" data-v6-replay="${e.aggregate_type}/${e.aggregate_id}">🔄 Replay</button>
        </td>
      </tr>`;
    }).join("");

    return summary + `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        ${panel("📊 Event turlari bo'yicha",
          `<div class="table-wrap"><table><thead><tr><th>Turi</th><th style="text-align:right">Soni</th><th>Nisbat</th></tr></thead>
          <tbody>${typeStatsHtml || `<tr><td colspan="3">${empty("Eventlar yo'q")}</td></tr>`}</tbody></table></div>`
        )}
        ${panel("📦 Aggregate'lar bo'yicha",
          `<div class="table-wrap"><table><thead><tr><th>Turi</th><th style="text-align:right">Ob'ektlar</th><th style="text-align:right">Event'lar</th></tr></thead>
          <tbody>${aggStatsHtml || `<tr><td colspan="3">${empty("Ma'lumot yo'q")}</td></tr>`}</tbody></table></div>`
        )}
      </div>

      ${panel("📜 Oxirgi event'lar (30 ta)",
        `<div class="table-wrap"><table><thead><tr>
          <th>Seq</th><th>Turi</th><th>Obyekt</th><th>ID</th>
          <th>Ma'lumot</th><th>Foydalanuvchi</th><th>Vaqt</th><th></th>
        </tr></thead><tbody>${eventsHtml || `<tr><td colspan="8">${empty("Eventlar yo'q")}</td></tr>`}</tbody></table></div>`
      )}

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        ${panel("🔍 Integrity tekshirish",
          `<div style="padding:8px 0">
            <p style="color:#94a3b8;font-size:.9em">Event zanjirining checksum'larini tekshirish — hech qanday event o'zgartirilmaganini ta'minlaydi.</p>
            <button class="btn btn-primary" onclick="v6CheckIntegrity()" style="margin-top:8px">🔎 Tekshirish</button>
            <div id="v6-integrity-result" style="margin-top:12px"></div>
          </div>`
        )}
        ${panel("🔄 Read Model yangilash",
          `<div style="padding:8px 0">
            <p style="color:#94a3b8;font-size:.9em">CQRS read model'larni event store'dan qayta hisoblash. Dashboard ma'lumotlarini yangilaydi.</p>
            <button class="btn btn-primary" onclick="v6RefreshReadModels()" style="margin-top:8px">🔄 Yangilash</button>
            <div id="v6-refresh-result" style="margin-top:12px"></div>
          </div>`
        )}
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        ${panel("📸 Snapshot boshqaruvi",
          `<div style="padding:8px 0">
            <div class="form-grid" style="margin-bottom:12px">
              <label>Obyekt turi
                <select id="v6-snap-type">
                  <option value="sale">sale (sotuv)</option>
                  <option value="product">product (mahsulot)</option>
                  <option value="customer">customer (mijoz)</option>
                  <option value="warehouse">warehouse (ombor)</option>
                </select>
              </label>
              <label>Obyekt ID <input id="v6-snap-id" type="number" min="1" value="1"></label>
            </div>
            <button class="btn btn-primary" onclick="v6CreateSnapshot()">📸 Snapshot yaratish</button>
            <div id="v6-snapshot-result" style="margin-top:12px"></div>
          </div>`
        )}
        ${panel("🔄 Event Replay",
          `<div style="padding:8px 0">
            <p style="color:#94a3b8;font-size:.9em">Obyektning barcha event'larini qayta o'ynatib, joriy holatini tiklash.</p>
            <div class="form-grid" style="margin-top:8px">
              <label>Obyekt turi
                <select id="v6-replay-type">
                  <option value="sale">sale</option>
                  <option value="product">product</option>
                  <option value="customer">customer</option>
                </select>
              </label>
              <label>Obyekt ID <input id="v6-replay-id" type="number" min="1" value="1"></label>
            </div>
            <button class="btn btn-primary" onclick="v6Replay()" style="margin-top:8px">🔄 Replay</button>
            <div id="v6-replay-result" style="margin-top:12px"></div>
          </div>`
        )}
      </div>
    `;
  }

  /* ================= 📊 CQRS DASHBOARD ================= */

  async function renderCqrs() {
    const [dashStats, eventTypeStats, aggStats, hourlyData] = await Promise.all([
      apiGet("/cqrs/dashboard_stats").catch(() => null),
      apiGet("/cqrs/event_type_stats").catch(() => null),
      apiGet("/cqrs/aggregate_stats").catch(() => null),
      apiGet("/cqrs/hourly_events").catch(() => null),
    ]);

    const ds = dashStats ? dashStats.data : {};
    const ets = eventTypeStats ? eventTypeStats.data : {};
    const ags = aggStats ? aggStats.data : {};
    const hd = hourlyData ? hourlyData.data : {};

    // Asosiy statistika
    const summary = cards([
      { icon: "📜", label: "Jami eventlar", value: fmtNum(ds.total_events || 0) },
      { icon: "🛒", label: "Sotuv event'lari", value: fmtNum(ds.total_sales_events || 0) },
      { icon: "👥", label: "Mijozlar yaratilgan", value: fmtNum(ds.total_customers_created || 0) },
      { icon: "↩️", label: "Qaytarishlar", value: fmtNum(ds.total_returns || 0) },
    ]);

    // Event turlari pie chart (CSS bilan)
    const etEntries = Object.entries(ets.event_types || {});
    const totalEvents = etEntries.reduce((sum, [, v]) => sum + v, 0);
    const typeChartHtml = etEntries.map(([type, count]) => {
      const pct = totalEvents > 0 ? (count * 100 / totalEvents).toFixed(1) : 0;
      const color = EVENT_COLORS[type] || "#6b7280";
      return `<div style="display:flex;align-items:center;gap:8px;margin:4px 0">
        <div style="width:12px;height:12px;border-radius:3px;background:${color};flex-shrink:0"></div>
        <span style="flex:1;font-size:.9em">${esc(type)}</span>
        <span style="font-weight:600">${fmtNum(count)}</span>
        <span style="color:#94a3b8;font-size:.8em;width:50px;text-align:right">${pct}%</span>
      </div>`;
    }).join("");

    // Aggregate'lar ro'yxati
    const aggEntries = Object.entries(ags.aggregates || {});
    const aggHtml = aggEntries.map(([type, count]) =>
      `<div style="display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1e293b">
        <span>${badge(type, "blue")}</span>
        <span style="font-weight:600">${fmtNum(count)} ob'ekt</span>
      </div>`
    ).join("");

    // Soatlik event grafigi (horizontal bar chart)
    const hours = hd.hours || [];
    const maxHourCount = Math.max(...hours.map(h => h.count), 1);
    const hourlyHtml = hours.map(h => {
      const pct = (h.count * 100 / maxHourCount).toFixed(0);
      const hour = h.hour ? h.hour.split(" ")[1] || h.hour : "—";
      return `<div style="display:flex;align-items:center;gap:8px;margin:3px 0">
        <span style="width:50px;font-size:.85em;color:#94a3b8">${hour}</span>
        <div style="flex:1;background:#1e293b;border-radius:4px;height:20px;overflow:hidden">
          <div style="background:linear-gradient(90deg,#3b82f6,#8b5cf6);height:100%;width:${pct}%;min-width:2px;border-radius:4px;transition:width .5s"></div>
        </div>
        <span style="width:40px;text-align:right;font-size:.85em;font-weight:600">${fmtNum(h.count)}</span>
      </div>`;
    }).join("");

    return summary + `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        ${panel("📊 Event turlari nisbati",
          typeChartHtml || empty("Ma'lumot yo'q")
        )}
        ${panel("📦 Aggregate turlari",
          aggHtml || empty("Ma'lumot yo'q")
        )}
      </div>

      ${panel("📈 Soatlik event'lar (oxirgi 24 soat)",
        hourlyHtml || empty("Soatlik ma'lumot yo'q"),
        `<button class="btn btn-small btn-outline" onclick="navigate('events')">📜 Batafsil</button>`
      )}

      ${panel("🔄 Read Model holati",
        `<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px">
          <div style="padding:12px;background:#0f172a;border-radius:8px;border:1px solid #1e293b">
            <div style="font-size:.85em;color:#94a3b8">dashboard_stats</div>
            <div style="font-weight:700;margin-top:4px">${ds.last_refreshed ? "✅ Yangilangan" : "⚠️ Yangilanmagan"}</div>
            <div style="font-size:.8em;color:#64748b;margin-top:4px">${ds.last_refreshed ? fmtDate(ds.last_refreshed) : "—"}</div>
          </div>
          <div style="padding:12px;background:#0f172a;border-radius:8px;border:1px solid #1e293b">
            <div style="font-size:.85em;color:#94a3b8">event_type_stats</div>
            <div style="font-weight:700;margin-top:4px">${ets.total ? `${fmtNum(ets.total)} ta event` : "⚠️ Bo'sh"}</div>
          </div>
          <div style="padding:12px;background:#0f172a;border-radius:8px;border:1px solid #1e293b">
            <div style="font-size:.85em;color:#94a3b8">aggregate_stats</div>
            <div style="font-weight:700;margin-top:4px">${aggEntries.length > 0 ? `${aggEntries.length} ta tur` : "⚠️ Bo'sh"}</div>
          </div>
        </div>
        <div style="margin-top:12px">
          <button class="btn btn-primary" onclick="v6RefreshCqrs()">🔄 Read model'larni yangilash</button>
          <span id="v6-cqrs-result" style="margin-left:12px"></span>
        </div>`
      )}
    `;
  }

  /* ================= GLOBAL FUNKSIYALAR ================= */

  // Integrity tekshirish
  window.v6CheckIntegrity = async function () {
    const el = document.getElementById("v6-integrity-result");
    el.innerHTML = "<span style='color:#94a3b8'>Tekshirilmoqda...</span>";
    try {
      const r = await apiPost("/events/integrity", { from_sequence: 0 });
      if (r.is_valid) {
        el.innerHTML = `<div style="padding:10px;background:#064e3b;border-radius:8px;border:1px solid #059669">
          <strong style="color:#34d399">✅ Integrity to'g'ri!</strong><br>
          <span style="font-size:.9em;color:#94a3b8">${fmtNum(r.total_checked)} ta event tekshirildi, hech qanday xatolik topilmadi.</span>
        </div>`;
      } else {
        el.innerHTML = `<div style="padding:10px;background:#7f1d1d;border-radius:8px;border:1px solid #dc2626">
          <strong style="color:#fca5a5">❌ Integrity xatosi!</strong><br>
          <span style="font-size:.9em;color:#94a3b8">${fmtNum(r.broken_count)} ta buzilgan event aniqlandi (${fmtNum(r.total_checked)} ta dan).</span>
        </div>`;
      }
    } catch (e) {
      el.innerHTML = `<div style="padding:10px;background:#7f1d1d;border-radius:8px;border:1px solid #dc2626">
        <strong style="color:#fca5a5">❌ Xatolik: ${esc(e.message)}</strong>
      </div>`;
    }
  };

  // Read model yangilash
  window.v6RefreshReadModels = async function () {
    const el = document.getElementById("v6-refresh-result");
    el.innerHTML = "<span style='color:#94a3b8'>Yangilanmoqda...</span>";
    try {
      const r = await apiPost("/cqrs/refresh", {});
      el.innerHTML = `<div style="padding:8px;background:#064e3b;border-radius:6px;border:1px solid #059669;color:#34d399;font-size:.9em">
        ✅ ${esc(r.message || "Read model'lar yangilandi")}
      </div>`;
      toast("✅ Read model'lar yangilandi");
    } catch (e) {
      el.innerHTML = `<div style="padding:8px;background:#7f1d1d;border-radius:6px;border:1px solid #dc2626;color:#fca5a5;font-size:.9em">
        ❌ ${esc(e.message)}
      </div>`;
    }
  };

  // Snapshot yaratish
  window.v6CreateSnapshot = async function () {
    const el = document.getElementById("v6-snapshot-result");
    const aggType = document.getElementById("v6-snap-type").value;
    const aggId = parseInt(document.getElementById("v6-snap-id").value) || 1;
    el.innerHTML = "<span style='color:#94a3b8'>Yaratilmoqda...</span>";
    try {
      const r = await apiPost("/snapshots/create", {
        aggregate_type: aggType,
        aggregate_id: aggId,
      });
      el.innerHTML = `<div style="padding:8px;background:#064e3b;border-radius:6px;border:1px solid #059669;color:#34d399;font-size:.9em">
        ✅ Snapshot yaratildi: ${esc(r.aggregate)} | ${fmtNum(r.event_count)} ta event | seq #${fmtNum(r.last_sequence)}
      </div>`;
      toast("📸 Snapshot yaratildi");
    } catch (e) {
      el.innerHTML = `<div style="padding:8px;background:#7f1d1d;border-radius:6px;border:1px solid #dc2626;color:#fca5a5;font-size:.9em">
        ❌ ${esc(e.message)}
      </div>`;
    }
  };

  // Event replay
  window.v6Replay = async function (aggType, aggId) {
    const el = document.getElementById("v6-replay-result");
    if (!aggType) aggType = document.getElementById("v6-replay-type").value;
    if (!aggId) aggId = parseInt(document.getElementById("v6-replay-id").value) || 1;
    el.innerHTML = "<span style='color:#94a3b8'>Replay qilinmoqda...</span>";
    try {
      const r = await apiPost("/events/replay", {
        aggregate_type: aggType,
        aggregate_id: aggId,
      });
      const stateStr = JSON.stringify(r.state || {}, null, 2);
      el.innerHTML = `<div style="padding:10px;background:#0f172a;border-radius:8px;border:1px solid #1e293b">
        <div style="display:flex;justify-content:space-between;margin-bottom:8px">
          <strong style="color:#34d399">🔄 Replay natijasi</strong>
          <span style="font-size:.85em;color:#94a3b8">${fmtNum(r.events_replayed)} ta event | snapshot: ${r.snapshot_used ? "✅" : "yo'q"}</span>
        </div>
        <pre style="background:#1e293b;padding:10px;border-radius:6px;font-size:.8em;overflow-x:auto;max-height:300px;color:#e2e8f0;margin:0">${esc(stateStr)}</pre>
      </div>`;
    } catch (e) {
      el.innerHTML = `<div style="padding:8px;background:#7f1d1d;border-radius:6px;border:1px solid #dc2626;color:#fca5a5;font-size:.9em">
        ❌ ${esc(e.message)}
      </div>`;
    }
  };

  // CQRS refresh
  window.v6RefreshCqrs = async function () {
    const el = document.getElementById("v6-cqrs-result");
    el.innerHTML = "⏳";
    try {
      await apiPost("/cqrs/refresh", {});
      el.innerHTML = "✅ Yangilandi";
      toast("✅ Read model'lar yangilandi");
      setTimeout(() => { el.innerHTML = ""; }, 2000);
    } catch (e) {
      el.innerHTML = "❌ " + esc(e.message);
    }
  };

  // Ro'yxatdan o'tkazish
  if (typeof RENDERERS !== "undefined") {
    RENDERERS.events = renderEvents;
    RENDERERS.cqrs = renderCqrs;
  }

  // Event'dan replay tugmasi bosilganda
  document.addEventListener("click", function (ev) {
    const btn = ev.target.closest("[data-v6-replay]");
    if (btn) {
      const parts = btn.dataset.v6Replay.split("/");
      window.v6Replay(parts[0], parseInt(parts[1]));
    }
  });
})();
