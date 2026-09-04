"""
Konfiguratsiya fayli - Bot sozlamalari
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

# =============== BOT SOZLAMALARI ===============
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN .env faylida belgilanishi shart!")

ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(','))) if os.getenv("ADMIN_IDS") else []
MAIN_ADMIN_ID = int(os.getenv("MAIN_ADMIN_ID", ADMIN_IDS[0] if ADMIN_IDS else 0))

# =============== DATABASE SOZLAMALARI ===============
# PostgreSQL uchun
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "construction_factory")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")

# Database URL (PostgreSQL)
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# SQLite uchun (agar PostgreSQL bo'lmasa)
# SQLITE_DB_PATH muhit o'zgaruvchisi orqali ham o'rnatilishi mumkin
# (masalan test/E2E muhitida databaseni vaqtinchalik papkaga yo'naltirish uchun)
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "database/construction.db")
DB_PATH = SQLITE_DB_PATH  # db.py foydalanadi
SQLITE_URL = f"sqlite:///{SQLITE_DB_PATH}"

# Qaysi databaseni ishlatish
USE_POSTGRESQL = os.getenv("USE_POSTGRESQL", "false").lower() == "true"
DATABASE_URL = DATABASE_URL if USE_POSTGRESQL else SQLITE_URL

# =============== LOYIHA YO'LLARI ===============
BASE_DIR = Path(__file__).parent

# Hisobotlar papkalari
REPORTS_DIR = BASE_DIR / "reports"
EXCEL_REPORTS_DIR = REPORTS_DIR / "excel"
CHARTS_DIR = REPORTS_DIR / "charts"
# BACKUP_DIR muhit o'zgaruvchisi orqali o'zgartirilishi mumkin (E2E/test uchun)
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", str(BASE_DIR / "backups")))
LOGS_DIR = BASE_DIR / "logs"
STATIC_DIR = BASE_DIR / "static"
IMAGES_DIR = STATIC_DIR / "images"

# Papkalarni yaratish
for directory in [REPORTS_DIR, EXCEL_REPORTS_DIR, CHARTS_DIR, BACKUP_DIR, LOGS_DIR, STATIC_DIR, IMAGES_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# =============== MATERIAL VA MAHSULOT SOZLAMALARI ===============
MATERIAL_UNITS = {
    "kg": "kilogram",
    "t": "tonna", 
    "m": "metr",
    "m2": "kvadrat metr",
    "m3": "kub metr",
    "dona": "dona",
    "qop": "qop",
    "l": "litr",
    "ta": "ta"
}

PRODUCT_CATEGORIES = {
    "sement": "Sement mahsulotlari",
    "rodbin": "Metall mahsulotlar",
    "kafel": "Kafel va plitka",
    "pol": "Pol qoplamalari",
    "gips": "Gips mahsulotlari",
    "keramika": "Keramika mahsulotlari",
    "boshqa": "Boshqa qurilish materiallari"
}

# =============== SOTUVLAR SOZLAMALARI ===============
ADMINS = ADMIN_IDS  # sales.py foydalanadi

PRODUCT_TYPES = {
    "sement": "Sement mahsulotlari",
    "rodbin": "Metall mahsulotlar",
    "kafel": "Kafel va plitka",
    "pol": "Pol qoplamalari",
    "gips": "Gips mahsulotlari",
    "keramika": "Keramika mahsulotlari",
    "boshqa": "Boshqa qurilish materiallari"
}

# =============== XODIMLAR SOZLAMALARI ===============
EMPLOYEE_POSITIONS = {
    "director": "Direktor",
    "manager": "Menejer",
    "engineer": "Muhandis",
    "worker": "Ishchi",
    "driver": "Haydovchi",
    "accountant": "Buxgalter",
    "storekeeper": "Omborchi",
    "technician": "Texnik",
    "supervisor": "Nazoratchi",
    "assistant": "Yordamchi"
}

# =============== ROLLAR MATRITSASI (v3) ===============
# Har bir rol: qaysi modullarni ko'ra oladi / o'zgartira oladi
# Modul kalitlari: production, warehouse, sales, crm, supplier, stock_ops (rezerv/ko'chirish), finance, reports, employees, admin, sms, ai, delivery, cash_shift
ROLES = {
    "direktor": {
        "label": "👑 Direktor",
        "can_view": ["production", "warehouse", "sales", "crm", "supplier", "stock_ops", "finance", "reports", "employees", "admin", "sms", "ai", "delivery", "cash_shift", "fuel", "expenses", "picking", "security", "ratings"],
        "can_edit": ["production", "warehouse", "sales", "crm", "supplier", "stock_ops", "finance", "reports", "employees", "admin", "sms", "ai", "delivery", "cash_shift", "fuel", "expenses", "picking", "security", "ratings"],
        "see_cost": True,
        "discount_limit": 100,
    },
    "sotuvchi": {
        "label": "🛒 Sotuvchi",
        "can_view": ["sales", "crm", "warehouse", "stock_ops", "delivery"],
        "can_edit": ["sales", "crm", "stock_ops", "delivery"],
        "see_cost": False,  # Tannarxni ko'ra olmaydi!
        "discount_limit": 5,  # 5% dan ortiq chegirma bera olmaydi
    },
    "kassir": {
        "label": "💵 Kassir",
        "can_view": ["sales", "cash_shift"],
        "can_edit": ["sales", "cash_shift"],
        "see_cost": False,
        "discount_limit": 0,
    },
    "omborchi": {
        "label": "📦 Omborchi",
        "can_view": ["warehouse", "supplier", "stock_ops", "picking"],
        "can_edit": ["warehouse", "supplier", "stock_ops", "picking"],
        "see_cost": False,  # Narxlarni ko'ra olmaydi
        "discount_limit": 0,
    },
    "haydovchi": {
        "label": "🚚 Haydovchi",
        "can_view": ["warehouse", "stock_ops", "delivery", "fuel", "expenses", "picking"],
        "can_edit": ["delivery", "fuel", "expenses"],
        "see_cost": False,
        "discount_limit": 0,
    },
    "buxgalter": {
        "label": "🧮 Buxgalter",
        "can_view": ["finance", "reports", "crm", "warehouse", "cash_shift", "fuel", "expenses"],
        "can_edit": ["finance", "expenses"],
        "see_cost": True,
        "discount_limit": 0,
    },
    "ishchi": {
        "label": "🔧 Ishchi",
        "can_view": ["production", "warehouse"],
        "can_edit": [],
        "see_cost": False,
        "discount_limit": 0,
    },
}

ROLE_LABELS = {key: val["label"] for key, val in ROLES.items()}

def role_can_view(role: str, module: str) -> bool:
    """Rol modulni ko'ra oladimi"""
    info = ROLES.get(role or "ishchi", ROLES["ishchi"])
    return module in info["can_view"]

