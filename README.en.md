# 🏗️ PERFECT BUILDING MCHJ — Construction Factory Management System

> 🌐 English  |  🇺🇿 [O'zbekcha](README.md)  |  🇷🇺 [Русский](README.ru.md)

A single, fully automated management system for **production + wholesale/retail
trade + warehouse + logistics** of building materials: every operation runs
through the **Telegram bot**, visual control through the **web dashboard**, and
integration through a **REST API**.

The system was designed around the company's real business processes (full
technical specification: [`construction_factory_bot.md`](construction_factory_bot.md) — 9,400+ lines).
Every module works across three layers — **bot + API + web UI** — and is
protected by a **role matrix** and **session security**.

| Layer | Technology | Port |
| :--- | :--- | :--- |
| 🤖 **Telegram bot** | Python **aiogram v3.22** (polling) | — |
| 🔌 **REST API (backend)** | Python **FastAPI** + SQLAlchemy | `8000` |
| 🌐 **Web frontend** | **Node.js** (zero-dependency server + proxy) | `3000` |
| 💾 **Database** | SQLite (default) / PostgreSQL (`USE_POSTGRESQL=true`) | — |

```
 Telegram Bot (aiogram) ────────┐
                                ▼
 Node.js web (web/public) ──/api──▶ FastAPI (:8000) ──▶ SQLite / PostgreSQL
                                ▲
 Click / Payme webhook ─────────┘        (ai_prediction, SMS, backup, scheduler)
```

---

## 📁 Repository structure

```
PERFECT_BULDING_MCHJ/
├── construction_factory_bot.md     # 📋 Full technical specification / analysis
├── construction_factory_bot/       # ⚙️ Complete implementation of the system
│   ├── main.py                     #    Telegram bot (aiogram) — entry point
│   ├── config.py                   #    All settings and .env parameters
│   ├── dashboard/                  #    FastAPI: app.py, api_v3.py, auth.py,
│   │                               #    payments.py (Click/Payme), shop.py, password_reset.py
│   ├── handlers/                   #    Bot handlers (sales, finance, ...)
│   ├── database/                   #    SQLAlchemy models, CRUD, schema upgrade
│   ├── utils/                      #    totp, backup, rate_limit, bot_auth, pdf/excel, charts...
│   ├── web/                        #    Node.js frontend (server.js + public/ SPA)
│   ├── tests/                      #    Pytest tests (582+)
│   ├── keyboards/                  #    Telegram inline keyboards
│   ├── Dockerfile                  #    Single container (Python 3.11 + Node 20)
│   └── docker-compose.yml          #    Services: api / web / bot
├── .github/workflows/ci.yml        # 🔄 CI: pytest + Node syntax check + Docker build
└── CodeAnalyzer_v1.py              #   Code analysis script
```

Further technical documentation:
- 📖 [`construction_factory_bot/README.md`](construction_factory_bot/README.md) — guide and API reference
- 📘 [`construction_factory_bot/PROJECT_GUIDE.md`](construction_factory_bot/PROJECT_GUIDE.md) — project guide
- 📗 [`construction_factory_bot/TAHLIL.md`](construction_factory_bot/TAHLIL.md) — step-by-step analysis results

---

## ✨ Key features (by version)

### v1–v2 — Core (bot + API)
Product catalogue and units of measure (pc/kg/m²/m³/pallet/sack), conversion
calculator, raw-material / finished-goods warehouses, production orders
(BOM/recipe-based raw-material consumption), sales, reports (Excel/PDF/charts),
SMS notifications, AI-assisted analytics.

### v3.0 — Extended modules (per spec)

