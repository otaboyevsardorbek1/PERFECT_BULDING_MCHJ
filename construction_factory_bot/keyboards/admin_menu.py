"""
Admin menyu klaviaturalari
Construction Factory Bot uchun
"""

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)


def get_admin_menu():
    """Admin paneli menyusi (reply keyboard)"""
    buttons = [
        [KeyboardButton(text="👥 Xodimlar boshqaruvi"), KeyboardButton(text="⚙️ Tizim sozlamalari")],
        [KeyboardButton(text="📊 Tizim statistika"), KeyboardButton(text="📝 Audit loglari")],
        [KeyboardButton(text="💾 Backup olish"), KeyboardButton(text="⬅️ Orqaga")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_admin_dashboard_keyboard():
    """Admin dashboard klaviaturasi"""
    buttons = [
        [KeyboardButton(text="👥 Xodimlar"), KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="💰 Sotuvlar"), KeyboardButton(text="🏭 Ishlab chiqarish")],
        [KeyboardButton(text="📦 Ombor"), KeyboardButton(text="🔔 Bildirishnomalar")],
        [KeyboardButton(text="🔙 Asosiy menyu")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_employee_management_menu():
    """Xodimlar boshqaruvi menyusi"""
    buttons = [
        [KeyboardButton(text="➕ Yangi xodim"), KeyboardButton(text="📋 Xodimlar ro'yxati")],
        [KeyboardButton(text="👤 Mening profilim"), KeyboardButton(text="⏱️ Ish vaqti kiritish")],
        [KeyboardButton(text="💰 Maosh to'lash"), KeyboardButton(text="📊 Xodimlar statistika")],
        [KeyboardButton(text="⬅️ Orqaga")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_employee_actions_keyboard(employee_id: int):
    """Xodim amallari klaviaturasi"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"emp_edit_{employee_id}"),
            InlineKeyboardButton(text="❌ O'chirish", callback_data=f"emp_delete_{employee_id}"),
        ],
        [
            InlineKeyboardButton(text="📊 Statistika", callback_data=f"emp_stats_{employee_id}"),
            InlineKeyboardButton(text="⬅️ Orqaga", callback_data="emp_back"),
        ],
    ])


def get_notifications_menu():
    """Bildirishnomalar menyusi"""
    buttons = [
        [KeyboardButton(text="📝 Yangi bildirishnoma"), KeyboardButton(text="📋 Barcha bildirishnomalar")],
        [KeyboardButton(text="⚙️ Avtomatik bildirishnomalar"), KeyboardButton(text="📊 Bildirishnomalar statistika")],
        [KeyboardButton(text="📨 Mening bildirishnomalarim"), KeyboardButton(text="🔄 Darhol tekshirish")],
        [KeyboardButton(text="⬅️ Orqaga")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


# Export qilinadigan funksiyalar
__all__ = [
    'get_admin_menu',
    'get_admin_dashboard_keyboard',
    'get_employee_management_menu',
    'get_employee_actions_keyboard',
    'get_notifications_menu',
]
