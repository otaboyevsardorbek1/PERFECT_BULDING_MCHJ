# 🏗️ PERFECT BUILDING MCHJ — Qurilish Korxonasini Boshqarish Tizimi

> 🌐 O'zbek  |  🇷🇺 [Русский](README.ru.md)  |  🇬🇧 [English](README.en.md)

Qurilish materiallari **ishlab chiqarish + ulgurji/chakana savdo + ombor + logistika**
uchun yagona, keng qamrovli avtomatlashtirilgan tizim: **Telegram Bot** orqali
barcha operatsiyalar, **Web dashboard** orqali vizual boshqaruv va **REST API**
orqali integratsiya.

Tizim korxonaning real ish jarayonlari asosida loyihalashtirilgan (to'liq
texnik topshiriq: [`construction_factory_bot.md`](construction_factory_bot.md) — 9 400+ qator),
har bir modul **bot + API + Web UI** uch qatlamda ishlaydi va **rol matritsasi**
hamda **sessiya xavfsizligi** bilan himoyalangan.

| Qatlam | Texnologiya | Port |
| :--- | :--- | :--- |
| 🤖 **Telegram Bot** | Python **aiogram v3.22** (polling) | — |
| 🔌 **REST API (Backend)** | Python **FastAPI** + SQLAlchemy | `8000` |
| 🌐 **Web Frontend** | **Node.js** (zero-dependency server + proxy) | `3000` |
| 💾 **Ma'lumotlar bazasi** | SQLite (default) / PostgreSQL (`USE_POSTGRESQL=true`) | — |

```
 Telegram Bot (aiogram) ────────┐
                                ▼
 Node.js web (web/public) ──/api──▶ FastAPI (:8000) ──▶ SQLite / PostgreSQL
                                ▲
 Click / Payme webhook ─────────┘        (ai_prediction, SMS, backup, scheduler)
```

---

## 📁 Repozitoriy tuzilishi

```
PERFECT_BULDING_MCHJ/
├── construction_factory_bot.md     # 📋 To'liq texnik topshiriq / tahlil hujjati
├── construction_factory_bot/       # ⚙️ Tizimning to'liq implementatsiyasi
│   ├── main.py                     #    Telegram bot (aiogram) — asosiy ishga tushirish
│   ├── config.py                   #    Barcha sozlamalar va .env parametrlari
│   ├── dashboard/                  #    FastAPI backend: app.py, api_v3.py, auth.py,
│   │                               #    payments.py (Click/Payme), shop.py, password_reset.py
│   ├── handlers/                   #    Bot buyruq/modul handlerlari (sales, finance, ...)
│   ├── database/                   #    SQLAlchemy modellar, CRUD, schema upgrade
│   ├── utils/                      #    totp, backup, rate_limit, bot_auth, pdf/excel, charts...
│   ├── web/                        #    Node.js frontend (server.js + public/ SPA)
│   ├── tests/                      #    Pytest testlari (582+)
│   ├── keyboards/                  #    Telegram inline-klaviaturalar
│   ├── Dockerfile                  #    Yagona konteyner (Python 3.11 + Node 20)
│   └── docker-compose.yml          #    api / web / bot xizmatlari
├── .github/workflows/ci.yml        # 🔄 CI: pytest + Node tekshiruvi + Docker build
└── CodeAnalyzer_v1.py              #   Kod tahlil skripti
```

Batafsil texnik hujjatlar:
- 📖 [`construction_factory_bot/README.md`](construction_factory_bot/README.md) — qo'llanma va API ro'yxati
- 📘 [`construction_factory_bot/PROJECT_GUIDE.md`](construction_factory_bot/PROJECT_GUIDE.md) — loyiha yo'riqnomasi
- 📗 [`construction_factory_bot/TAHLIL.md`](construction_factory_bot/TAHLIL.md) — bosqichma-bosqich tahlil natijalari

---

## ✨ Asosiy imkoniyatlar (versiyalar bo'yicha)