def role_can_edit(role: str, module: str) -> bool:
    """Rol modulda o'zgartirish qila oladimi"""
    info = ROLES.get(role or "ishchi", ROLES["ishchi"])
    return module in info["can_edit"]

def role_see_cost(role: str) -> bool:
    """Rol tannarxni ko'ra oladimi"""
    return ROLES.get(role or "ishchi", ROLES["ishchi"]).get("see_cost", False)

def get_role_label(role: str) -> str:
    return ROLE_LABELS.get(role or "ishchi", role or "ishchi")

EMPLOYEE_DEPARTMENTS = {
    "production": "Ishlab chiqarish",
    "warehouse": "Ombor",
    "sales": "Sotuv",
    "accounting": "Buxgalteriya",
    "management": "Rahbariyat",
    "logistics": "Logistika",
    "quality": "Sifat nazorati",
    "maintenance": "Texnik xizmat",
    "hr": "Kadrlar bo'limi"
}

# =============== BILDIRISHNOMA SOZLAMALARI ===============
NOTIFICATION_TYPES = {
    "low_stock": "Xom ashyo tugashi",
    "production_complete": "Ishlab chiqarish tugashi",
    "order_delivered": "Buyurtma yetkazib berildi",
    "salary_payment": "Maosh to'lovi",
    "system_alert": "Tizim ogohlantirishi",
    "daily_report": "Kunlik hisobot",
    "weekly_report": "Haftalik hisobot",
    "monthly_report": "Oylik hisobot",
    "slow_stock": "Sekin sotiladigan zaxira",
    "holiday": "Bayram tabriklari",
    "birthday": "Tug'ilgan kun tabriklari",
    "emergency": "Favqulodda vaziyat"
}

