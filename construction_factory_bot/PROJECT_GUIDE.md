# 🏗️ Qurilish Materiallari Korxonasi Boti - To'liq Loyiha Qo'llanmasi

## 📋 Mundarija

1. [🏗️ Arxitektura](#1-arxitektura)
2. [💾 Database](#2-database)
3. [🔒 Xavfsizlik](#3-xavfsizlik)
4. [📈 Masshtablash](#4-masshtablash)
5. [🚀 Deploy](#5-deploy)
6. [🧪 Testing](#6-testing)
7. [💡 Yangi g'oyalar](#7-yangi-goyalar)

---

## 1. 🏗️ Arxitektura

### 1.1 Loyiha tuzilishi

```
construction_factory_bot/
├── main.py                    # Asosiy fayl (entry point) — aiogram v3
├── config.py                  # Konfiguratsiya (rollar matritsasi ham)
├── requirements.txt           # Kutubxonalar
├── .env.example               # Environment namunasi
│
├── database/                  # Ma'lumotlar bazasi
│   ├── models.py              # SQLAlchemy modellari (+ v3 jadvallar, auto-migratsiya)
│   ├── crud.py                # CRUD + biznes mantiq (nasiya, qabul akti, P&L...)
│   ├── db.py                  # SQLite boshqaruvchi
│   └── session.py             # Database sessiya
│
├── handlers/                  # Telegram handlerlar (aiogram v3)
│   ├── start.py               # /start, /help (rolga qarab menyu)
│   ├── production.py          # Ishlab chiqarish
│   ├── warehouse.py           # Ombor
│   ├── reports.py             # Excel hisobotlar
│   ├── pdf_reports.py         # PDF hisobotlar
│   ├── admin.py               # Admin panel
│   ├── employees.py           # Xodimlar
│   ├── sales.py               # Sotuvlar (nasiya limiti, chegirma)
│   ├── notifications.py       # Bildirishnomalar
│   ├── sms.py                 # SMS xizmati
│   ├── ai_predict.py          # AI bashoratlar
│   ├── customers.py           # v3: CRM / mijozlar
│   ├── suppliers.py           # v3: yetkazib beruvchilar + qabul aktlari
│   ├── stock_ops.py           # v3: rezervatsiya, ko'chirish, inventarizatsiya, konvertatsiya
│   ├── finance.py             # v3: moliya (P&L, qarz, soliq)
│   └── roles.py               # v3: rollar matritsasi boshqaruvi
│
├── keyboards/                 # Klaviaturalar
│   ├── main_menu.py           # Asosiy menyu (rolga qarab)
│   ├── admin_menu.py          # Admin menyu
│   └── inline_keyboards.py    # Inline tugmalar
│
├── utils/                     # Yordamchi modullar
│   ├── calculations.py        # Hisob-kitoblar
│   ├── notifications.py       # Push bildirishnomalar
│   ├── excel_reports.py       # Excel yaratish
│   ├── pdf_reports.py         # PDF yaratish
│   ├── charts.py              # Grafiklar
│   ├── helpers.py             # Yordamchi funksiyalar
│   ├── formulas.py            # Mahsulot formulalari
│   ├── sms_service.py         # SMS xizmati
│   ├── ai_prediction.py       # AI bashoratlar
│   └── access.py              # v3: rol tekshiruvi (rullar matritsasi)
│
├── dashboard/                 # Python REST API (FastAPI)
│   ├── app.py                 # FastAPI ilova (CORS + legacy sahifa)
│   ├── api_v3.py              # v3 REST endpointlari (CRM, ta'minot, moliya...)
│   └── ...
│
├── web/                       # v3: NODE.JS WEB FRONTEND (zero-dependency)
│   ├── server.js              # Node http server + /api proxy
│   ├── package.json           # npm start
│   └── public/                # Yangi dizayn: index.html, style.css, app.js
│
├── reports/                   # Hisobotlar papkasi
├── logs/                      # Log fayllar
└── tests/                     # 200+ test (CRUD, API, utils, handler)
```

### 1.2 Modullar orasidagi bog'lik

```
main.py
    ↓
handlers/*
    ↓
├── database/* (ma'lumotlar bazasi)
├── keyboards/* (klaviaturalar)
└── utils/* (yordamchi funksiyalar)
```

### 1.3 API dizayni (Web Dashboard)

```
GET  /                    # Dashboard sahifasi
GET  /api/stats           # Umumiy statistika
GET  /api/warehouse       # Ombor holati
GET  /api/products        # Mahsulotlar
GET  /api/orders          # Buyurtmalar
```

### 1.4 Arxitektura afzalliklari

| Afzallik | Tavsif |
|----------|--------|
| **Modullilik** | Har bir funksiya alohida faylda |
| **Kengaytirilishi** | Yangi handler qo'shish oson |
| **Qayta ishlatilishi** | Utils modullari boshqa loyihalarda ishlatilishi mumkin |
| **Test qilinishi** | Har bir modulni alohida test qilish mumkin |

---

## 2. 💾 Database

### 2.1 Jadvallar tuzilishi

```sql
-- 1. Xom ashyolar
raw_materials (
    id, name, category, unit, current_stock, min_stock, 
    max_stock, price_per_unit, supplier, ...
)

-- 2. Mahsulotlar
products (
    id, name, category, unit, selling_price, production_cost,
    profit_margin, barcode, description, ...
)

-- 3. Mahsulot formulalari (BOM)
product_formulas (
    id, product_id, raw_material_id, quantity, waste_percentage, ...
)

-- 4. Ombor harakatlari
warehouse_transactions (
    id, date, product_id, raw_material_id, quantity,
    transaction_type, user_id, ...
)

-- 5. Ishlab chiqarish buyurtmalari
production_orders (
    id, order_number, product_id, quantity, status,
    priority, planned_start, planned_end, total_cost, ...
)

-- 6. Xodimlar
employees (
    id, telegram_id, full_name, phone_number, position,
    department, status, salary, is_admin, ...
)

-- 7. Ish vaqtlari
work_hours (
    id, employee_id, date, start_time, end_time,
    hours_worked, overtime_hours, ...
)

-- 8. Maosh to'lovlari
salary_payments (
    id, employee_id, month, year, base_salary,
    bonus, total_amount, payment_date, ...
)

-- 9. Sotuvlar
sales (
    id, invoice_number, product_id, quantity, unit_price,
    total_amount, customer_name, payment_method, ...
)

-- 10. Bildirishnomalar
notifications (
    id, notification_type, title, message, recipient_id,
    status, priority, scheduled_time, ...
)

-- 11. Tizim loglari
system_logs (
    id, user_id, action, module, details, ip_address, ...
)
```

### 2.2 Indekslar

```sql
-- Tezkor qidiruv uchun indekslar
CREATE INDEX idx_raw_materials_name ON raw_materials(name);
CREATE INDEX idx_products_category ON products(category);
CREATE INDEX idx_warehouse_transactions_date ON warehouse_transactions(date);
CREATE INDEX idx_production_orders_status ON production_orders(status);
CREATE INDEX idx_employees_telegram_id ON employees(telegram_id);
CREATE INDEX idx_sales_sale_date ON sales(sale_date);
CREATE INDEX idx_notifications_status ON notifications(status);
```

### 2.3 Migratsiya (Alembic)

```bash
# Alembic ni sozlash
alembic init alembic

# Yangi migratsiya yaratish
alembic revision --autogenerate -m "description"

# Migratsiyani qo'llash
alembic upgrade head

# Migratsiyani bekor qilish
alembic downgrade -1
```

### 2.4 Database optimallashtirish

| Muammo | Yechim |
|--------|--------|
| **Sekin querylar** | Indekslar qo'shish, eager loading |
| **Ko'p ulanishlar** | Connection pooling (asyncpg) |
| **Katta hajm** | Arxivlash, partition qilish |
| **Backup** | Avtomatik backup (daily) |

### 2.5 SQLite → PostgreSQL o'tish

```python
# config.py
USE_POSTGRESQL = True  # PostgreSQL ishlatish

# Database URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
```

---

## 3. 🔒 Xavfsizlik

### 3.1 Autentifikatsiya

```python
# Admin tekshirish
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# Middleware orqali
class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user_id = event.from_user.id
        if not is_admin(user_id):
            await event.answer("❌ Ruxsat yo'q!")
            return
        return await handler(event, data)
```

### 3.2 Ruxsatlar tizimi

```python
# Ruxsat turlari
class Permission(Enum):
    VIEW_DASHBOARD = "view_dashboard"
    MANAGE_PRODUCTS = "manage_products"
    MANAGE_EMPLOYEES = "manage_employees"
    MANAGE_ORDERS = "manage_orders"
    VIEW_REPORTS = "view_reports"
    MANAGE_SETTINGS = "manage_settings"

# Xodim ruxsatlari
employee_permissions = {
    "admin": [p for p in Permission],  # Barcha ruxsatlar
    "manager": [Permission.VIEW_DASHBOARD, Permission.MANAGE_ORDERS],
    "worker": [Permission.VIEW_DASHBOARD],
}
```

### 3.3 Ma'lumotlarni himoya qilish

```python
# 1. Parolni hashlash
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

hashed_password = pwd_context.hash("password123")
verified = pwd_context.verify("password123", hashed_password)

# 2. JWT tokenlar
import jwt
from datetime import datetime, timedelta

def create_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

# 3. Maxfiy ma'lumotlarni yashirish
def mask_phone(phone: str) -> str:
    return phone[:4] + "****" + phone[-3:]
```

### 3.4 Xavfsizlik sozlamalari

```python
# config.py
SECURITY_SETTINGS = {
    "max_login_attempts": 5,        # Maksimal urinishlar
    "session_timeout": 3600,        # Sessiya vaqti (1 soat)
    "password_min_length": 8,       # Parol uzunligi
    "require_2fa": False,           # 2FA talab qilish
    "block_suspicious": True,       # Shubhali faollikni bloklash
    "rate_limit": 100,              # So'rovlar limiti (soatiga)
}
```

### 3.5 Xavfsizlik check-listi

- [x] Bot tokeni .env faylda saqlanadi
- [x] Admin ID lari faqat serverda
- [x] Parollar hashlangan
- [x] SSL/TLS ishlatiladi
- [x] Log fayllar himoyalangan
- [x] Backuplar shifrlangan

---

## 4. 📈 Masshtablash

### 4.1 Ko'p foydalanuvchi qo'llab-quvvatlash

```python
# 1. Async database (asyncpg)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

async_engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/db",
    pool_size=20,
    max_overflow=10
)

# 2. Redis kesh
import redis.asyncio as redis

redis_client = redis.Redis(host='localhost', port=6379, db=0)

# Keshlash
async def get_cached_data(key: str):
    cached = await redis_client.get(key)
    if cached:
        return json.loads(cached)
    # Database dan olish va keshlash
    data = await fetch_from_db(key)
    await redis_client.setex(key, 300, json.dumps(data))  # 5 daqiqa
    return data
```

### 4.2 Yuklama taqsimlash

```python
# 1. Celery (background tasks)
from celery import Celery

celery_app = Celery('bot', broker='redis://localhost:6379/0')

@celery_app.task
def send_notification_task(user_id: int, message: str):
    # Kekin vazifalarni bajarish
    asyncio.run(send_notification(user_id, message))

# 2. Queue tizimi
import asyncio
from collections import deque

message_queue = asyncio.Queue()

async def process_queue():
    while True:
        task = await message_queue.get()
        await process_task(task)
```

### 4.3 Monitoring

```python
# 1. Prometheus metrics
from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter('bot_requests', 'Total requests')
REQUEST_LATENCY = Histogram('bot_latency', 'Request latency')

@app.middleware("http")
async def metrics_middleware(request, call_next):
    REQUEST_COUNT.inc()
    with REQUEST_LATENCY.time():
        response = await call_next(request)
    return response

# 2. Sentry (xatolik monitoring)
import sentry_sdk
sentry_sdk.init(dsn="your-dsn-here")
```

### 4.4 Performance maslahatlari

| Maslahat | Tavsif |
|----------|--------|
| **Keshlash** | Tez-tez ishlatiladigan ma'lumotlarni keshlash |
| **Lazy loading** | Kerak bo'lganda ma'lumotlarni yuklash |
| **Pagination** | Katta ro'yxatlarni sahifalarga bo'lish |
| **Indexing** | Tez qidiruv uchun indekslar |
| **Connection pooling** | Ulanishlarni qayta ishlatish |

---

## 5. 🚀 Deploy

### 5.1 Docker

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Kutubxonalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Loyiha fayllari
COPY . .

# Papkalar
RUN mkdir -p logs reports/excel reports/charts reports/pdf backups

# Botni ishga tushirish
CMD ["python", "main.py"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  bot:
    build: .
    restart: always
    env_file: .env
    volumes:
      - ./logs:/app/logs
      - ./reports:/app/reports
      - ./database:/app/database
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: construction_factory
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  dashboard:
    build: .
    command: python dashboard/app.py
    ports:
      - "8000:8000"
    depends_on:
      - postgres

volumes:
  postgres_data:
```

### 5.2 Server sozlash

```bash
# 1. Serverga ulanish
ssh user@server-ip

# 2. Docker o'rnatish
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 3. Loyihani ko'chirish
git clone https://github.com/username/project.git
cd project

# 4. .env faylini yaratish
cp .env.example .env
nano .env  # Sozlamalarni kiriting

# 5. Docker compose bilan ishga tushirish
docker-compose up -d

# 6. Loglarni ko'rish
docker-compose logs -f bot
```

### 5.3 CI/CD (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy to server
        uses: appleboy/ssh-action@v0.1.5
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_KEY }}
          script: |
            cd /path/to/project
            git pull
            docker-compose down
            docker-compose up -d --build
```

### 5.4 Nginx sozlash

```nginx
# /etc/nginx/sites-available/bot-dashboard
server {
    listen 80;
    server_name dashboard.example.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /static {
        alias /path/to/project/dashboard/static;
    }
}
```

---

## 6. 🧪 Testing

### 6.1 Test turlari

```python
# 1. Unit testlar
import pytest
from utils.calculations import ProductionCalculator

def test_production_cost():
    calc = ProductionCalculator()
    result = calc.calculate_production_cost(1, 100)
    assert result.success == True
    assert result.data['total_cost'] > 0

# 2. Integration testlar
@pytest.mark.asyncio
async def test_start_handler():
    from handlers.start import cmd_start
    from aiogram import types
    
    message = types.Message(
        text="/start",
        from_user=types.User(id=123, is_bot=False)
    )
    
    await cmd_start(message, state=None)
    # Xabar yuborilganligini tekshirish

# 3. API testlar
from fastapi.testclient import TestClient
from dashboard.app import app

client = TestClient(app)

def test_api_stats():
    response = client.get("/api/stats")
    assert response.status_code == 200
    assert "products" in response.json()
```

### 6.2 Test fayllari

```
tests/
├── __init__.py
├── conftest.py              # Test sozlamalari
├── test_handlers/
│   ├── test_start.py
│   ├── test_production.py
│   └── test_warehouse.py
├── test_utils/
│   ├── test_calculations.py
│   └── test_helpers.py
└── test_api/
    └── test_dashboard.py
```

### 6.3 Test komandalari

```bash
# Barcha testlarni ishga tushirish
pytest

# Maxsus fayl
pytest tests/test_handlers/test_start.py

# Coverage bilan
pytest --cov=handlers --cov-report=html

# Async testlar
pytest-asyncio tests/
```

### 6.4 Sifat nazorati

```bash
# Code formatting
black .

# Linting
flake8 .

# Type checking
mypy .

# Import sorting
isort .
```

---

## 7. 💡 v3 — Qo'shilgan yangi modullar (TZ asosida)

### 7.0 Arxitektura yangilanishi

| Qatlam | v2 (eski) | v3 (hozir) |
|--------|-----------|------------|
| **Bot** | aiogram v3 | aiogram v3 (bir xil) |
| **Web/UI** | FastAPI ichidagi inline HTML | **Node.js** frontend (`web/`), FastAPI faqat REST API |
| **REST API** | 4 ta endpoint | 30+ endpoint (`/api/*`) |
| **Database** | SQLite | SQLite + avtomatik migratsiya (PostgreSQL'ga tayyor) |
| **Rollar** | faqat admin | To'liq rol matritsasi |

### 7.1 Ishga tushirish (v3)

```bash
# 1) Python REST API
python -m uvicorn dashboard.app:app --port 8000

# 2) Node.js web (npm install shart emas)
cd web && PORT=3000 PY_API_URL=http://127.0.0.1:8000 node server.js

# 3) Bot
python main.py
```

### 7.2 v3 modullar ro'yxati

| Funksiya | Bot | API | Node UI |
|----------|:---:|:---:|:---:|
| CRM / Mijozlar (nasiya limiti, FIFO qarz to'lovi, ballar) | ✅ | ✅ | ✅ |
| Sotuv: nasiya limit tekshiruvi, oldindan to'lov, chegirma | ✅ | — | ✅ |
| Yetkazib beruvchilar + sifat nazorati qabul aktlari | ✅ | ✅ | ✅ |
| Qayta buyurtma tavsiyalari (min stock) | ✅ | ✅ | ✅ |
| Rezervatsiya (2–24 soat, avto-yechish) | ✅ | ✅ | ✅ |
| Omborlararo ko'chirish | ✅ | ✅ | ✅ |
| Inventarizatsiya varaqalari + dalolatnoma | ✅ | ✅ | ✅ |
| O'lchov birliklari konvertatsiyasi | ✅ | ✅ | — |
| P&L, soliq kalkulyatori, qarz hisobotlari | ✅ | ✅ | ✅ |
| Rollar matritsasi boshqaruvi | ✅ | ✅ | ✅ |

> 💡 **Sodiqlik ballari qoidasi (v3):** ballar faqat **haqiqatda olingan pulga** beriladi — har 100 000 so'm = 1 ball.
> Naqd/karta sotuvda to'liq summaga, nasiya sotuvida **avansga**, qarz to'langanda esa **to'langan qismga** ball yoziladi.
> Sotuvni yozish `crud.create_sale_record()` orqali amalga oshiriladi (test: `tests/test_database/test_sales_flow.py`).

### 7.3 Rol matritsasi (config.py `ROLES`)

```python
ROLES = {
    "direktor": {..., "can_view": ["production", "warehouse", ...], "see_cost": True, "discount_limit": 100},
    "sotuvchi": {..., "can_edit": ["sales", "crm", "stock_ops"], "see_cost": False, "discount_limit": 5},
    "omborchi": {..., "see_cost": False},
    "buxgalter": {..., "see_cost": True},
}
```

### 7.4 Database avtomatik migratsiya

Eski `construction.db` yangi jadvallar/ustunlar bilan avtomatik yangilanadi —
`models.upgrade_schema()` `main.py` startup'ida va dashboard importida chaqiriladi.
Ma'lumot o'chirilmaydi, faqat `ALTER TABLE ADD COLUMN` + yangi jadval yaratish.

### 7.5 Qo'shimcha funksiyalar (kelajak)

| Funksiya | Tavsif | Muddati |
|----------|--------|---------|
| **📊 Real-time Dashboard** | WebSocket orqali yangilanish | 1-2 hafta |
| **🤖 Chatbot 2.0** | NLP asosidagi suhbat | 1-2 oy |
| **📱 Mobil ilova** | Flutter/React Native | 3-4 oy |
| **🔗 API Integration** | 1C, SAP bilan bog'lash | 2-3 oy |
| **📊 BI Tizimi** | Business Intelligence | 1-2 oy |
| ~~💳 To'lov tizimi~~ | ✅ Click, Payme integratsiya (dashboard/payments.py) | bajarildi |
| ~~↩️ Qaytarish akti~~ | ✅ Pul/almashtirish/bonus qaytarish (handlers/returns.py, ReturnAct) | bajarildi |
| ~~📍 GPS Tracking~~ | ✅ Yetkazib berish + GPS kuzatuv (handlers/delivery.py, Delivery/DeliveryLocation) | bajarildi |
| ~~🔬 Sifat nazorati (QC)~~ | ✅ Tayyor mahsulot chiqishida tekshiruv akti (database/crud.py `create_production_qc`, ProductionQC; bot `🔬 Sifat nazorati`; `POST /api/production/{id}/quality`) | bajarildi |

### 7.2 Yangi modullar

```python
# 1. CRM tizimi
class CRMModule:
    """Mijozlar bilan ishlash"""
    - Mijozlar bazasi
    - Buyurtmalar tarixi
    - Hisobotlar
    - Eslatmalar

# 2. ERP tizimi
class ERPModule:
    """Korxona resurslarni boshqarish"""
    - Ombor boshqaruvi
    - Ishlab chiqarish rejalashtirish
    - Moliya hisobi
    - Kadrlar boshqaruvi

# 3. IoT integratsiya
class IoTModule:
    """Internet of Things"""
    - Harorat sensorlari
    - Og'irlik sensorlari
    - Kamera tizimi
    - Avtomatik boshqarish

# 4. Sun'iy intellekt
class AIModule:
    """AI/ML funksiyalari"""
    - Rasm tanish (defektlarni aniqlash)
    - Talabni bashorat qilish
    - Narxni optimallashtirish
    - Chatbot (NLP)
```

### 7.3 Roadmap

```
2024 Q1:
├── ✅ Asosiy bot funksiyalari
├── ✅ PDF hisobotlar
├── ✅ SMS integratsiya
└── ✅ AI bashoratlar

2024 Q2:
├── 🔄 Web dashboard v2
├── 🔄 API v1
├── 🔄 Testing framework
└── 🔄 Docker deployment

2024 Q3:
├── 📋 ERP moduli
├── 📋 CRM moduli
├── 📋 To'lov tizimi
└── 📋 Mobil ilova

2024 Q4:
├── 📋 AI/ML modullari
├── 📋 IoT integratsiya
├── 📋 Multi-language
└── 📋 Enterprise versiya
```

---

## 📞 Qo'llab-quvvatlash

- **Email**: support@example.com
- **Telegram**: @support_bot
- **GitHub**: https://github.com/username/project

---

## 8. 🆕 v5 — To'liq REST API + narx tarixi + yangi Web sahifalar (TZ asosida)

### 8.1 v5 nima qo'shdi

| Modul | Tavsif | Fayllar |
| :--- | :--- | :--- |
| **REST API v5** | `construction_factory_bot.md` 2-bo'limidagi spec API ro'yxati bo'yicha 70+ endpoint: Users, Products, Categories, Orders (sotuv), Payments, Inventory, Reports, Suppliers, Production, Warehouses, Auth aliaslar | `dashboard/api_v5.py` |
| **Narx tarixi** | Har bir narx o'zgarishi `product_price_history` jadvaliga yangi qator sifatida yoziladi — istalgan sana uchun eski/yangi narx ko'rinadi. API: `GET /api/products/{id}/price-history`, bot: `💱 Narx tarixi` | `database/models.py`, `database/crud_v5.py` |
| **Omborlar** | `warehouses` jadvali + CRUD API (xomashyo/tayyor/brak turlari, sektorlar, mas'ul) | `database/crud_v5.py`, `api_v5` |
| **Web UI (6 sahifa)** | 💰 Sotuv (POS), 🏭 Ishlab chiqarish, 🚚 Yetkazib berish (+ imzo, GPS), ↩️ Qaytarish, 💵 Smena (kassa), 🛒 Do'kon buyurtmalari | `web/public/app_v5.js`, `index.html` |
| **PWA** | `manifest.json` + `sw.js` — mobil telefonda ilova kabi ishlaydi, offline rejimda oxirgi nusxa ko'rinadi | `web/public/` |

### 8.2 API tez ma'lumotnoma (v5)

```
POST /api/auth/login|logout|refresh|verify-2fa   # spec aliaslar
GET|PUT /api/auth/profile                        # profil
GET|POST /api/users · GET|PUT|DELETE /api/users/{id}
PUT /api/users/{id}/status|password
GET /api/products · POST /api/products · PUT /api/products/{id}
PUT /api/products/{id}/price (narx tarixiga yozadi)
PUT /api/products/{id}/stock · POST /api/products/import
GET /api/products/search|low-stock|top-selling|{id}/price-history
GET|POST /api/categories · PUT|DELETE /api/categories/{name}
PUT /api/customers/{id} · PUT /api/customers/{id}/credit
GET /api/customers/debtors|{id}/orders
POST /api/orders (sotuv) · PUT /api/orders/{num}/status · DELETE /api/orders/{num}
POST /api/orders/{num}/reserve · PUT /api/orders/{num}/cancel-reserve
GET|POST /api/payments · GET /api/payments/daily
GET /api/inventory · GET /api/inventory/{product_id}
PUT /api/inventory/adjust · GET /api/inventory/history
POST /api/deliveries/{id}/signature
GET /api/reports/daily|weekly|monthly|yearly|profit-loss|debt|top-customers|sales-by-category
POST /api/reports/export (CSV/Excel)
PUT /api/suppliers/{id} · GET /api/suppliers/{id}/purchases
GET|POST /api/production · PUT /api/production/{id}/status
GET|POST /api/warehouses · PUT /api/warehouses/{id}
```

### 8.3 Eslatma

- Router tartibi: `api_v5` avval ro'yxatdan o'tadi — literal yo'llar parametrli yo'llardan ustun turadi.
- `see_cost=False` rollar uchun tannarx maydonlari `CostVisibilityMiddleware` orqali kesiladi (yangi endpointlarda ham).
- Web UI yangi sahifalari `app_v5.js` da — `app.js`'ga tegmaydi, global `PAGES`/`RENDERERS`'ni kengaytiradi.

## 9. 🔖 v5.1 — Tranzaksiya kodi, avans fotosi, mijoz ma'lumotlari shifrlash

Qayta to'liq auditda (`construction_factory_bot.md` A–H "20+ nozik holat"
bo'limlari) topilgan qolgan bo'shliqlar yopildi:

| TZ talabi | Amalga oshirish |
| :--- | :--- |
| **Tranzaksiya kodi** (A: har bir operatsiyaga unikal 16 xonali kod) | `transaction_code` ustuni (`sales`, `return_acts`, `warehouse_transactions`); YYMMDD+10 raqam; yangi qatorlarda avtomatik, eski DB'ga `upgrade_schema` backfill; bot cheki va qaytarish aktida `🔖 Tranzaksiya` qatori |
| **Hujjatni kod orqali topish** (A: "soliqchilar tekshiruvida 1 daqiqada") | `GET /api/documents/lookup?code=...` — sotuv/qaytarish/ombor harakati; web POS'da "🔍 Hujjat izlash" kartasi |
| **Avans hisoboti fotosurati** (A: "fotosurat bilan yuklaydi") | `ExpenseReport.photo_path`; bot avans oqimida ixtiyoriy rasm qadami, direktor `🖼` tugmasi bilan ko'radi |
| **Mijozlar ma'lumotlari shifrlash** (F: "sotuvchi faqat ism va qarz") | `mask_customer_dict` — direktor/haydovchi to'liq; qolgan rollarga telefon maskalangan (`+998 ** *** ** 45`), manzil/izoh yashirin |

Yangi endpoint: `GET /api/documents/lookup?code=<16 raqam>` — javob: `{found, type: sale|return_act|warehouse_transaction, document}`.

## 10. 🆕 v5.2 — Spec yangi 3-bo'limi (FUNKSIONAL MODULLAR) bo'yicha

Remote'da yangilangan spec (3.1–3.15) audit qilindi; funksional bo'shliqlar:

| TZ talabi | Amalga oshirish |
| :--- | :--- |
| **Maxsus mijoz narxlari** (3.1) | `customer_prices` jadvali; `GET/PUT/DELETE /api/customers/{id}/prices`; `POST /api/orders` da `unit_price` berilmasa maxsus narx qo'llanadi |
| **Minimal zaxira** (3.1) | `Product.min_stock`; `GET /api/products/low-stock` har mahsulotning o'z `min_stock` chegarasini hisobga oladi |
| **Partiya va sertifikat** (3.2) | `RawMaterial.batch_number/certificate_number/expiry_date`; qabul aktida yoziladi; API + bot aktida ko'rinadi |

```
GET    /api/customers/{id}/prices
PUT    /api/customers/{id}/prices        {product_id, price}
DELETE /api/customers/{id}/prices/{product_id}
```

3.9–3.15 (AI/IoT/Event Sourcing/Feature Flags/ChatOps/SLO/Multi-Cloud) va
HPA/Spot kabi bulut bo'limlari — infratuzilma strategiyasi, roadmap'da.

## 11. 🆕 v5.3 — "TIZIM MUKAMMALLIGI" qoldiq bo'shliqlari

Spec'ning barcha bo'limlari (10 085 qator) yana bir bor to'liq audit qilindi;
16 ta kelajak bo'limi (Gen AI, Edge, Blockchain, AR/VR, biometrik, avtonom
dronlar, kvant, self-healing, DID, carbon, voice, predictive analytics,
digital twins, low-code, kripto, ESG) bundan mustasno. Yopilgan bo'shliqlar:

| TZ talabi | Amalga oshirish |
| :--- | :--- |
| **Transport vositalari** (ERD `vehicles`) | `vehicles` jadvali + `GET/POST/PUT/DELETE /api/vehicles`; `fuel_logs.vehicle_id`, `deliveries.vehicle_id`; bot "🚗 Transport" + web sahifa |
| **Ortiqcha zaxira** (ERD `max_stock`) | `Product.max_stock`; `GET /api/products/over-stock` |
| **Rangli ombor xaritasi** (B-bo'lim) | `GET /api/warehouses/fill-levels` — yashil/sariq/qizil to'liqlik |
| **"Nima bo'lsa?" tahlili** (E-bo'lim) | `GET /api/analytics/what-if?scenario=price_down&percent=5` — 90 kunlik prognoz |
| **Amal muddati eslatmasi** (3.1/3.2) | `GET /api/inventory/expiring?days=30` — yaqinlashgan/o'tgan xom ashyolar |
| **Xodimlar smenasi kalendari** (E-bo'lim) | `GET /api/work-schedule?month=YYYY-MM` — kun/soat/qo'shimcha vaqt |
| **Xodim ochiq operatsiyalari** (H-bo'lim) | `GET /api/employees/{id}/open-operations` — ishdan ketmoqchi xodim topshirig'i |
| **Trening simulyatori** ("Eng muhim taklif") | Bot "🎓 Trening": 4 mavzu, 3 savoldan, izoh + SERTIFIKAT |

Yangi modullar rol matritsasida: `vehicles` (direktor/haydovchi), `schedule`
(direktor), `analytics` (direktor/buxgalter), `training` (barcha rollar).

```
GET    /api/vehicles
POST   /api/vehicles             {number, brand, capacity, fuel_type, ...}
PUT    /api/vehicles/{id}
DELETE /api/vehicles/{id}
GET    /api/products/over-stock
GET    /api/warehouses/fill-levels
GET    /api/inventory/expiring?days=30
GET    /api/work-schedule?month=YYYY-MM
GET    /api/employees/{id}/open-operations
GET    /api/analytics/what-if?scenario=price_down&percent=5
```

## 12. 🚚 v5.4 — Yetkazib berishda mashina tanlash

TZ ERD `deliveries.vehicle_id` bo'yicha haydovchi va menejer transport
vositasini tanlaydi:

- `database/crud_v54.py`: `create_delivery_with_vehicle` (faol mashina
  tekshiruvi bilan), `set_delivery_vehicle` (haydovchi GPS boshlashda
  tayinlamagan topshiriqqa mashina tanlaydi), `delivery_with_vehicle_dict`
  (API javobida `vehicle_id`/`vehicle_number`).
- API: `POST /api/deliveries` endi `vehicle_id` qabul qiladi;
  `GET /api/deliveries` javobida mashina ma'lumoti bor.
- Bot: menejer topshiriq yaratishda haydovchidan keyin mashina tanlaydi
  ("🚫 Mashinasiz" ixtiyoriy); haydovchi GPS kuzatuvni boshlashda mashina
  tayinlanmagan bo'lsa o'zi tanlaydi. Topshiriq matnida "🚛 Mashina" qatori.
- Web: yetkazish formasida transport select + jadvalda mashina ustuni.

---

## 📝 Xulosa

Bu loyiha **to'liq va keng qamrovli** tizim. Quyidagi yo'nalishlarni rivojlantirish mumkin:

1. **🚀 Deploy** - Docker va CI/CD sozlash
2. **🧪 Testing** - Unit va integration testlar yozish
3. **🔒 Xavfsizlik** - 2FA, audit log, rate limiting
4. **📈 Masshtablash** - Redis, Celery, load balancing
5. **🌐 Web Portal** - To'liq web ilova yaratish
6. **🤖 AI/ML** - Chuqur o'rganish modullari

Har bir bosqich uchun alohida reja tuzish va amalga oshirish tavsiya etiladi.
