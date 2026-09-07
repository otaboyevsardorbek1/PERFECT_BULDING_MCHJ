# 🏗️ PERFECT BUILDING MCHJ — Система управления строительной компанией

> 🌐 Русский  |  🇺🇿 [O'zbekcha](README.md)  |  🇬🇧 [English](README.en.md)

Единая комплексная автоматизированная система для **производства + оптовой/розничной
торговли + склада + логистики** строительных материалов: все операции — через
**Telegram-бота**, визуальное управление — через **Web-дашборд**, интеграция —
через **REST API**.

Система спроектирована на основе реальных бизнес-процессов компании
(полное техническое задание: [`construction_factory_bot.md`](construction_factory_bot.md) — 9 400+ строк).
Каждый модуль работает в трёх слоях — **бот + API + Web UI** — и защищён
**матрицей ролей** и **безопасностью сессий**.

| Слой | Технология | Порт |
| :--- | :--- | :--- |
| 🤖 **Telegram-бот** | Python **aiogram v3.22** (polling) | — |
| 🔌 **REST API (бэкенд)** | Python **FastAPI** + SQLAlchemy | `8000` |
| 🌐 **Web-фронтенд** | **Node.js** (сервер без зависимостей + proxy) | `3000` |
| 💾 **База данных** | SQLite (по умолчанию) / PostgreSQL (`USE_POSTGRESQL=true`) | — |

```
 Telegram Bot (aiogram) ────────┐
                                ▼
 Node.js web (web/public) ──/api──▶ FastAPI (:8000) ──▶ SQLite / PostgreSQL
                                ▲
 Click / Payme webhook ─────────┘        (ai_prediction, SMS, backup, scheduler)
```

---

## 📁 Структура репозитория

```
PERFECT_BULDING_MCHJ/
├── construction_factory_bot.md     # 📋 Полное техническое задание / аналитика
├── construction_factory_bot/       # ⚙️ Полная реализация системы
│   ├── main.py                     #    Telegram-бот (aiogram) — точка входа
│   ├── config.py                   #    Все настройки и параметры .env
│   ├── dashboard/                  #    FastAPI: app.py, api_v3.py, auth.py,
│   │                               #    payments.py (Click/Payme), shop.py, password_reset.py
│   ├── handlers/                   #    Обработчики бота (sales, finance, ...)
│   ├── database/                   #    SQLAlchemy-модели, CRUD, обновление схемы
│   ├── utils/                      #    totp, backup, rate_limit, bot_auth, pdf/excel, charts...
│   ├── web/                        #    Node.js-фронтенд (server.js + public/ SPA)
│   ├── tests/                      #    Pytest-тесты (582+)
│   ├── keyboards/                  #    Inline-клавиатуры Telegram
│   ├── Dockerfile                  #    Единый контейнер (Python 3.11 + Node 20)
│   └── docker-compose.yml          #    Сервисы: api / web / bot
├── .github/workflows/ci.yml        # 🔄 CI: pytest + проверка Node + Docker build
└── CodeAnalyzer_v1.py              #   Скрипт анализа кода
```

Дополнительная техническая документация:
- 📖 [`construction_factory_bot/README.md`](construction_factory_bot/README.md) — руководство и список API
- 📘 [`construction_factory_bot/PROJECT_GUIDE.md`](construction_factory_bot/PROJECT_GUIDE.md) — руководство по проекту
- 📗 [`construction_factory_bot/TAHLIL.md`](construction_factory_bot/TAHLIL.md) — поэтапные результаты анализа

---

## ✨ Основные возможности (по версиям)

### v1–v2 — Ядро (бот + API)
Каталог продукции и единицы измерения (шт/кг/м²/м³/паллета/мешок), калькулятор
конвертации, склады сырья/готовой продукции, производственные заказы (расчёт
сырья по рецептуре/BOM), продажи, отчёты (Excel/PDF/графики), SMS-уведомления,
AI-аналитика.

### v3.0 — Расширенные модули (по ТЗ)

| Модуль | Бот | API | Web UI |
| :--- | :-: | :-: | :-: |
| 👥 **CRM / Клиенты** (карточка, лимит рассрочки, FIFO-оплата, баллы) | ✅ | ✅ | ✅ |
| 💰 **Продажи** (рассрочка, предоплата, **смешанная оплата**, скидки) | ✅ | — | ✅ |
| 🚚 **Поставщики** + **акт приёмки** с контролем качества | ✅ | ✅ | ✅ |
| 🔒 **Резервирование** (2–24 ч, автоснятие) | ✅ | ✅ | ✅ |
| 🔄 **Перемещение между складами** (сырьё/готовая/брак) | ✅ | ✅ | ✅ |
| 📋 **Инвентаризация** (система ↔ факт, акт недостачи) | ✅ | — | ✅ |
| 💱 **Конвертация** (1 паллета = 40 мешков = 2000 кг) | ✅ | ✅ | — |
| 📊 **Финансы**: P&L, НДС 12%, налог с оборота 4%, долги | ✅ | ✅ | ✅ |
| ↩️ **Акт возврата** (деньги/обмен/бонус, правило 7 дней, корректировка P&L) | ✅ | ✅ | — |
| 🚚 **Доставка + GPS** (водитель, онлайн-отслеживание) | ✅ | ✅ | — |
| 🏭 **Производство** + 🔬 **Контроль качества (QC)** | ✅ | ✅ | ✅ |
| 💳 **SMS-напоминания о долгах** (3/7/14/30 дней) | ✅ авто | — | — |
| 🕰️ **Медленно продаваемые остатки** — предупреждения | ✅ авто | — | — |
| 💾 **Бэкап/восстановление** (авто, с шифрованием, в Telegram/S3) | ✅ | ✅ | ✅ |
| 🛒 **Публичный веб-магазин** (`/shop.html`, наличные / Click / Payme) | — | ✅ | ✅ |
| 💵 **Кассовая смена** (расчёт расхождения наличных) | ✅ | ✅ | — |
| 🏅 **Сегментация клиентов** (Золото/Серебро/Бронза) | ✅ | ✅ | ✅ |
| 💡 **Рекомендация похожих товаров** + 🚨 блокировка больших скидок | ✅ | ✅ | — |
| 📊 **Ежедневный дайджест директора** | ✅ авто | — | — |

### v4.0 — Безопасность: логин/пароль + сессия (5–30 минут) ⭐
Требование ТЗ: каждый сотрудник входит по **паролю** и получает сессию на
**5–30 минут**; при завершении сессии или выходе (logout) все выданные
**права (роли) автоматически аннулируются**.

- Бот: `/login` (телефон+пароль), `/sessiya`, `/logout`, `/parol`
- Пароли — **PBKDF2-HMAC-SHA256** (одинаковый формат для бота и веба)
- Неверный пароль → блокировка на `BOT_LOGIN_MAX_ATTEMPTS` (3) попыток
  на `10` минут (защита от перебора)
- Таймер неактивности (`idle_timeout`) автоматически завершает сессию
- Web: access-токен на `SESSION_MINUTES` (5–30), refresh-токен с ротацией (sliding)
- `POST /api/logout` → сессия отзывается на сервере; старые токены не работают
- Глобальный middleware блокирует все команды бота без сессии
- Для совместимости со старой системой: `BOT_AUTH_ENABLED=false` — прежний режим

### v4.1 — Операционные модули (бот + API + Web UI)

| Модуль | Описание |
| :--- | :--- |
| ⛽ **Контроль топлива** | Запись литров/цены/спидометра, норма Л/100км |
| 🧾 **Авансовые (расходные) отчёты** | Запись расходов → подтверждение директором/бухгалтером |
| 📦 **Комплектовочный лист (picking list)** | Список для кладовщика по заказу, сектора |
| 🚨 **Детектор подозрительных операций** | Ночные продажи, большие скидки и др. аномалии |
| 🏆 **Рейтинг продавцов** | Продажи за 30 дней, число чеков, средний чек |
| 🕰️ **Учёт рабочего времени сотрудников** | Приход/уход, отработанные и сверхурочные часы |

### v4.2 — 2FA: Google Authenticator (TOTP)
Пароль + **6-значный одноразовый код** для директора/кассира и любого сотрудника:
- Бот: `/2fa` (включение по QR-коду / отключение), шаг кода в `/login`
- Web: двухшаговый `/login` (пароль → `otp_token` → код); API `428/401/200`
- `/api/auth/2fa/setup|enable|disable`, поле `two_fa_enabled` в `/api/me`
- TOTP по RFC 6238 (`utils/totp.py`), старая БД мигрируется автоматически

### 🐳 v4.x — Docker + CI/CD
`docker-compose up -d --build` — api (:8000), web (:3000), bot; SQLite, бэкапы и
логи в shared volume. `.github/workflows/ci.yml` — на каждый push/PR: 582+ теста,
проверка синтаксиса Node и Docker build.

---

## 🚀 Запуск

### 1) Локально (Python-бэкенд + бот)

```bash
cd construction_factory_bot

python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Создайте .env (минимум BOT_TOKEN и ADMIN_IDS):
#   cp .env.example .env   (или вручную, минимум:)
#
#   BOT_TOKEN=123456:ABC...
#   ADMIN_IDS=123456789
#   API_SECRET_KEY=длинный-случайный-ключ      # подпись веб-токенов

# 1) REST API (его вызывает веб-фронтенд)
python -m uvicorn dashboard.app:app --host 0.0.0.0 --port 8000

# 2) Telegram-бот (та же база данных)
python main.py
```

### 2) Веб-фронтенд (Node.js — доп. библиотеки не нужны)

```bash
cd web
PORT=3000 PY_API_URL=http://127.0.0.1:8000 node server.js
```

В браузере: **http://localhost:3000** → веб-дашборд,
**http://localhost:3000/shop.html** → публичный веб-магазин.

### 3) Docker (всё сразу)

```bash
cd construction_factory_bot
cp .env.example .env    # введите BOT_TOKEN, ADMIN_IDS
docker-compose up -d --build
```

### 🔐 Первый запуск: пароли

Сотрудники входят по **телефону + паролю** (и в боте, и в вебе):

```bash
# Директор может задать пароль через CLI:
python -m dashboard.auth set-password --phone +998901234567 --password parol1234

# или указать в .env (выдаётся администраторам автоматически):
#   WEB_ADMIN_PASSWORD=parol1234
```

Управление:
```bash
python -m dashboard.auth list-users      # сотрудники и статус паролей
```

---

## 🤖 Telegram-бот — основные команды

| Команда | Назначение |
| :--- | :--- |
| `/start` `/help` | Запуск, справка |
| `/login` | Открыть сессию (телефон + пароль; при 2FA — код) |
| `/logout` | Завершить сессию — права снимаются немедленно |
| `/sessiya` | Статус сессии (остаток времени, таймер неактивности) |
| `/parol` | Установить/сменить пароль |
| `/2fa` | Включить Google Authenticator (QR) / отключить |
| `/rollar` | Управление ролями (директор) |
| `/cancel` | Отменить текущее действие |

Остальные возможности — через **inline-клавиатуры** (по ролям):
👑 Панель администратора (бэкап, роли, сотрудники, аудит), 🛒 Продажи, 👥 CRM,
📦 Склад, 🏭 Производство, 📊 Отчёты, ⛽ Топливо, 🧾 Авансы, 🚚 Доставка и т.д.

> Каждое сообщение/callback проходит проверку сессии — без сессии работают
> только `/start`, `/help`, `/cancel`, `/login`, `/logout`, `/sessiya`, `/parol`.

---

## 💳 Онлайн-платежи (Click / Payme)

Клиент оплачивает долг за рассрочку или заказ магазина через Click/Payme:

1. В `.env` укажите: `CLICK_MERCHANT_ID`, `CLICK_SERVICE_ID`, `CLICK_SECRET_KEY`,
   `PAYME_MERCHANT_ID`, `PAYME_KEY`.
2. В кабинете пропишите вебхуки: `/api/payments/click`, `/api/payments/payme`.
3. `POST /api/payments/invoice` → в ответе `links.click` / `links.payme`.
4. Вебхук автоматически подтверждает платёж и закрывает долг по FIFO.

> Вебхуки открыты — защищены внешней подписью/паролем.

---

## 🧪 Тесты

```bash
cd construction_factory_bot
pytest          # 582+ теста (бот, БД, API auth, 2FA, сессии, магазин, смены, ...)
```

---

## 🧩 Основные настройки (.env)

```ini
# ── Обязательные ──
BOT_TOKEN=...                        # Токен Telegram-бота (@BotFather)
ADMIN_IDS=123456789                  # Telegram ID директоров
API_SECRET_KEY=...                   # Подпись веб-токенов доступа

# ── Безопасность сессий (ТЗ: 5–30 минут) ──
BOT_AUTH_ENABLED=true                # false → старый режим (по telegram_id)
BOT_SESSION_MINUTES=15               # сессия бота (5..30)
BOT_SESSION_IDLE_MINUTES=25          # лимит неактивности бота
BOT_LOGIN_MAX_ATTEMPTS=3             # лимит неверных паролей (блокировка)
BOT_LOGIN_LOCKOUT_MINUTES=10
BOT_MAX_SESSIONS_PER_EMPLOYEE=2
SESSION_MINUTES=15                   # веб access-токен (5..30)
SESSION_IDLE_MINUTES=25              # лимит неактивности веба
REFRESH_TOKEN_TTL_DAYS=30            # веб refresh-токен (sliding)

# ── База данных ──
# SQLite по умолчанию: database/construction.db
USE_POSTGRESQL=false
# DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD (для PostgreSQL)

# ── Бэкапы ──
BACKUP_TIME=02:00
BACKUP_KEEP_DAYS=30
BACKUP_UPLOAD=none                   # telegram | s3 | telegram,s3
BACKUP_TELEGRAM_CHANNEL_ID=...
BACKUP_S3_BUCKET=...  BACKUP_S3_ACCESS_KEY=...  BACKUP_S3_SECRET_KEY=...
BACKUP_ENCRYPTION_PASSWORD=...       # если задан — внешние копии шифруются AES

# ── Платежи / SMS / AI ──
CLICK_MERCHANT_ID=...  CLICK_SERVICE_ID=...  CLICK_SECRET_KEY=...
PAYME_MERCHANT_ID=...  PAYME_KEY=...
SMS_ENABLED=false      SMS_API_KEY=...
```

---

## 🔌 REST API (кратко)

Все эндпоинты: `http://localhost:8000/api/...` (через Node —
`http://localhost:3000/api/...`), авторизация: `Authorization: Bearer <token>`.

```
POST /api/login  /api/refresh  /api/logout      # auth: access + refresh token
GET  /api/me                                    # текущий пользователь и права
POST /api/auth/2fa/setup|enable|disable         # управление 2FA

GET  /api/stats  /api/warehouse  /api/products  /api/convert
GET/POST /api/customers ...  /api/suppliers ...  /api/receipts ...
GET/POST /api/reservations ...  /api/transfers ...  /api/inventory-checks ...
GET  /api/finance/pl|tax|debts                  # P&L, налоги, долги
GET/POST /api/returns ...  /api/deliveries ...  # возвраты, доставка (GPS)
GET/POST /api/fuel/*  /api/expenses/*  /api/picking/*  /api/security/*
GET  /api/sellers/ratings                       # операционные модули v4.1
GET/POST /api/backups ...                       # бэкап/восстановление (директор)
GET  /api/cash-shifts/current  POST /api/cash-shifts/open|close

# Публичный веб-магазин (без авторизации):
GET  /api/shop/catalog  POST /api/shop/orders  GET /api/shop/orders/{number}
# Вебхуки Click/Payme:
POST /api/payments/click  POST /api/payments/payme
```

Полный список и матрица ролей: [`construction_factory_bot/README.md`](construction_factory_bot/README.md).

---

## 🗺️ Дорожная карта (следующие этапы)

- 📱 Мобильные приложения (Android/iOS) или офлайн-режим PWA
- 🔄 Обновления в реальном времени через WebSocket
- 🛰️ Расширенная панель аудита и статистики для директора
- 📊 Вывод AI-прогнозов (спрос, цены) в интерфейс

---

## 📜 Лицензия

MIT — подробнее: [`construction_factory_bot/web/package.json`](construction_factory_bot/web/package.json)
и документация репозитория.

---

*Этот README написан на основе полного анализа системы. За техническими деталями
каждого модуля, форматами ответов API и диалоговыми сценариями бота обратитесь к
[`construction_factory_bot.md`](construction_factory_bot.md) (техническое задание) и
[`construction_factory_bot/README.md`](construction_factory_bot/README.md) (руководство по реализации).*
