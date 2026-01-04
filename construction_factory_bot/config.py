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
SQLITE_DB_PATH = "database/construction.db"
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
BACKUP_DIR = BASE_DIR / "backups"
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
BACKUP_SETTINGS = {
    "enabled": True,
    "schedule": "daily",  # daily, weekly, monthly
    "time": "02:00",  # Backup vaqti (24 soat formatida)
    "keep_days": 30,  # 30 kun saqlash
    "compression": "zip",  # zip, gzip, none
    "include_logs": True,
    "include_reports": False,
    "notify_on_backup": True
}

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
    # SMS yuborish uchun (agar kerak bo'lsa)
    "sms_enabled": False,
    "sms_provider": "eskiz.uz",
    "sms_api_key": os.getenv("SMS_API_KEY", ""),
    "sms_sender": "KORXONA",
    
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

# =============== TEST SOZLAMALARI ===============
TEST_SETTINGS = {
    "test_mode": os.getenv("TEST_MODE", "false").lower() == "true",
    "test_database": "test_construction.db",
    "test_admin_id": 123456789,
    "skip_payments": True,
    "skip_notifications": False,
    "generate_sample_data": True
}

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