| Module | Bot | API | Web UI |
| :--- | :-: | :-: | :-: |
| 👥 **CRM / Customers** (card, credit limit, FIFO payments, points) | ✅ | ✅ | ✅ |
| 💰 **Sales** (credit, prepayment, **mixed payment**, discounts) | ✅ | — | ✅ |
| 🚚 **Suppliers** + **receipt act** with quality control | ✅ | ✅ | ✅ |
| 🔒 **Reservation** (2–24 h, auto-release) | ✅ | ✅ | ✅ |
| 🔄 **Inter-warehouse transfers** (raw/finished/defective) | ✅ | ✅ | ✅ |
| 📋 **Inventory checks** (system ↔ actual, shortage report) | ✅ | — | ✅ |
| 💱 **Conversion** (1 pallet = 40 sacks = 2000 kg) | ✅ | ✅ | — |
| 📊 **Finance**: P&L, VAT 12%, turnover tax 4%, debts | ✅ | ✅ | ✅ |
| ↩️ **Return act** (cash/exchange/bonus, 7-day rule, P&L adjustment) | ✅ | ✅ | — |
| 🚚 **Delivery + GPS** (driver, live tracking) | ✅ | ✅ | — |
| 🏭 **Production** + 🔬 **Quality control (QC)** acts | ✅ | ✅ | ✅ |
| 💳 **Debt SMS reminders** (days 3/7/14/30) | ✅ auto | — | — |
| 🕰️ **Slow-moving stock** alerts | ✅ auto | — | — |
| 💾 **Backup/restore** (automatic, encrypted, to Telegram/S3) | ✅ | ✅ | ✅ |
| 🛒 **Public web store** (`/shop.html`, cash / Click / Payme) | — | ✅ | ✅ |
| 💵 **Cashier shift** (cash discrepancy calculation) | ✅ | ✅ | — |
| 🏅 **Customer segmentation** (Gold/Silver/Bronze) | ✅ | ✅ | ✅ |
| 💡 **Related-product suggestions** + 🚨 large-discount blocking | ✅ | ✅ | — |
| 📊 **Director's daily digest** | ✅ auto | — | — |

### v4.0 — Security: login/password + sessions (5–30 minutes) ⭐
Spec requirement: every employee signs in with a **password** and receives a
**5-to-30-minute session**; when the session ends or the user logs out, all
granted **permissions (role rights) are revoked automatically**.

- Bot: `/login` (phone + password), `/sessiya`, `/logout`, `/parol`
- Passwords hashed with **PBKDF2-HMAC-SHA256** (same format for bot and web)
- Wrong password → account locked for `BOT_LOGIN_MAX_ATTEMPTS` (3) attempts for
  `10` minutes (brute-force protection)
- Inactivity timer (`idle_timeout`) ends the session automatically
- Web: access token `SESSION_MINUTES` (5–30), rotating refresh token (sliding)
- `POST /api/logout` → session revoked server-side; old tokens stop working
- A global middleware blocks all bot commands without an active session
- Legacy mode preserved: `BOT_AUTH_ENABLED=false` → previous (telegram_id) flow

### v4.1 — Operational modules (bot + API + web UI)

| Module | Description |
| :--- | :--- |
| ⛽ **Fuel control** | Litres/price/odometer logging, L/100km norm monitoring |
| 🧾 **Advance (expense) reports** | Expense records → approved by director/accountant |
| 📦 **Picking list** | Order-based list for the storekeeper, zones |
| 🚨 **Suspicious activity detector** | Night sales, large discounts and other anomalies |
| 🏆 **Seller ratings** | 30-day sales, number of receipts, average receipt |
| 🕰️ **Employee working hours** | Clock in/out, worked and overtime hours |

### v4.2 — 2FA: Google Authenticator (TOTP)
Password + **6-digit one-time code** for the director/cashier and any employee:
- Bot: `/2fa` (enable with QR image / disable), code step in `/login`
- Web: two-step `/login` (password → `otp_token` → code); API `428/401/200`
- `/api/auth/2fa/setup|enable|disable`, `two_fa_enabled` field in `/api/me`
- TOTP per RFC 6238 (`utils/totp.py`); legacy DB migrates automatically

