"""
Admin menyu klaviaturalari
Construction Factory Bot uchun
"""

from typing import List, Dict, Optional
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


class AdminMenu:
    """Admin menyu klaviaturalari sinfi"""
    
    @staticmethod
    def create_admin_main_keyboard(is_super_admin: bool = False) -> ReplyKeyboardMarkup:
        """
        Admin asosiy menyusi (reply keyboard)
        
        Args:
            is_super_admin: Super admin ekanligi
            
        Returns:
            ReplyKeyboardMarkup: Klaviatura
        """
        builder = ReplyKeyboardBuilder()
        
        # Birinchi qator
        builder.add(
            KeyboardButton(text="👥 Xodimlar"),
            KeyboardButton(text="📊 Statistika")
        )
        
        # Ikkinchi qator
        builder.add(
            KeyboardButton(text="💰 Sotuvlar"),
            KeyboardButton(text="🏭 Ishlab chiqarish")
        )
        
        # Uchinchi qator
        builder.add(
            KeyboardButton(text="📦 Ombor"),
            KeyboardButton(text="🔔 Bildirishnomalar")
        )
        
        # Super admin uchun qo'shimcha tugmalar
        if is_super_admin:
            builder.add(KeyboardButton(text="⚙️ Sozlamalar"))
            builder.add(KeyboardButton(text="🔐 Ruxsatlar"))
        
        # Asosiy menyuga qaytish
        builder.add(KeyboardButton(text="🔙 Asosiy menyu"))
        
        # Matritsa shaklini sozlash
        builder.adjust(2, 2, 2, 1 if is_super_admin else 0, 1, 1)
        
        return builder.as_markup(resize_keyboard=True)
    
    @staticmethod
    def create_employees_admin_keyboard() -> ReplyKeyboardMarkup:
        """
        Xodimlar admin menyusi
        
        Returns:
            ReplyKeyboardMarkup: Klaviatura
        """
        builder = ReplyKeyboardBuilder()
        
        builder.add(
            KeyboardButton(text="➕ Yangi xodim"),
            KeyboardButton(text="📋 Xodimlar ro'yxati")
        )
        
        builder.add(
            KeyboardButton(text="💰 Ish haqlari"),
            KeyboardButton(text="⏱️ Ish vaqtlari")
        )
        
        builder.add(
            KeyboardButton(text="📊 Samandarolik"),
            KeyboardButton(text="📈 KPI")
        )
        
        builder.add(
            KeyboardButton(text="🔙 Admin menyu"),
            KeyboardButton(text="🔙 Asosiy menyu")
        )
        
        builder.adjust(2, 2, 2, 2)
        
        return builder.as_markup(resize_keyboard=True)
    
    @staticmethod
    def create_warehouse_admin_keyboard() -> ReplyKeyboardMarkup:
        """
        Ombor admin menyusi
        
        Returns:
            ReplyKeyboardMarkup: Klaviatura
        """
        builder = ReplyKeyboardBuilder()
        
        builder.add(
            KeyboardButton(text="📥 Kirim"),
            KeyboardButton(text="📤 Chiqim")
        )
        
        builder.add(
            KeyboardButton(text="📊 Qoldiqlar"),
            KeyboardButton(text="⚠️ Kam qolganlar")
        )
        
        builder.add(
            KeyboardButton(text="🔄 Transfer"),
            KeyboardButton(text="📦 Inventarizatsiya")
        )
        
        builder.add(
            KeyboardButton(text="📈 Statistika"),
            KeyboardButton(text="📄 Hisobotlar")
        )
        
        builder.add(
            KeyboardButton(text="🔙 Admin menyu")
        )
        
        builder.adjust(2, 2, 2, 2, 1)
        
        return builder.as_markup(resize_keyboard=True)
    
    @staticmethod
    def create_production_admin_keyboard() -> ReplyKeyboardMarkup:
        """
        Ishlab chiqarish admin menyusi
        
        Returns:
            ReplyKeyboardMarkup: Klaviatura
        """
        builder = ReplyKeyboardBuilder()
        
        builder.add(
            KeyboardButton(text="🏭 Yangi buyurtma"),
            KeyboardButton(text="📋 Faol buyurtmalar")
        )
        
        builder.add(
            KeyboardButton(text="✅ Tugallanganlar"),
            KeyboardButton(text="⏸️ To'xtatilganlar")
        )
        
        builder.add(
            KeyboardButton(text="⚙️ Jihozlar"),
            KeyboardButton(text="👷‍♂️ Brigadalar")
        )
        
        builder.add(
            KeyboardButton(text="📊 Samaradorlik"),
            KeyboardButton(text="📈 Statistika")
        )
        
        builder.add(
            KeyboardButton(text="🔙 Admin menyu")
        )
        
        builder.adjust(2, 2, 2, 2, 1)
        
        return builder.as_markup(resize_keyboard=True)
    
    @staticmethod
    def create_sales_admin_keyboard() -> ReplyKeyboardMarkup:
        """
        Sotuvlar admin menyusi
        
        Returns:
            ReplyKeyboardMarkup: Klaviatura
        """
        builder = ReplyKeyboardBuilder()
        
        builder.add(
            KeyboardButton(text="💰 Barcha sotuvlar"),
            KeyboardButton(text="📊 Kunlik daromad")
        )
        
        builder.add(
            KeyboardButton(text="📈 Oylik statistika"),
            KeyboardButton(text="👥 Mijozlar bazasi")
        )
        
        builder.add(
            KeyboardButton(text="🏆 Top mahsulotlar"),
            KeyboardButton(text="📉 Kam sotilganlar")
        )
        
        builder.add(
            KeyboardButton(text="⚙️ Narx sozlamalari"),
            KeyboardButton(text="📊 Tahlillar")
        )
        
        builder.add(
            KeyboardButton(text="🔙 Admin menyu")
        )
        
        builder.adjust(2, 2, 2, 2, 1)
        
        return builder.as_markup(resize_keyboard=True)
    
    @staticmethod
    def create_statistics_admin_keyboard() -> ReplyKeyboardMarkup:
        """
        Statistika admin menyusi
        
        Returns:
            ReplyKeyboardMarkup: Klaviatura
        """
        builder = ReplyKeyboardBuilder()
        
        builder.add(
            KeyboardButton(text="📈 Moliyaviy"),
            KeyboardButton(text="🏭 Ishlab chiqarish")
        )
        
        builder.add(
            KeyboardButton(text="💰 Sotuvlar"),
            KeyboardButton(text="👥 Xodimlar")
        )
        
        builder.add(
            KeyboardButton(text="📦 Ombor"),
            KeyboardButton(text="📊 KPI")
        )
        
        builder.add(
            KeyboardButton(text="📅 Kunlik"),
            KeyboardButton(text="📆 Haftalik")
        )
        
        builder.add(
            KeyboardButton(text="📊 Oylik"),
            KeyboardButton(text="📈 Yillik")
        )
        
        builder.add(
            KeyboardButton(text="🔙 Admin menyu")
        )
        
        builder.adjust(2, 2, 2, 2, 2, 1)
        
        return builder.as_markup(resize_keyboard=True)
    
    @staticmethod
    def create_settings_admin_keyboard() -> ReplyKeyboardMarkup:
        """
        Sozlamalar admin menyusi
        
        Returns:
            ReplyKeyboardMarkup: Klaviatura
        """
        builder = ReplyKeyboardBuilder()
        
        builder.add(
            KeyboardButton(text="🏢 Korxona ma'lumotlari"),
            KeyboardButton(text="💰 Narxlar va stavkalar")
        )
        
        builder.add(
            KeyboardButton(text="⚙️ Texnik sozlamalar"),
            KeyboardButton(text="👥 Ruxsatlar")
        )
        
        builder.add(
            KeyboardButton(text="📊 KPI sozlamalari"),
            KeyboardButton(text="🔔 Bildirishnomalar")
        )
        
        builder.add(
            KeyboardButton(text="📧 Email sozlamalari"),
            KeyboardButton(text="📱 SMS sozlamalari")
        )
        
        builder.add(
            KeyboardButton(text="💾 Backup"),
            KeyboardButton(text="🔄 Yangilash")
        )
        
        builder.add(
            KeyboardButton(text="🔙 Admin menyu")
        )
        
        builder.adjust(2, 2, 2, 2, 2, 1)
        
        return builder.as_markup(resize_keyboard=True)
    
    @staticmethod
    def create_notifications_admin_keyboard() -> ReplyKeyboardMarkup:
        """
        Bildirishnomalar admin menyusi
        
        Returns:
            ReplyKeyboardMarkup: Klaviatura
        """
        builder = ReplyKeyboardBuilder()
        
        builder.add(
            KeyboardButton(text="📢 Yangi xabar"),
            KeyboardButton(text="📋 Xabarlar tarixi")
        )
        
        builder.add(
            KeyboardButton(text="👥 Guruhlarga"),
            KeyboardButton(text="📊 Statistika")
        )
        
        builder.add(
            KeyboardButton(text="⚙️ Sozlamalar"),
            KeyboardButton(text="📈 Faollik")
        )
        
        builder.add(
            KeyboardButton(text="🔙 Admin menyu")
        )
        
        builder.adjust(2, 2, 2, 1)
        
        return builder.as_markup(resize_keyboard=True)
    
    @staticmethod
    def create_quick_actions_keyboard() -> InlineKeyboardMarkup:
        """
        Tezkor amallar inline klaviaturasi
        
        Returns:
            InlineKeyboardMarkup: Klaviatura
        """
        builder = InlineKeyboardBuilder()
        
        builder.row(
            InlineKeyboardButton(
                text="➕ Yangi xodim",
                callback_data="quick_add_employee"
            ),
            InlineKeyboardButton(
                text="💰 Yangi sotuv",
                callback_data="quick_new_sale"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="📥 Ombor kirimi",
                callback_data="quick_warehouse_in"
            ),
            InlineKeyboardButton(
                text="🏭 Yangi buyurtma",
                callback_data="quick_new_order"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="📊 Bugun statistikasi",
                callback_data="quick_today_stats"
            ),
            InlineKeyboardButton(
                text="⚠️ Ogohlantirishlar",
                callback_data="quick_alerts"
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def create_back_keyboard(back_to: str = "admin_main") -> ReplyKeyboardMarkup:
        """
        Orqaga qaytish klaviaturasi
        
        Args:
            back_to: Qayerga qaytish
            
        Returns:
            ReplyKeyboardMarkup: Klaviatura
        """
        builder = ReplyKeyboardBuilder()
        
        if back_to == "admin_main":
            builder.add(KeyboardButton(text="🔙 Admin menyu"))
        elif back_to == "main":
            builder.add(KeyboardButton(text="🔙 Asosiy menyu"))
        else:
            builder.add(KeyboardButton(text="🔙 Orqaga"))
        
        return builder.as_markup(resize_keyboard=True)


# Qisqa nomlar
admin_main = AdminMenu.create_admin_main_keyboard
admin_employees = AdminMenu.create_employees_admin_keyboard
admin_warehouse = AdminMenu.create_warehouse_admin_keyboard
admin_production = AdminMenu.create_production_admin_keyboard
admin_sales = AdminMenu.create_sales_admin_keyboard
admin_statistics = AdminMenu.create_statistics_admin_keyboard
admin_settings = AdminMenu.create_settings_admin_keyboard
admin_notifications = AdminMenu.create_notifications_admin_keyboard
admin_quick_actions = AdminMenu.create_quick_actions_keyboard
admin_back = AdminMenu.create_back_keyboard

# =============== QO'SHIMCHA FUNKSIYALAR (handlerlar uchun) ===============

def get_admin_menu():
    """Admin paneli menyusi (reply keyboard)"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        KeyboardButton("👥 Xodimlar boshqaruvi"),
        KeyboardButton("⚙️ Tizim sozlamalari"),
        KeyboardButton("📊 Tizim statistika"),
        KeyboardButton("📝 Audit loglari"),
        KeyboardButton("💾 Backup olish"),
        KeyboardButton("⬅️ Orqaga")
    ]
    keyboard.add(*buttons)
    return keyboard

def get_admin_dashboard_keyboard():
    """Admin dashboard klaviaturasi"""
    return AdminMenu.create_admin_main_keyboard()

def get_employee_management_menu():
    """Xodimlar boshqaruvi menyusi"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        KeyboardButton("➕ Yangi xodim"),
        KeyboardButton("📋 Xodimlar ro'yxati"),
        KeyboardButton("👤 Mening profilim"),
        KeyboardButton("⏱️ Ish vaqti kiritish"),
        KeyboardButton("💰 Maosh to'lash"),
        KeyboardButton("📊 Xodimlar statistika"),
        KeyboardButton("⬅️ Orqaga")
    ]
    keyboard.add(*buttons)
    return keyboard

def get_employee_actions_keyboard(employee_id: int):
    """Xodim amallari klaviaturasi"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✏️ Tahrirlash", callback_data=f"emp_edit_{employee_id}"),
        InlineKeyboardButton("❌ O'chirish", callback_data=f"emp_delete_{employee_id}"),
        InlineKeyboardButton("📊 Statistika", callback_data=f"emp_stats_{employee_id}"),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="emp_back")
    )
    return keyboard

def get_notifications_menu():
    """Bildirishnomalar menyusi"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        KeyboardButton("📝 Yangi bildirishnoma"),
        KeyboardButton("📋 Barcha bildirishnomalar"),
        KeyboardButton("⚙️ Avtomatik bildirishnomalar"),
        KeyboardButton("📊 Bildirishnomalar statistika"),
        KeyboardButton("📨 Mening bildirishnomalarim"),
        KeyboardButton("🔄 Darhol tekshirish"),
        KeyboardButton("⬅️ Orqaga")
    ]
    keyboard.add(*buttons)
    return keyboard

# Export qilinadigan funksiyalar
__all__ = [
    'AdminMenu',
    'admin_main',
    'admin_employees',
    'admin_warehouse',
    'admin_production',
    'admin_sales',
    'admin_statistics',
    'admin_settings',
    'admin_notifications',
    'admin_quick_actions',
    'admin_back',
    'get_admin_menu',
    'get_admin_dashboard_keyboard',
    'get_employee_management_menu',
    'get_employee_actions_keyboard',
    'get_notifications_menu',
]