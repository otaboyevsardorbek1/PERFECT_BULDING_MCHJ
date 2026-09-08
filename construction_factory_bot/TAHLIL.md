# 🏗️ TIZIM TAHLILI VA YANGILASH HISOBOTI

> Sanalar: 2026-09-04
> Asos: `construction_factory_bot.txt` (9 457 qatorlik to'liq texnik topshiriq)
> Natija: **530 ta test o'tdi** (avval 515 ta), tizim hatolarsiz ishga tushadi

---

## 1. 📊 Mavjud tizim tahlili (TZ bilan solishtirish)

### 1.1 Nima ishlab chiqilgan (v3.0 asosida)

| TZ moduli | Bot | API | Web UI | Holat |
| :--- | :-: | :-: | :-: | :--- |
| Mahsulot katalogi + o'lchov birliklari konvertatsiyasi | ✅ | ✅ | ✅ | Ishlamoqda |
| Ta'minot va qabul qilish (sifat nazorati akti, kamomad) | ✅ | ✅ | ✅ | Ishlamoqda |
| Rezervatsiya (2–24 soat, avto-yechish) | ✅ | ✅ | ✅ | Ishlamoqda |
| Omborlararo ko'chirish + inventarizatsiya | ✅ | ✅ | ✅ | Ishlamoqda |
| Sotuv (nasiya, chegirma, aralash to'lov) | ✅ | — | ✅ | Ishlamoqda |
| Qaytarish akti (pul/almashtirish/bonus) | ✅ | ✅ | — | Ishlamoqda |
| Yetkazib berish + GPS kuzatuv (haydovchi) | ✅ | ✅ | — | Ishlamoqda |
| CRM (mijoz kartasi, qarz FIFO, ballar) | ✅ | ✅ | ✅ | Ishlamoqda |
| Moliya: P&L, soliq kalkulyatori, qarz hisobotlari | ✅ | ✅ | ✅ | Ishlamoqda |
| Ishlab chiqarish + sifat nazorati (QC) | ✅ | ✅ | — | Ishlamoqda |
| Smena (kassa) — ochish/yopish, naqd farq | ✅ | ✅ | — | Ishlamoqda |
| Ommaviy web-do'kon (catalog + savat + checkout) | — | ✅ | ✅ | Ishlamoqda |
| Click/Payme onlayn to'lovlar | — | ✅ | — | Ishlamoqda |
| Qarz SMS eslatmalari (3/7/14/30 kun) | ✅ (avto) | — | — | Ishlamoqda |
| Sekin sotiladigan zaxira ogohlantirishi | ✅ (avto) | — | — | Ishlamoqda |
| Avtomatik backup + bulutga yuklash + shifrlash | ✅ | ✅ | ✅ | Ishlamoqda |
| Rollar matritsasi (direktor…ishchi) | ✅ | ✅ | ✅ | Ishlamoqda |
| Web auth (parol, refresh token, parolni tiklash) | — | ✅ | ✅ | Ishlamoqda |

### 1.2 TZ dagi muhim mezonlar bilan moslik

| TZ talabi | Holat |
| :--- | :--- |
| "Sotuvchi tannarxni ko'ra olmaydi" (see_cost) | ✅ Server tomonda kesiladi (CostVisibilityMiddleware) |
| "Omborchi narxlarni ko'ra olmaydi" | ✅ Rol matritsasi (omborchi see_cost=false) |
| "Katta chegirma — direktor tasdig'i" (ikki bosqichli tasdiq) | ⚠️ Qisman: limit bor, endi direktor ogohlantirishi qo'shildi |
| "Mijoz triaji — Oltin/Kumush/Bronza" | ❌ → ✅ Yangi qo'shildi |
| "O'xshash mahsulot taklifi (bu g'ishtga mos sement)" | ❌ → ✅ Yangi qo'shildi |
| "Har kuni ertalab direktor kunlik digesti" | ⚠️ → ✅ Boyitildi (qarz, kechikkan, zaxira bilan) |
| "Har bir operatsiyaga unikal tranzaksiya kodi" | ✅ Document raqamlari (INV-/PO-/SQC-…) |
| "Xatomni o'chirilmaydigan tarzda saqlash" | ✅ WarehouseTransaction + SystemLog audit |
| "Qaytarish — 7 kun qoidasi" | ✅ RETURN_PERIOD_DAYS=7 |
| "Sodiqlik ballari faqat olingan pulga" | ✅ Har 100 000 so'm = 1 ball |

---

## 2. 🐞 Topilgan va tuzatilgan xatolar

Testlar o'tayotgan bo'lsa ham, **bot ishga tushishini buzadigan 2 ta kritik xato** bor edi:

### 2.1 `handlers/cash_shift.py` — SyntaxError (kritik)
- **Muammo:** 104-qatorda f-string ichida noto'g'ri qochirilgan apostrof — `'🔴 Ochiq smena yo\\'q'`
- **Natija:** `main.py` botni ishga tushirganda `from handlers.cash_shift import …` import'ida **yiqilardi**.
- **Sabab:** Testlar faqat `crud`/API qatlamini sinagan, handler faylini import qilmagan.
- **Yechim:** Qatordan noto'g'ri qochirish olib tashlandi (f-string ichida o'zgaruvchiga o'tkazildi).

### 2.2 `utils/notifications.py` — NameError: `func` (runtime)
- **Muammo:** `check_delivery_notifications`, `send_daily_report`, `send_monthly_report` funksiyalarida `func.date`/`func.sum` ishlatilgan, lekin `from sqlalchemy import func` **modul darajasida import qilinmagan** (faqat bitta funksiya ichida local import bor edi).
- **Natija:** Rejali hisobot/digest chaqirilganda `NameError` berardi.
- **Yechim:** `func` importi modul darajasiga ko'chirildi, ortiqcha local import olib tashlandi.

### 2.3 Boshqa tekshiruvlar
- ✅ Barcha 41 ta modul import qilindi — xato yo'q
- ✅ `py_compile` — barcha fayllar sintaksis toza
- ✅ Node.js `server.js` va `app.js` — sintaksis toza, server HTTP 200 qaytaradi
- ✅ FastAPI — barcha marshrutlar ro'yxatda, auth qatlami ishlaydi (401 -> login)

---

## 3. ✨ Yangi qo'shilgan funksiyalar (TZ asosida)

### 3.1 🏅 Mijoz triaji — Oltin / Kumush / Bronza (TZ: CRM bo'limi)
- **Logika:** jami xarid >= 50 mln so'm → Oltin; >= 10 mln → Kumush; qolganlar — Bronza.
- **Qoidalar:** qarz xaridning 50% dan oshsa daraja pasayadi; muddati o'tgan qarzi bo'lsa — Bronza.
- **Chegaralar .env orqali:** `CUSTOMER_TIER_GOLD_THRESHOLD`, `CUSTOMER_TIER_SILVER_THRESHOLD`
- **Kirish nuqtalari:**
  - Bot: mijoz kartasida toifa, CRM statistikada segmentatsiya
  - API: `GET /api/customers/segmentation` (yangilangan `customer_to_dict` da `tier`/`tier_label`)
  - Web: CRM sahifasida rangli toifa badge'lari + segmentatsiya paneli
- **Fayllar:** `database/crud.py`, `handlers/customers.py`, `dashboard/api_v3.py`, `web/public/app.js`, `web/public/style.css`

### 3.2 💡 O'xshash mahsulot taklifi (TZ: "bu g'ishtga mos sement va armatura")
- **Logika:** bir xil kategoriya + faol + omborda qoldig'i bor mahsulotlar; kategoriya bo'sh bo'lsa — narxi yaqin mahsulotlar.
- **Kirish nuqtalari:**
  - Bot: sotuvda mahsulot tanlanganda inline tugmalar bilan taklif (almashtirish yoki asosiy bilan davom etish)
  - API: `GET /api/products/{id}/related`
- **Fayllar:** `database/crud.py`, `handlers/sales.py`, `dashboard/api_v3.py`

### 3.3 🚨 Katta chegirma — direktor ogohlantirishi (TZ: ikki bosqichli tasdiq)
- Rol limitidan ortiq chegirma berishga urinish endi:
  1) sotuvni bloklaydi (avvalgi qoida),
  2) direktor(lar)ga Telegram ogohlantirishi yuboradi,
  3) `SystemLog` audit'ga yozadi ("Chegirma limitidan oshish urinishi").