### 🐳 v4.x — Docker + CI/CD
`docker-compose up -d --build` — api (:8000), web (:3000), bot; SQLite, backups
and logs on a shared volume. `.github/workflows/ci.yml` — on every push/PR:
582+ tests, Node syntax check and Docker build.

---

## 🚀 Getting started

### 1) Locally (Python backend + bot)

```bash
cd construction_factory_bot

python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Create .env (at least BOT_TOKEN and ADMIN_IDS):
#   cp .env.example .env   (or write the minimal set manually:)
#
#   BOT_TOKEN=123456:ABC...
#   ADMIN_IDS=123456789
#   API_SECRET_KEY=long-random-key            # signs web access tokens

# 1) REST API (consumed by the web frontend)
python -m uvicorn dashboard.app:app --host 0.0.0.0 --port 8000

# 2) Telegram bot (same database)
python main.py
```

### 2) Web frontend (Node.js — no extra dependencies needed)

```bash
cd web
PORT=3000 PY_API_URL=http://127.0.0.1:8000 node server.js
```

Then open: **http://localhost:3000** → web dashboard,
**http://localhost:3000/shop.html** → public web store.

### 3) Docker (everything at once)

```bash
cd construction_factory_bot
cp .env.example .env    # set BOT_TOKEN, ADMIN_IDS
docker-compose up -d --build
```

### 🔐 First run: passwords

Employees sign in with **phone + password** (both in the bot and on the web):

```bash
# The director can set a password via the CLI:
python -m dashboard.auth set-password --phone +998901234567 --password parol1234

# or via .env (assigned to admins automatically):
#   WEB_ADMIN_PASSWORD=parol1234
```

Administration:
```bash
python -m dashboard.auth list-users      # employees and password status
```

---

## 🤖 Telegram bot — main commands

| Command | Purpose |
| :--- | :--- |
| `/start` `/help` | Start, help |
| `/login` | Open a session (phone + password; with 2FA — also the code) |
| `/logout` | End the session — rights are revoked immediately |
| `/sessiya` | Session status (remaining time, inactivity timer) |
| `/parol` | Set/change password |
| `/2fa` | Enable Google Authenticator (QR) / disable |
| `/rollar` | Role management (director) |
| `/cancel` | Cancel the current action |

Everything else is available via **inline keyboards** (by role):
👑 Admin panel (backup, roles, employees, audit), 🛒 Sales, 👥 CRM, 📦 Warehouse,
🏭 Production, 📊 Reports, ⛽ Fuel, 🧾 Advances, 🚚 Delivery, and more.

> Every message/callback goes through session verification — without a session
> only `/start`, `/help`, `/cancel`, `/login`, `/logout`, `/sessiya`, `/parol` work.

---

## 💳 Online payments (Click / Payme)

A customer can pay an outstanding credit balance or a store order via Click/Payme:

1. Put the keys in `.env`: `CLICK_MERCHANT_ID`, `CLICK_SERVICE_ID`,
   `CLICK_SECRET_KEY`, `PAYME_MERCHANT_ID`, `PAYME_KEY`.
2. Register the webhooks in the payment cabinet:
   `/api/payments/click`, `/api/payments/payme`.
3. `POST /api/payments/invoice` → response contains `links.click` / `links.payme`.
4. The webhook confirms the payment automatically and closes the debt by FIFO.

> Webhooks are public — they are protected by the gateway's external
> signature/password rather than a Bearer token.

---

## 🧪 Tests

```bash
cd construction_factory_bot
pytest          # 582+ tests (bot, DB, API auth, 2FA, sessions, shop, shifts, ...)
```

---

## 🧩 Main settings (.env)

