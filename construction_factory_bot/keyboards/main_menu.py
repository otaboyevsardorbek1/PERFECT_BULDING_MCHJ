from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def get_main_menu():
    """Asosiy menyu"""
    buttons = [
        [KeyboardButton(text="🏭 Ishlab chiqarish"), KeyboardButton(text="📦 Ombor holati")],
        [KeyboardButton(text="💰 Xarajat hisobi"), KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="➕ Xom ashyo kiritish"), KeyboardButton(text="📈 Hisobotlar")],
        [KeyboardButton(text="📄 PDF hisobotlar"), KeyboardButton(text="📱 SMS xizmati")],
        [KeyboardButton(text="🤖 AI bashorat"), KeyboardButton(text="⚙️ Sozlamalar")],
        [KeyboardButton(text="ℹ️ Yordam")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_production_menu():
    """Ishlab chiqarish menyusi"""
    buttons = [
        [KeyboardButton(text="🔄 Yangi buyurtma"), KeyboardButton(text="📋 Jarayondagilar")],
        [KeyboardButton(text="✅ Tayyor buyurtmalar"), KeyboardButton(text="📊 Ishlab chiqarish statistikasi")],
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