- **Fayl:** `handlers/sales.py`

### 3.4 📊 Direktor kunlik digesti boyitildi (TZ: "har kuni ertalab 8:00")
Endi kundalik hisobot quyidagilarni o'z ichiga oladi:
- Sotuvlar soni, daromad, nasiyaga sotilgan qism
- Eng ko'p sotilgan mahsulot
- Kechiktirilgan nasiya qarzlari (sotuvlar soni, jami summa, mijozlar)
- Past zaxira (xom ashyo + tugagan mahsulotlar)
- Bugun tugashi kerak bo'lgan ishlab chiqarish buyurtmalari
- **Fayl:** `utils/notifications.py`

---

## 4. 🧪 Test natijalari

| Ko'rsatkich | Qiymat |
| :--- | :--- |
| Avval | 515 passed |
| Yangi testlar | +15 (mijoz triaji, o'xshash mahsulot, API endpointlar) |
| Hozir | **530 passed** |

Yangi test fayli: `tests/test_database/test_customer_tier.py` (13 test) + `tests/test_api/test_api_v3.py` (+2 test)

---

## 5. 🚀 Ishga tushirish (o'zgarmagan)

```bash
# 1) Backend + Bot
pip install -r requirements.txt
cp .env.example .env   # BOT_TOKEN, ADMIN_IDS kiriting
python -m uvicorn dashboard.app:app --port 8000   # REST API
python main.py                                     # Telegram bot

# 2) Web frontend (Node.js, zero-dependency)
cd web && PORT=3000 PY_API_URL=http://127.0.0.1:8000 node server.js
# Brauzer: http://localhost:3000
```

## 6. ✅ Keyingi qadamlar — bajarildi (v4.1)

| Qadam | Holat | Qayerda |
| :--- | :--- | :--- |
| **Rate limiting** | ✅ Bajarildi | `dashboard/app.py` RateLimitMiddleware (IP+yo'l bo'yicha, login uchun 10/min) |
| **Xodim avans hisoboti** | ✅ Bajarildi | `models.ExpenseReport`, `crud.create_expense_report`, bot + `/api/expenses/*` + Web UI |
| **Yoqilg'i nazorati** | ✅ Bajarildi | `models.FuelLog`, `crud.get_fuel_efficiency` (L/100km, me'yor tekshiruvi), bot + `/api/fuel/*` + Web UI |
| **Picking list / yig'ish varaqasi** | ✅ Bajarildi | `models.PickingList`, bot + `/api/picking/*` + Web UI (sektor bilan) |
| **Docker + CI/CD** | ✅ Bajarildi | `Dockerfile`, `docker-compose.yml` (api/web/bot), `.github/workflows/ci.yml` (pytest + Node + build) |
| **Shubhali harakat detektori** | ✅ Bajarildi | `models.SuspiciousActivity` + `/api/security/*` + Web UI |
| **Sotuvchilar reytingi** | ✅ Bajarildi | `crud.get_seller_ratings` + `/api/sellers/ratings` + Web UI |
| **Xodim ish vaqti** | ✅ Bajarildi | `handlers/employees.py` (kirish/chiqish, overtime) |
| **Web UI (operatsion modullar)** | ✅ Bajarildi | `web/public/index.html` + `app.js` — 5 ta yangi sahifa |