```ini
# ── Required ──
BOT_TOKEN=...                        # Telegram bot token (@BotFather)
ADMIN_IDS=123456789                  # Directors' Telegram IDs
API_SECRET_KEY=...                   # Web access-token signature key

# ── Session security (spec: 5–30 minutes) ──
BOT_AUTH_ENABLED=true                # false → legacy mode (by telegram_id)
BOT_SESSION_MINUTES=15               # bot session (5..30)
BOT_SESSION_IDLE_MINUTES=25          # bot inactivity limit
BOT_LOGIN_MAX_ATTEMPTS=3             # wrong-password limit (lockout)
BOT_LOGIN_LOCKOUT_MINUTES=10
BOT_MAX_SESSIONS_PER_EMPLOYEE=2
SESSION_MINUTES=15                   # web access token (5..30)
SESSION_IDLE_MINUTES=25              # web inactivity limit
REFRESH_TOKEN_TTL_DAYS=30            # web refresh token (sliding)

# ── Database ──
# SQLite by default: database/construction.db
USE_POSTGRESQL=false
# DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD (for PostgreSQL)

# ── Backups ──
BACKUP_TIME=02:00
BACKUP_KEEP_DAYS=30
BACKUP_UPLOAD=none                   # telegram | s3 | telegram,s3
BACKUP_TELEGRAM_CHANNEL_ID=...
BACKUP_S3_BUCKET=...  BACKUP_S3_ACCESS_KEY=...  BACKUP_S3_SECRET_KEY=...
BACKUP_ENCRYPTION_PASSWORD=...       # if set — outgoing backups are AES-encrypted

# ── Payments / SMS / AI ──
CLICK_MERCHANT_ID=...  CLICK_SERVICE_ID=...  CLICK_SECRET_KEY=...
PAYME_MERCHANT_ID=...  PAYME_KEY=...
SMS_ENABLED=false      SMS_API_KEY=...
```

---

## 🔌 REST API (summary)

All endpoints live at `http://localhost:8000/api/...` (via Node —
`http://localhost:3000/api/...`); auth: `Authorization: Bearer <token>`.

```
POST /api/login  /api/refresh  /api/logout      # auth: access + refresh token
GET  /api/me                                    # current user and permissions
POST /api/auth/2fa/setup|enable|disable         # 2FA management

GET  /api/stats  /api/warehouse  /api/products  /api/convert
GET/POST /api/customers ...  /api/suppliers ...  /api/receipts ...
GET/POST /api/reservations ...  /api/transfers ...  /api/inventory-checks ...
GET  /api/finance/pl|tax|debts                  # P&L, taxes, debts
GET/POST /api/returns ...  /api/deliveries ...  # returns, delivery (GPS)
GET/POST /api/fuel/*  /api/expenses/*  /api/picking/*  /api/security/*
GET  /api/sellers/ratings                       # v4.1 operational modules
GET/POST /api/backups ...                       # backup/restore (director)
GET  /api/cash-shifts/current  POST /api/cash-shifts/open|close

# Public web store (no auth required):
GET  /api/shop/catalog  POST /api/shop/orders  GET /api/shop/orders/{number}
# Click/Payme webhooks:
POST /api/payments/click  POST /api/payments/payme
```

Full endpoint list and role matrix:
[`construction_factory_bot/README.md`](construction_factory_bot/README.md).

---

## 🗺️ Roadmap (next steps)

- 📱 Mobile apps (Android/iOS) or offline PWA mode
- 🔄 Real-time updates over WebSocket
- 🛰️ Extended audit and statistics panel for the director
- 📊 Surfacing AI forecasts (demand, prices) in the UI

---

## 📜 License

MIT — see [`construction_factory_bot/web/package.json`](construction_factory_bot/web/package.json)
and the repository documentation.

---

*This README was written based on a full analysis of the system. For technical
details of every module, API response shapes and bot dialogue flows, refer to
[`construction_factory_bot.md`](construction_factory_bot.md) (technical specification) and
[`construction_factory_bot/README.md`](construction_factory_bot/README.md) (implementation guide).*