### v1–v2 — Yadro (bot + API)
Mahsulot katalogi va o'lchov birliklari (dona/kg/m²/m³/pallet/qop), konvertatsiya
kalkulyatori, xom ashyo/tayyor mahsulot omborlari, ishlab chiqarish buyurtmalari
(BOM/retsept bo'yicha xom ashyo hisobi), sotuv, hisobotlar (Excel/PDF/grafik),
SMS bildirishnomalar, AI yordamchi tahlil.

### v3.0 — Kengaytirilgan modullar (TZ asosida)

| Modul | Bot | API | Web UI |
| :--- | :-: | :-: | :-: |
| 👥 **CRM / Mijozlar** (karta, nasiya limiti, FIFO qarz, ballar) | ✅ | ✅ | ✅ |
| 💰 **Sotuv** (nasiya, oldindan to'lov, **aralash to'lov**, chegirma) | ✅ | — | ✅ |
| 🚚 **Yetkazib beruvchilar** + sifat nazoratli **qabul akti** | ✅ | ✅ | ✅ |
| 🔒 **Rezervatsiya** (2–24 soat, avtomatik yechilish) | ✅ | ✅ | ✅ |
| 🔄 **Omborlararo ko'chirish** (xomashyo/tayyor/brak) | ✅ | ✅ | ✅ |
| 📋 **Inventarizatsiya** (tizim ↔ haqiqiy, kamomad dalolatnomasi) | ✅ | — | ✅ |
| 💱 **Konvertatsiya** (1 pallet = 40 qop = 2000 kg) | ✅ | ✅ | — |
| 📊 **Moliya**: P&L, QQS 12%, aylanma soliq 4%, qarzlar | ✅ | ✅ | ✅ |
| ↩️ **Qaytarish akti** (pul/almashtirish/bonus, 7 kun qoidasi, P&L tuzatish) | ✅ | ✅ | — |
| 🚚 **Yetkazib berish + GPS** (haydovchi, jonli kuzatuv) | ✅ | ✅ | — |
| 🏭 **Ishlab chiqarish** + 🔬 **Sifat nazorati (QC)** aktlari | ✅ | ✅ | ✅ |
| 💳 **Qarz SMS eslatmalari** (3/7/14/30 kun) | ✅ avto | — | — |
| 🕰️ **Sekin sotiladigan zaxira** ogohlantirishlari | ✅ avto | — | — |
| 💾 **Backup/tiklash** (avtomatik, shifrlangan, Telegram/S3 bulutga) | ✅ | ✅ | ✅ |
| 🛒 **Ommaviy web-do'kon** (`/shop.html`, naqd / Click / Payme) | — | ✅ | ✅ |
| 💵 **Kassir smenasi** (naqd farqini hisoblash) | ✅ | ✅ | — |
| 🏅 **Mijoz triaji** (Oltin/Kumush/Bronza) | ✅ | ✅ | ✅ |
| 💡 **O'xshash mahsulot taklifi** + 🚨 katta chegirma blokirovkasi | ✅ | ✅ | — |
| 📊 **Direktor kunlik digesti** | ✅ avto | — | — |

### v4.0 — Xavfsizlik: login/parol + sessiya (5–30 daqiqa) ⭐
TZ talabi: har bir xodim tizimga **parol bilan kiradi**, **5 daqiqadan 30
daqiqagacha** sessiya oladi; sessiya tugaganda yoki logout qilinganda unga
berilgan **barcha darajalar (rol ruxsatlari) avtomatik bekor qilinadi**.

- Bot: `/login` (telefon+parol), `/sessiya`, `/logout`, `/parol`
- Parollar **PBKDF2-HMAC-SHA256** (bot va web bir xil format)
- Xato parol → `BOT_LOGIN_MAX_ATTEMPTS` (3) dan keyin `10` daqiqaga blok
- Harakatsizlik taymeri (`idle_timeout`) sessiyani avtomatik o'ldiradi
- Web: access token `SESSION_MINUTES` (5–30), refresh token rotatsiyali (sliding)
- `POST /api/logout` → sessiya serverda revoke; eski tokenlar ishlamaydi
- Global middleware sessiyasiz barcha bot buyruqlarini bloklaydi
- Eski tizimga ziyon yetkazmaslik uchun `BOT_AUTH_ENABLED=false` — avvalgi rejim

### v4.1 — Operatsion modullar (bot + API + Web UI)

| Modul | Tavsif |
| :--- | :--- |
| ⛽ **Yoqilg'i nazorati** | Litr/narx/spidometr qaydi, L/100km me'yor nazorati |
| 🧾 **Avans (expense) hisobotlari** | Xarajat qaydi → direktor/buxgalter tasdiqlaydi |
| 📦 **Yig'ish varaqasi (picking list)** | Buyurtma bo'yicha omborchi ro'yxati, sektorlar |
| 🚨 **Shubhali harakat detektori** | Tungi sotuv, katta chegirma va h.k. anomaliyalar |
| 🏆 **Sotuvchilar reytingi** | 30 kunlik savdo, chek soni, o'rtacha chek |
| 🕰️ **Xodim ish vaqti** | Kirish/chiqish, ishlagan va qo'shimcha soatlar |

### v4.2 — 2FA: Google Authenticator (TOTP)
Direktor/kassir va istalgan xodim uchun parol + **6 xonali kod**:
- Bot: `/2fa` (QR rasm bilan yoqish/o'chirish), `/login` da kod bosqichi
- Web: `/login` 2 bosqichli (parol → `otp_token` → kod); API `428/401/200`
- `/api/auth/2fa/setup|enable|disable`, `/api/me` da `two_fa_enabled`
- RFC 6238 TOTP (`utils/totp.py`), eski DB avtomatik migratsiya qilinadi

### v5 — To'liq REST API + Narx tarixi + Web sahifalar + PWA
- 70+ endpoint (`dashboard/api_v5.py`): Users, Products (search/import/narx→tarix),
  Categories, Orders (sotuv), Payments, Inventory, Reports (eksport), Suppliers,
  Production, Warehouses, Auth aliaslar
- Narx tarixi (`product_price_history`), 6 ta yangi web sahifa (`app_v5.js`),
  PWA (`manifest.json` + `sw.js`)

### v5.1 — Tranzaksiya kodi + Avans fotosi + Mijoz shifrlash
- 🔖 Har bir sotuv/qaytarish/ombor harakatiga **16 xonali tranzaksiya kodi**;
  `GET /api/documents/lookup?code=...` orqali hujjatni 1 daqiqada topish
- 📎 Avans hisobotiga bot orqali ixtiyoriy **chek fotosurati** yuklash
- 🔒 Mijoz telefon/manzilini **rol bo'yicha yashirish** (sotuvchi maskani ko'radi,
  direktor/haydovchi to'liq)

### v5.2 — Mijoz narxlari + Minimal zaxira + Partiya raqami (spec 3-bo'lim)
- 💰 **Maxsus mijoz narxlari** (`customer_prices`): `GET/PUT/DELETE
  /api/customers/{id}/prices`; sotuvda maxsus narx avtomatik qo'llanadi
- 📉 **Mahsulot `min_stock`** — low-stock hisobotda o'z chegarasi ishlatiladi
- 🔖 **Partiya/sertifikat/amal muddati** xomashyo qabul aktiga yoziladi

### 🐳 v4.x — Docker + CI/CD
`docker-compose up -d --build` — api (:8000), web (:3000), bot — SQLite, backups,
logs shared volume'da. `.github/workflows/ci.yml` — har push/PR da: 621+ test,
Node sintaksis tekshiruvi va Docker build.

---

## 🚀 Ishga tushirish

### 1) Lokal (Python backend + bot)

```bash
cd construction_factory_bot

python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# .env yarating (kamida BOT_TOKEN va ADMIN_IDS):
#   cp .env.example .env   (yoki qo'lda quyidagi minimalni yozing)
#
#   BOT_TOKEN=123456:ABC...
#   ADMIN_IDS=123456789
#   API_SECRET_KEY=uzun-tasodifiy-kalit       # web tokenlar uchun

# 1) REST API (web frontend buni chaqiradi)
python -m uvicorn dashboard.app:app --host 0.0.0.0 --port 8000

# 2) Telegram bot (ayni database bilan)
python main.py
```

### 2) Web frontend (Node.js — qo'shimcha kutubxona kerak emas)

```bash
cd web
PORT=3000 PY_API_URL=http://127.0.0.1:8000 node server.js
```

Brauzerda: **http://localhost:3000** → web dashboard,
**http://localhost:3000/shop.html** → ommaviy web-do'kon.

### 3) Docker (barchasi birdan)

```bash
cd construction_factory_bot
cp .env.example .env    # BOT_TOKEN, ADMIN_IDS kiriting
docker-compose up -d --build
```

### 🔐 Birinchi ishga tushirish: parollar

Xodimlar **telefon raqami + parol** bilan kiradi (bot ham, web ham):

```bash
# Direktor parolni CLI orqali o'rnatishi mumkin:
python -m dashboard.auth set-password --phone +998901234567 --password parol1234

# yoki .env'ga qo'ying (adminlarga avtomatik beriladi):
#   WEB_ADMIN_PASSWORD=parol1234
```

Boshqaruv:
```bash
python -m dashboard.auth list-users      # xodimlar va parol holati
```

---

## 🤖 Telegram Bot — asosiy buyruqlar

| Buyruq | Vazifasi |
| :--- | :--- |
| `/start` `/help` | Ishga tushirish, yordam |
| `/login` | Telefon + parol bilan sessiya ochish (2FA bo'lsa — kod) |
| `/logout` | Sessiyani bekor qilish — darajalar darhol o'chadi |
| `/sessiya` | Sessiya holati (qolgan vaqt, idle taymer) |
| `/parol` | Parolni o'rnatish/o'zgartirish |
| `/2fa` | Google Authenticator yoqish (QR) / o'chirish |
| `/rollar` | Rollar boshqaruvi (direktor) |
| `/cancel` | Joriy amalni bekor qilish |

Qolgan barcha imkoniyatlar **inline-klaviaturalar** orqali (rolga qarab):
👑 Admin paneli (backup, rollar, xodimlar, audit), 🛒 Sotuv, 👥 CRM, 📦 Ombor,
🏭 Ishlab chiqarish, 📊 Hisobotlar, ⛽ Yoqilg'i, 🧾 Avans, 🚚 Yetkazib berish va h.k.

> Har bir xabar/callback sessiya tekshiruvidan o'tadi — sessiyasiz faqat
> `/start`, `/help`, `/cancel`, `/login`, `/logout`, `/sessiya`, `/parol` ishlaydi.

---

## 💳 Onlayn to'lovlar (Click / Payme)

Mijoz nasiya qarzini yoki do'kon buyurtmasini Click/Payme orqali to'laydi:

1. `.env` ga kiriting: `CLICK_MERCHANT_ID`, `CLICK_SERVICE_ID`, `CLICK_SECRET_KEY`,
   `PAYME_MERCHANT_ID`, `PAYME_KEY`.
2. Kabinetga webhook bering: `/api/payments/click`, `/api/payments/payme`.
3. `POST /api/payments/invoice` → javobda `links.click` / `links.payme`.
4. Webhook to'lovni avtomatik tasdiqlaydi va qarzni FIFO bo'yicha yopadi.

> Webhooklar ochiq — ular tashqi imzo/parol bilan himoyalangan.

---

## 🧪 Testlar

```bash
cd construction_factory_bot
pytest          # 582+ test (bot, DB, API auth, 2FA, sessiya, shop, smena, ...)
```

---

## 🧩 Asosiy sozlashlar (.env)

```ini
# ── Majburiy ──
BOT_TOKEN=...                        # Telegram bot tokeni (@BotFather)
ADMIN_IDS=123456789                  # Direktor Telegram ID lari
API_SECRET_KEY=...                   # Web access token imzosi

# ── Sessiya xavfsizligi (TZ: 5–30 daqiqa) ──
BOT_AUTH_ENABLED=true                # false → eski rejim (telegram_id bo'yicha)
BOT_SESSION_MINUTES=15               # bot sessiyasi (5..30)
BOT_SESSION_IDLE_MINUTES=25          # bot harakatsizlik limiti
BOT_LOGIN_MAX_ATTEMPTS=3             # xato parol limiti (blok)
BOT_LOGIN_LOCKOUT_MINUTES=10
BOT_MAX_SESSIONS_PER_EMPLOYEE=2
SESSION_MINUTES=15                   # web access token (5..30)
SESSION_IDLE_MINUTES=25              # web harakatsizlik limiti
REFRESH_TOKEN_TTL_DAYS=30            # web refresh token (sliding)

# ── Ma'lumotlar bazasi ──
# SQLite default: database/construction.db
USE_POSTGRESQL=false
# DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD (PostgreSQL uchun)

# ── Backup ──
BACKUP_TIME=02:00
BACKUP_KEEP_DAYS=30
BACKUP_UPLOAD=none                   # telegram | s3 | telegram,s3
BACKUP_TELEGRAM_CHANNEL_ID=...
BACKUP_S3_BUCKET=...  BACKUP_S3_ACCESS_KEY=...  BACKUP_S3_SECRET_KEY=...
BACKUP_ENCRYPTION_PASSWORD=...       # qo'yilsa — chiquvchi nusxalar AES bilan shifrlanadi

# ── To'lovlar / SMS / AI ──
CLICK_MERCHANT_ID=...  CLICK_SERVICE_ID=...  CLICK_SECRET_KEY=...
PAYME_MERCHANT_ID=...  PAYME_KEY=...
SMS_ENABLED=false      SMS_API_KEY=...
```

---

## 🔌 REST API (qisqacha)

Barcha endpointlar `http://localhost:8000/api/...` (Node orqali
`http://localhost:3000/api/...`), auth: `Authorization: Bearer <token>`.

```
POST /api/login  /api/refresh  /api/logout      # auth: access + refresh token
GET  /api/me                                    # joriy foydalanuvchi + ruxsatlar
POST /api/auth/2fa/setup|enable|disable         # 2FA boshqaruvi

GET  /api/stats  /api/warehouse  /api/products  /api/convert
GET/POST /api/customers ...  /api/suppliers ...  /api/receipts ...
GET/POST /api/reservations ...  /api/transfers ...  /api/inventory-checks ...
GET  /api/finance/pl|tax|debts                  # P&L, soliq, qarzlar
GET/POST /api/returns ...  /api/deliveries ...  # qaytarish, yetkazib berish (GPS)
GET/POST /api/fuel/*  /api/expenses/*  /api/picking/*  /api/security/*
GET  /api/sellers/ratings                       # v4.1 operatsion modullar
GET/POST /api/backups ...                       # backup/tiklash (direktor)
GET  /api/cash-shifts/current  POST /api/cash-shifts/open|close

# Ommaviy web-do'kon (auth shart emas):
GET  /api/shop/catalog  POST /api/shop/orders  GET /api/shop/orders/{number}
# Click/Payme webhook:
POST /api/payments/click  POST /api/payments/payme
```

To'liq ro'yxat va rol matritsasi: [`construction_factory_bot/README.md`](construction_factory_bot/README.md).

---

## 🗺️ Roadmap (navbatdagi bosqichlar)

- 📱 Mobil ilovalar (Android/iOS) yoki PWA offline rejimi
- 🔄 WebSocket orqali real-time yangilanishlar
- 🛰️ Direktor uchun kengaytirilgan audit va statistika paneli
- 📊 AI asosidagi prognoz (talab, narx) modulini UI'ga chiqarish

---

## 📜 Litsenziya

MIT — batafsil: [`construction_factory_bot/web/package.json`](construction_factory_bot/web/package.json)
va repozitoriy hujjatlari.

---

*Ushbu README tizimning to'liq tahlili asosida yozilgan. Har bir modulning
texnik tafsilotlari, API javob shakllari va bot dialog oqimlari uchun
[`construction_factory_bot.md`](construction_factory_bot.md) (texnik topshiriq) va
[`construction_factory_bot/README.md`](construction_factory_bot/README.md) (implementatsiya qo'llanmasi) ga murojaat qiling.*