NOTIFICATION_PRIORITIES = {
    1: {"name": "Past", "icon": "🟢", "delay": 3600},  # 1 soat
    2: {"name": "Oʻrta", "icon": "🟡", "delay": 1800},  # 30 daqiqa
    3: {"name": "Yuqori", "icon": "🟠", "delay": 600},   # 10 daqiqa
    4: {"name": "Juda yuqori", "icon": "🔴", "delay": 300},  # 5 daqiqa
    5: {"name": "Favqulodda", "icon": "🚨", "delay": 60}   # 1 daqiqa
}

# =============== ISHLAB CHIQARISH SOZLAMALARI ===============
PRODUCTION_SETTINGS = {
    "default_profit_margin": 0.4,  # 40%
    "labor_cost_percentage": 0.3,  # 30%
    "energy_cost_percentage": 0.1,  # 10%
    "waste_percentage": 0.05,  # 5%
    "default_priority": 2,
    "max_production_per_day": 1000,
    "min_production_quantity": 1,
    "max_production_quantity": 10000
}

# =============== XAVFSIZLIK SOZLAMALARI ===============
SECURITY_SETTINGS = {
    "max_login_attempts": 5,
    "session_timeout": 3600,  # 1 soat
    "password_min_length": 8,
    "require_strong_password": True,
    "enable_2fa": False,
    "ip_whitelist": [],
    "block_suspicious_activity": True
}

# =============== EXCEL HISOBOT SOZLAMALARI ===============
EXCEL_SETTINGS = {
    "default_style": "Medium",
    "currency_format": "#,##0",
    "date_format": "YYYY-MM-DD",
    "time_format": "HH:MM",
    "auto_adjust_columns": True,
    "include_charts": True,
    "max_rows_per_sheet": 100000,
    "compression_level": 6
}

# =============== GRAFIK SOZLAMALARI ===============
CHART_SETTINGS = {
    "default_width": 16,
    "default_height": 9,
    "dpi": 300,
    "style": "seaborn",
    "color_palette": "husl",
    "font_size": {
        "title": 16,
        "labels": 12,
        "ticks": 10,
        "legend": 10
    },
    "save_format": "png",  # png, pdf, svg
    "transparent_background": False
}

# =============== BACKUP SOZLAMALARI ===============
# Rejali avtomatik backup (fon vazifasida kuniga bir marta; utils/backup.py)
BACKUP_SETTINGS = {
    "enabled": os.getenv("BACKUP_ENABLED", "true").lower() == "true",
    "schedule": os.getenv("BACKUP_SCHEDULE", "daily"),  # daily, weekly (dushanba), monthly (1-kun)
    "time": os.getenv("BACKUP_TIME", "02:00"),  # Backup vaqti (24 soat formatida HH:MM)
    "keep_days": int(os.getenv("BACKUP_KEEP_DAYS", "30")),  # 30 kun saqlash
    "compression": os.getenv("BACKUP_COMPRESSION", "zip"),  # zip, gzip, none (zaxira .db sifatida saqlanadi)
    "include_logs": True,
    "include_reports": False,
    "notify_on_backup": os.getenv("BACKUP_NOTIFY", "true").lower() == "true"
}