---

## 7. 📊 v4.0/4.1 natijalari

- **568 ta test o'tdi** (v4 bot-auth testlari bilan birga)
- Bot: `/login`, `/sessiya`, `/logout`, `/parol` — sessiya 5–30 daqiqa, tugaganda barcha darajalar bekor
- Web: qisqa muddatli access token + refresh (sliding) + idle timeout + logout revoke
- Operatsion modullar endi bot, API va Web dashboard'da bir xil ishlaydi
- Docker + GitHub Actions CI loyihaga qo'shildi

---

## 8. 🔢 v4.2 — 2FA: Google Authenticator (TZ: "Direktor va kassir uchun")

| Qadam | Holat | Qayerda |
| :--- | :--- | :--- |
| **TOTP yadro (RFC 6238)** | ✅ Bajarildi | `utils/totp.py` — secret, kod, tekshirish (±30s oyna), otpauth URI, QR (qrcode) |
| **DB ustunlari** | ✅ Bajarildi | `Employee.otp_secret`/`otp_enabled` + `EXTRA_COLUMNS` migratsiyasi |
| **Bot `/2fa`** | ✅ Bajarildi | Yoqish: QR rasm + secret, kod bilan tasdiqlash; o'chirish: joriy kod talab |
| **Bot `/login`** | ✅ Bajarildi | 2FA yoqilgan xodim paroldan keyin `waiting_otp` bosqichida kod kiritadi |
| **Web `/login`** | ✅ Bajarildi | Parol -> `issue_2fa_pending_token` (5 daq) -> otp formasi -> sessiya |
| **API `/api/login`** | ✅ Bajarildi | 2FA yoqilgan bo'lsa `otp_code` talab (kodsiz 428, noto'g'ri 401) |
| **API `/api/auth/2fa/*`** | ✅ Bajarildi | `setup` (secret+QR), `enable`, `disable` — kod bilan; `/api/me` da `two_fa_enabled` |
| **Web UI** | ✅ Bajarildi | Login'da 2-bosqich forma; Xavfsizlik sahifasida yoqish/o'chirish (QR modal) |
| **Testlar** | ✅ Bajarildi | `tests/test_api/test_2fa.py` — 14 test (TOTP + API + web login) |

