from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu():
    """Asosiy menyu"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    buttons = [
        KeyboardButton("🏭 Ishlab chiqarish"),
        KeyboardButton("📦 Ombor holati"),
        KeyboardButton("💰 Xarajat hisobi"),
        KeyboardButton("📊 Statistika"),
        KeyboardButton("➕ Xom ashyo kiritish"),
        KeyboardButton("📈 Hisobotlar"),
        KeyboardButton("⚙️ Sozlamalar"),
        KeyboardButton("ℹ️ Yordam")
    ]
    
    keyboard.add(*buttons)
    return keyboard

def get_production_menu():
    """Ishlab chiqarish menyusi"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    buttons = [
        KeyboardButton("🔄 Yangi buyurtma"),
        KeyboardButton("📋 Jarayondagilar"),
        KeyboardButton("✅ Tayyor buyurtmalar"),
        KeyboardButton("📊 Ishlab chiqarish statistikasi"),
        KeyboardButton("⬅️ Orqaga")
    ]
    
    keyboard.add(*buttons)
    return keyboard

def get_products_keyboard():
    """Mahsulotlar tugmalari"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    products = [
        ("Sement", "sement"),
        ("Rodbin", "rodbin"),
        ("Kafel", "kafel"),
        ("Nalinoy pol", "nalinoy_pol"),
        ("Gips", "gips"),
        ("Keramika", "keramika")
    ]
    
    for name, code in products:
        keyboard.insert(InlineKeyboardButton(name, callback_data=f"product_{code}"))
    
    return keyboard

def get_confirm_keyboard():
    """Tasdiqlash tugmalari"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_yes"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data="confirm_no")
    )
    return keyboard

def get_report_period_keyboard():
    """Hisobot davri tugmalari"""
    keyboard = InlineKeyboardMarkup(row_width=3)
    
    periods = [
        ("Kunlik", "daily"),
        ("Haftalik", "weekly"),
        ("Oylik", "monthly"),
        ("Choraklik", "quarterly"),
        ("Yillik", "yearly")
    ]
    
    for name, code in periods:
        keyboard.insert(InlineKeyboardButton(name, callback_data=f"report_{code}"))
    
    keyboard.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_main"))
    
    return keyboard