# =============== BACKUPNI UZOQ JOYGA YUKLASH ===============
# Har bir backup faylni uzoq joyda saqlash (favqulodda holatda serverda
# muammo bo'lsa ham nusxa mavjud bo'ladi).
# remote: "none" (o'chirilgan) | "telegram" (kanalga) | "s3" (S3-mos bulut)
#         yoki ikkalasi: "telegram,s3" (har bir backup hammaga yuklanadi)
BACKUP_UPLOAD_SETTINGS = {
    "remote": os.getenv("BACKUP_UPLOAD", "none").lower(),
    # Telegram: @kanal_nomi yoki -100... (bot kanalga admin qo'shilgan bo'lishi kerak)
    "telegram_channel": os.getenv("BACKUP_TELEGRAM_CHANNEL_ID", ""),
    # S3-mos xizmat (AWS S3, MinIO, Wasabi, DigitalOcean Spaces, Yandex Cloud...)
    # Endpoint misollar: https://s3.amazonaws.com | http://localhost:9000 (MinIO)
    "s3_endpoint": os.getenv("BACKUP_S3_ENDPOINT", ""),
    "s3_region": os.getenv("BACKUP_S3_REGION", "us-east-1"),
    "s3_bucket": os.getenv("BACKUP_S3_BUCKET", ""),
    "s3_access_key": os.getenv("BACKUP_S3_ACCESS_KEY", ""),
    "s3_secret_key": os.getenv("BACKUP_S3_SECRET_KEY", ""),
    "s3_prefix": os.getenv("BACKUP_S3_PREFIX", "backups"),  # bucket ichidagi papka
    # UZOQ JOYDAGI nusxalar necha kun saqlanadi (Telegram kanal / S3 bucket).
    # 0 bo'lsa uzoq joyda tozalash o'chiriladi. Berilmasa BACKUP_KEEP_DAYS ishlatiladi.
    "remote_keep_days": int(os.getenv("BACKUP_REMOTE_KEEP_DAYS", "") or BACKUP_SETTINGS["keep_days"]),
}

# =============== BACKUP SHIFRLASH (chiquvchi nusxalar) ===============
# Parol qo'yilsa, SERVERDAN CHIQADIGAN har bir backup fayl shifrlanadi
# (PBKDF2 + AES — Fernet) va shifrlangan holatda Telegram/S3 ga yuklanadi.
# Lokal nusxa (backups/) shifrlanmaydi — parol faqat .env da saqlanadi.
# Shifrlangan faylni ochish: utils/backup.py decrypt_backup_file()
BACKUP_ENCRYPTION_PASSWORD = os.getenv("BACKUP_ENCRYPTION_PASSWORD", "")

# =============== LIMITLAR ===============
LIMITS = {
    "max_file_size": 10 * 1024 * 1024,  # 10 MB
    "max_excel_rows": 100000,
    "max_chart_points": 1000,
    "max_notifications_per_day": 100,
    "max_employees": 1000,
    "max_products": 1000,
    "max_raw_materials": 500,
    "max_transactions_per_day": 10000
}

# =============== TIZIM SOZLAMALARI ===============
SYSTEM_SETTINGS = {
    "debug_mode": os.getenv("DEBUG_MODE", "false").lower() == "true",
    "maintenance_mode": False,
    "auto_update": True,
    "notify_on_error": True,
    "log_level": "INFO",  # DEBUG, INFO, WARNING, ERROR
    "timezone": "Asia/Tashkent",
    "language": "uz",  # uz, ru, en
    "currency": "UZS",
    "date_format": "YYYY-MM-DD",
    "decimal_separator": ".",
    "thousands_separator": ","
}