**Natija: 582 ta test o'tdi** (568 + 14 yangi).

---

## 9. 🔍 v5 — Spec'ning REST API ro'yxati va qolgan funksiyalar to'liq tekshirildi

> Audit: `construction_factory_bot.md` (9 457 qator) ning barcha funksional bo'limlari
> kod bilan solishtirildi; **etishmayotgan REST API endpointlari, narx tarixi,
> web UI sahifalari va PWA qo'shildi.**

### 9.1 Yangi qo'shilgan qismlar

| Modul | Nima qo'shildi | Qayerda |
| :--- | :--- | :--- |
| **REST API (spec 2-bo'lim)** | `dashboard/api_v5.py` — spec'ga mos 70+ endpoint | `/api/*` |
| **Narx tarixi (TZ: "Sana bo'yicha")** | `ProductPriceHistory` jadvali, `record_price_change`, API + bot "💱 Narx tarixi" | `models`, `crud_v5`, `api_v5`, `handlers/warehouse` |
| **Omborlar (Warehouses CRUD)** | `Warehouse` jadvali + GET/POST/PUT `/api/warehouses` | `models`, `crud_v5`, `api_v5` |
| **Web UI — 6 ta yangi sahifa** | 💰 Sotuv (POS), 🏭 Ishlab chiqarish, 🚚 Yetkazib berish, ↩️ Qaytarish, 💵 Smena, 🛒 Do'kon buyurtmalari | `web/public/app_v5.js` |
| **PWA (TZ: Mobil versiya)** | `manifest.json` + `sw.js` (offline rejim, network-first) | `web/public/` |

### 9.2 Spec API ro'yxati bo'yicha holat

| Spec endpoint guruhi | Holat |
| :--- | :--- |
| Auth (`/api/auth/login|logout|refresh|profile|register|verify-2fa`) | ✅ `api_v5` |
| Users (CRUD + status + parol) | ✅ `api_v5` |
| Products (CRUD, search, import, price→tarix, stock, low-stock, top-selling) | ✅ `api_v5` |
| Categories (CRUD) | ✅ `api_v5` |
| Customers (update, credit, debtors, orders) | ✅ `api_v5` |
| Orders (sotuv yaratish, status, reserve, cancel) | ✅ `api_v5` |
| Payments (list, create, daily) | ✅ `api_v5` |
| Inventory (list, product, adjust, history) | ✅ `api_v5` |
| Deliveries (imzo/signature) | ✅ `api_v5` |
| Reports (daily/weekly/monthly/yearly/PL/debt/top-customers/category/export) | ✅ `api_v5` |
| Suppliers (update, purchases) | ✅ `api_v5` |
| Production (list, create, status) | ✅ `api_v5` |
| Warehouses (CRUD) | ✅ `api_v5` |

### 9.3 Natija

- **603 ta test o'tdi** (582 + 21 yangi `tests/test_api/test_api_v5.py`)
- Barcha modullar import toza, `node --check` toza
- Router tartibi: `api_v5` avval ro'yxatdan o'tadi — literal yo'llar
  (`/customers/debtors`, `/orders/sales`, `/inventory/history`) parametrli
  yo'llardan ustun turadi
- `CostVisibilityMiddleware` tannarx maydonlarini `see_cost=False` rollar uchun
  kesishda davom etadi (yangi endpointlarda ham)

### 9.4 Roadmap (spec'ning tashqi infratuzilma qismlari)

Spec'dagi quyidagi bo'limlar bulut infratuzilmasi (K8s, Terraform, Helm,
ArgoCD, Istio, OPA, monitoring stack) uchun namunaviy kodlar — ular mahalliy
SQLite/PostgreSQL tizimiga tegishli emas va `PROJECT_GUIDE.md` "Kelajak"
ro'yxatida saqlanadi. Ularni talab qilsangiz, alohida loyiha sifatida ishlab
berish mumkin.