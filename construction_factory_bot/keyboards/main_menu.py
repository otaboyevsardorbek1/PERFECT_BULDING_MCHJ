from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from config import role_can_view


# Menyu satrlari: (label, modul) — modul ro'l matritsasida tekshiriladi
_MAIN_ROWS = [
    ("🏭 Ishlab chiqarish", "production"),
    ("📦 Ombor holati", "warehouse"),
    ("💰 Sotuvlar", "sales"),
    ("👥 Mijozlar", "crm"),
    ("🚚 Yetkazib beruvchilar", "supplier"),
    ("🔒 Rezervatsiya", "stock_ops"),
    ("🔄 Ko'chirish", "stock_ops"),
    ("📋 Inventarizatsiya", "stock_ops"),
    ("💱 Konvertatsiya", "stock_ops"),
    ("🧾 Nasiya to'lovlari", "finance"),
    ("💰 Xarajat hisobi", "finance"),
    ("🚚 Yetkazib berish", "delivery"),
    ("📊 Statistika", "reports"),
    ("💵 Smena (kassa)", "cash_shift"),
    ("➕ Xom ashyo kiritish", "warehouse"),
    ("💱 Narx tarixi", "warehouse"),
    ("📈 Hisobotlar", "reports"),
    ("📄 PDF hisobotlar", "reports"),
    ("📱 SMS xizmati", "sms"),
    ("🤖 AI bashorat", "ai"),
    ("⏳ Amal muddati", "warehouse"),
    ("🚗 Transport", "vehicles"),
    ("📅 Smena kalendari", "schedule"),
    ("🤔 Nima bo'lsa?", "analytics"),
    ("🎓 Trening", "training"),
    ("👑 Admin paneli", "admin"),
    ("⚙️ Sozlamalar", "all"),
    ("ℹ️ Yordam", "all"),
]

# Auth tugmalari (v4) — har doim ko'rinadi (login oldi/xavfsizlik boshqaruvi)
_AUTH_ROWS = [
    ("🔐 Kirish (login)", "all"),
    ("📊 Sessiya holati", "all"),
    ("🚪 Chiqish (logout)", "all"),
]


def get_main_menu(role: str = None):
    """
    Asosiy menyu.
    role berilmasa — to'liq menyu (eski funksionallik saqlanadi).
    role berilsa — rolga ruxsat etilgan modullar ko'rsatiladi.
    """
    buttons = []
    all_rows = _MAIN_ROWS + _AUTH_ROWS
    for i in range(0, len(all_rows), 2):
        row_items = all_rows[i:i + 2]
        row_buttons = []
        for label, module in row_items:
            if role and module != "all" and not role_can_view(role, module):
                continue
            row_buttons.append(KeyboardButton(text=label))
        if row_buttons:
            buttons.append(row_buttons)
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_production_menu():
    """Ishlab chiqarish menyusi"""
    buttons = [
        [KeyboardButton(text="🔄 Yangi buyurtma"), KeyboardButton(text="📋 Jarayondagilar")],
        [KeyboardButton(text="✅ Tayyor buyurtmalar"), KeyboardButton(text="🔬 Sifat nazorati")],
        [KeyboardButton(text="📊 Ishlab chiqarish statistikasi"), KeyboardButton(text="📋 QC tarixi")],
        [KeyboardButton(text="⬅️ Orqaga")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_qc_status_keyboard():
    """Sifat nazorati natijasi tugmalari"""
    buttons = [
        [KeyboardButton(text="✅ Qabul qilindi"), KeyboardButton(text="⚠️ Qisman qabul")],
        [KeyboardButton(text="❌ Rad etilgan"), KeyboardButton(text="❌ Bekor qilish")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_crm_menu():
    """Mijozlar (CRM) menyusi"""
    buttons = [
        [KeyboardButton(text="➕ Yangi mijoz"), KeyboardButton(text="🔍 Mijoz qidirish")],
        [KeyboardButton(text="📋 Barcha mijozlar"), KeyboardButton(text="🧾 Qarz to'lovi")],
        [KeyboardButton(text="📊 CRM statistika"), KeyboardButton(text="⬅️ Orqaga")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_supplier_menu():
    """Yetkazib beruvchilar menyusi"""
    buttons = [
        [KeyboardButton(text="➕ Yangi yetkazib beruvchi"), KeyboardButton(text="📋 Yetkazib beruvchilar")],
        [KeyboardButton(text="📦 Qabul qilish akti"), KeyboardButton(text="🛒 Qayta buyurtma tavsiyalari")],
        [KeyboardButton(text="⬅️ Orqaga")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_stock_ops_menu():
    """Ombor operatsiyalari (v3) menyusi"""
    buttons = [
        [KeyboardButton(text="🔒 Rezervatsiya yaratish"), KeyboardButton(text="📋 Faol rezervatsiyalar")],
        [KeyboardButton(text="🔄 Ko'chirish yaratish"), KeyboardButton(text="📋 Ko'chirishlar tarixi")],
        [KeyboardButton(text="📋 Inventarizatsiya o'tkazish"), KeyboardButton(text="💱 Konvertatsiya bajarish")],
        [KeyboardButton(text="⬅️ Orqaga")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_products_keyboard():
    """Mahsulotlar tugmalari — database'dan faol mahsulotlarni oladi"""
    from database.session import get_db_session
    from database.models import Product

    with get_db_session() as db:
        products = db.query(Product).filter(Product.is_active == True).order_by(Product.name).all()

    if not products:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ Mahsulotlar topilmadi", callback_data="noop")]
        ])

    rows = []
    for product in products:
        label = f"{product.name} ({product.selling_price:,.0f} so'm)" if product.selling_price else product.name
        rows.append([InlineKeyboardButton(text=label, callback_data=f"product_{product.id}")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_confirm_keyboard():
    """Tasdiqlash tugmalari"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="confirm_yes"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="confirm_no"),
        ]
    ])


def get_report_period_keyboard():
    """Hisobot davri tugmalari"""
    rows = [
        [InlineKeyboardButton(text="Kunlik", callback_data="report_daily"),
         InlineKeyboardButton(text="Haftalik", callback_data="report_weekly"),
         InlineKeyboardButton(text="Oylik", callback_data="report_monthly")],
        [InlineKeyboardButton(text="Choraklik", callback_data="report_quarterly"),
         InlineKeyboardButton(text="Yillik", callback_data="report_yearly")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