# =============== INTEGRATSIYA SOZLAMALARI ===============
INTEGRATION_SETTINGS = {
    # SMS yuborish uchun (Eskiz.uz)
    "sms_enabled": os.getenv("SMS_ENABLED", "false").lower() == "true",
    "sms_provider": "eskiz.uz",
    "sms_api_key": os.getenv("SMS_API_KEY", ""),
    "sms_sender": os.getenv("SMS_SENDER", "KORXONA"),
    
    # Email yuborish uchun
    "email_enabled": False,
    "email_host": "smtp.gmail.com",
    "email_port": 587,
    "email_username": os.getenv("EMAIL_USERNAME", ""),
    "email_password": os.getenv("EMAIL_PASSWORD", ""),
    
    # Telegram kanal/guruh
    "telegram_channel_id": os.getenv("TELEGRAM_CHANNEL_ID", ""),
    "telegram_group_id": os.getenv("TELEGRAM_GROUP_ID", ""),
    
    # API endpoints
    "api_enabled": False,
    "api_host": "0.0.0.0",
    "api_port": 8000,
    "api_secret_key": os.getenv("API_SECRET_KEY", "")
}

# =============== WEB SOZLAMALARI (Node.js frontend) ===============
WEB_SETTINGS = {
    "port": int(os.getenv("WEB_PORT", "3000")),
    "python_api_url": os.getenv("PYTHON_API_URL", "http://127.0.0.1:8000"),
    "cors_origins": os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(","),
}

# =============== ONLAYN TO'LOVLAR (Click / Payme) ===============
# Click: https://my.click.uz kabineti -> Service ID va Secret key (SHOP API ulangan bo'lishi kerak)
CLICK_MERCHANT_ID = os.getenv("CLICK_MERCHANT_ID", "")
CLICK_SERVICE_ID = os.getenv("CLICK_SERVICE_ID", "")
CLICK_SECRET_KEY = os.getenv("CLICK_SECRET_KEY", "")
# Payme: Payme Business kabineti -> Merchant (cashbox) ID va kalit (parol)
PAYME_MERCHANT_ID = os.getenv("PAYME_MERCHANT_ID", "")
PAYME_KEY = os.getenv("PAYME_KEY", "")
# Mijoz to'lovdan keyin qaytadigan sahifa (ixtiyoriy, masalan web dashboard)
PAYMENT_RETURN_URL = os.getenv("PAYMENT_RETURN_URL", "")

# =============== QAYTARISH AKTI (RETURN) ===============
# Mijoz tovarni necha kun ichida qaytarishi mumkin (TZ: 7 kun)
RETURN_PERIOD_DAYS = int(os.getenv("RETURN_PERIOD_DAYS", "7"))

# =============== NASIYA QARZ ESLATMALARI (SMS) ===============
# Muddati o'tgan qarz uchun SMS eslatma yuboriladigan kunlar (muddati o'tgandan keyin).
# Har bir chegara har bir sotuv uchun bir marta yuboriladi (sale_id + day_bucket unikal).
DEBT_REMINDER_DAYS = sorted(
    int(x) for x in os.getenv("DEBT_REMINDER_DAYS", "3,7,14,30").split(",")
    if x.strip().isdigit()
)

# =============== SEKIN SOTILADIGAN ZAXIRA (SLOW-MOVING STOCK) ===============
# Tovar/xom ashyo necha kundan beri harakatlanmasa (sotuv, ishlab chiqarish, kirim,
# qaytarish, ko'chirish) ogohlantirish yuboriladi. Ogohlantirish tovar harakatga
# qaytguncha bir marta yuboriladi (SlowStockAlert jadvali unikalligi).
SLOW_STOCK_DAYS = int(os.getenv("SLOW_STOCK_DAYS", "30"))

# =============== TEST SOZLAMALARI ===============
TEST_SETTINGS = {
    "test_mode": os.getenv("TEST_MODE", "false").lower() == "true",
    "test_database": "test_construction.db",
    "test_admin_id": 123456789,
    "skip_payments": True,
    "skip_notifications": False,
    "generate_sample_data": True
}

# Nasiya to'lov usullari
PAYMENT_METHODS = {
    "cash": "💵 Naqd",
    "card": "💳 Karta",
    "payme": "📱 Payme",
    "click": "📱 Click",
    "transfer": "🏦 O'tkazma",
    "credit": "📝 Nasiya",
}

# Ombor turlari (3 xil ombor)
WAREHOUSE_TYPES = ["xomashyo", "tayyor", "brak", "asosiy"]

# =============== FUNKSIYALAR ===============
def get_database_url():
    """Database URL ni olish"""
    return DATABASE_URL

def is_admin(user_id: int) -> bool:
    """Foydalanuvchi admin ekanligini tekshirish"""
    return user_id in ADMIN_IDS

def is_main_admin(user_id: int) -> bool:
    """Foydalanuvchi asosiy admin ekanligini tekshirish"""
    return user_id == MAIN_ADMIN_ID

def format_currency(amount: float) -> str:
    """Pul miqdorini formatlash"""
    return f"{amount:,.0f} {SYSTEM_SETTINGS['currency']}"

def format_date(date_obj) -> str:
    """Sana ni formatlash"""
    if SYSTEM_SETTINGS['date_format'] == "DD-MM-YYYY":
        return date_obj.strftime("%d-%m-%Y")
    elif SYSTEM_SETTINGS['date_format'] == "MM/DD/YYYY":
        return date_obj.strftime("%m/%d/%Y")
    else:  # YYYY-MM-DD
        return date_obj.strftime("%Y-%m-%d")
def get_language_text(key: str, language: str = None) -> str:  # type: ignore
    """Tilga mos matnni olish"""
    if language is None:
        language = SYSTEM_SETTINGS['language']

    texts = {
        "uz": {
            "welcome": "Xush kelibsiz!",
            "error": "Xatolik yuz berdi",
            "success": "Muvaffaqiyatli bajarildi",
            "confirm": "Tasdiqlaysizmi?",
            "cancel": "Bekor qilish",
            "save": "Saqlash",
            "delete": "Oʻchirish",
            "edit": "Tahrirlash",
            "view": "Koʻrish",
            "add": "Qoʻshish",
            "search": "Qidirish",
            "filter": "Filtr",
            "sort": "Saralash",
            "export": "Eksport",
            "import": "Import",
            "print": "Chop etish",
            "refresh": "Yangilash",
            "help": "Yordam",
            "settings": "Sozlamalar",
            "logout": "Chiqish",
            "login": "Kirish",
            "register": "Roʻyxatdan oʻtish",
            "profile": "Profil",
            "dashboard": "Boshqaruv paneli",
            "reports": "Hisobotlar",
            "statistics": "Statistika",
            "notifications": "Bildirishnomalar",
            "messages": "Xabarlar",
            "calendar": "Kalendar",
            "tasks": "Vazifalar",
            "projects": "Loyihalar",
            "employees": "Xodimlar",
            "customers": "Mijozlar",
            "products": "Mahsulotlar",
            "orders": "Buyurtmalar",
            "inventory": "Inventarizatsiya",
            "warehouse": "Ombor",
            "production": "Ishlab chiqarish",
            "sales": "Sotuv",
            "purchases": "Xaridlar",
            "finance": "Moliya",
            "accounting": "Buxgalteriya",
            "hr": "Kadrlar",
            "administration": "Administratsiya",
            "system": "Tizim",
            "security": "Xavfsizlik",
            "backup": "Zaxira nusxa",
            "restore": "Tiklash",
            "update": "Yangilash",
            "maintenance": "Texnik xizmat"
        },

        "ru": {
            "welcome": "Добро пожаловать!",
            "error": "Произошла ошибка",
            "success": "Успешно выполнено",
            "confirm": "Подтвердить?",
            "cancel": "Отмена",
            "save": "Сохранить",
            "delete": "Удалить",
            "edit": "Редактировать",
            "view": "Просмотр",
            "add": "Добавить",
            "search": "Поиск",
            "filter": "Фильтр",
            "sort": "Сортировка",
            "export": "Экспорт",
            "import": "Импорт",
            "print": "Печать",
            "refresh": "Обновить",
            "help": "Помощь",
            "settings": "Настройки",
            "logout": "Выход",
            "login": "Вход",
            "register": "Регистрация",
            "profile": "Профиль",
            "dashboard": "Панель управления",
            "reports": "Отчёты",
            "statistics": "Статистика",
            "notifications": "Уведомления",
            "messages": "Сообщения",
            "calendar": "Календарь",
            "tasks": "Задачи",
            "projects": "Проекты",
            "employees": "Сотрудники",
            "customers": "Клиенты",
            "products": "Товары",
            "orders": "Заказы",
            "inventory": "Инвентаризация",
            "warehouse": "Склад",
            "production": "Производство",
            "sales": "Продажи",
            "purchases": "Закупки",
            "finance": "Финансы",
            "accounting": "Бухгалтерия",
            "hr": "Кадры",
            "administration": "Администрирование",
            "system": "Система",
            "security": "Безопасность",
            "backup": "Резервное копирование",
            "restore": "Восстановление",
            "update": "Обновление",
            "maintenance": "Техническое обслуживание"
        },

        "en": {
            "welcome": "Welcome!",
            "error": "An error occurred",
            "success": "Successfully completed",
            "confirm": "Do you confirm?",
            "cancel": "Cancel",
            "save": "Save",
            "delete": "Delete",
            "edit": "Edit",
            "view": "View",
            "add": "Add",
            "search": "Search",
            "filter": "Filter",
            "sort": "Sort",
            "export": "Export",
            "import": "Import",
            "print": "Print",
            "refresh": "Refresh",
            "help": "Help",
            "settings": "Settings",
            "logout": "Logout",
            "login": "Login",
            "register": "Register",
            "profile": "Profile",
            "dashboard": "Dashboard",
            "reports": "Reports",
            "statistics": "Statistics",
            "notifications": "Notifications",
            "messages": "Messages",
            "calendar": "Calendar",
            "tasks": "Tasks",
            "projects": "Projects",
            "employees": "Employees",
            "customers": "Customers",
            "products": "Products",
            "orders": "Orders",
            "inventory": "Inventory",
            "warehouse": "Warehouse",
            "production": "Production",
            "sales": "Sales",
            "purchases": "Purchases",
            "finance": "Finance",
            "accounting": "Accounting",
            "hr": "Human Resources",
            "administration": "Administration",
            "system": "System",
            "security": "Security",
            "backup": "Backup",
            "restore": "Restore",
            "update": "Update",
            "maintenance": "Maintenance"
        }
    }

    return texts.get(language, texts["uz"]).get(key, key)


# Konfiguratsiyani tekshirish
def validate_config():
    """Konfiguratsiyani tekshirish"""
    
    errors = []
    
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN belgilanishi shart!")
    
    if not ADMIN_IDS:
        errors.append("ADMIN_IDS kamida bitta admin ID belgilanishi shart!")
    
    if USE_POSTGRESQL and not all([DB_HOST, DB_NAME, DB_USER]):
        errors.append("PostgreSQL sozlamalari toʻliq emas!")
    
    if errors:
        raise ValueError(f"Konfiguratsiya xatolari: {', '.join(errors)}")
    
    return True

# Dastur ishga tushganda konfiguratsiyani tekshirish
if __name__ == "__main__":
    try:
        validate_config()
        print("✅ Konfiguratsiya toʻgʻri sozlandi!")
    except ValueError as e:
        print(f"❌ Konfiguratsiya xatosi: {e}")