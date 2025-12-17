"""
Inline klaviaturalar
Construction Factory Bot uchun
"""

from typing import List, Dict, Optional, Tuple, Any
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


class InlineKeyboards:
    """Inline klaviaturalar sinfi"""
    
    @staticmethod
    def create_sales_menu_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
        """
        Sotuvlar menyusi klaviaturasi
        
        Args:
            is_admin: Admin ekanligi
            
        Returns:
            InlineKeyboardMarkup: Klaviatura
        """
        builder = InlineKeyboardBuilder()
        
        # Asosiy tugmalar
        builder.row(
            InlineKeyboardButton(
                text="🛒 Yangi sotuv",
                callback_data="new_sale"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="📊 Sotuvlar tarixi",
                callback_data="sales_history"
            ),
            InlineKeyboardButton(
                text="📈 Statistika",
                callback_data="sales_statistics"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="📄 Hisobot olish",
                callback_data="sales_report"
            ),
            InlineKeyboardButton(
                text="🔄 Qaytarish",
                callback_data="sales_return"
            )
        )
        
        if is_admin:
            builder.row(
                InlineKeyboardButton(
                    text="⚙️ Sotuv sozlamalari",
                    callback_data="sales_settings"
                )
            )
        
        builder.row(
            InlineKeyboardButton(
                text="🔙 Asosiy menyu",
                callback_data="back_to_main"
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def create_product_selection_keyboard(products: List[Dict], 
                                         category: str,
                                         page: int = 0,
                                         items_per_page: int = 8) -> InlineKeyboardMarkup:
        """
        Mahsulot tanlash klaviaturasi
        
        Args:
            products: Mahsulotlar ro'yxati
            category: Kategoriya nomi
            page: Sahifa raqami
            items_per_page: Sahifadagi elementlar soni
            
        Returns:
            InlineKeyboardMarkup: Klaviatura
        """
        builder = InlineKeyboardBuilder()
        
        # Sahifalash
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        page_products = products[start_idx:end_idx]
        
        # Mahsulot tugmalari
        for product in page_products:
            product_id = product.get('id', 0)
            product_name = product.get('name', 'Noma\'lum')
            quantity = product.get('quantity_available', 0)
            unit = product.get('unit', 'dona')
            
            button_text = f"{product_name} ({quantity} {unit})"
            if quantity <= 0:
                button_text = f"❌ {product_name}"
            
            builder.row(
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"select_product_{product_id}"
                )
            )
        
        # Navigatsiya tugmalari (agar kerak bo'lsa)
        total_pages = (len(products) + items_per_page - 1) // items_per_page
        
        nav_buttons = []
        
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="◀️ Oldingi",
                    callback_data=f"product_page_{category}_{page-1}"
                )
            )
        
        nav_buttons.append(
            InlineKeyboardButton(
                text=f"{page+1}/{total_pages}",
                callback_data="noop"
            )
        )
        
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="▶️ Keyingi",
                    callback_data=f"product_page_{category}_{page+1}"
                )
            )
        
        if nav_buttons:
            builder.row(*nav_buttons)
        
        # Kategoriya navigatsiyasi
        builder.row(
            InlineKeyboardButton(
                text="📦 Boshqa kategoriya",
                callback_data="change_category"
            )
        )
        
        # Sotuvni yakunlash
        builder.row(
            InlineKeyboardButton(
                text="✅ Sotuvni yakunlash",
                callback_data="finish_sale"
            )
        )
        
        # Orqaga
        builder.row(
            InlineKeyboardButton(
                text="🔙 Orqaga",
                callback_data="back_to_sales_menu"
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def create_pagination_keyboard(current_page: int,
                                  total_pages: int,
                                  callback_prefix: str,
                                  extra_buttons: List[Dict] = None) -> InlineKeyboardMarkup:
        """
        Sahifalash klaviaturasi
        
        Args:
            current_page: Joriy sahifa
            total_pages: Jami sahifalar
            callback_prefix: Callback data prefiksi
            extra_buttons: Qo'shimcha tugmalar
            
        Returns:
            InlineKeyboardMarkup: Klaviatura
        """
        builder = InlineKeyboardBuilder()
        
        # Sahifa navigatsiyasi
        nav_buttons = []
        
        if current_page > 0:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="◀️",
                    callback_data=f"{callback_prefix}_page_{current_page-1}"
                )
            )
        
        nav_buttons.append(
            InlineKeyboardButton(
                text=f"{current_page+1}/{total_pages}",
                callback_data="noop"
            )
        )
        
        if current_page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="▶️",
                    callback_data=f"{callback_prefix}_page_{current_page+1}"
                )
            )
        
        if nav_buttons:
            builder.row(*nav_buttons)
        
        # Qo'shimcha tugmalar
        if extra_buttons:
            for button in extra_buttons:
                builder.row(
                    InlineKeyboardButton(
                        text=button.get('text', ''),
                        callback_data=button.get('callback_data', 'noop')
                    )
                )
        
        return builder.as_markup()
    
    @staticmethod
    def create_confirmation_keyboard(confirm_callback: str,
                                    cancel_callback: str,
                                    confirm_text: str = "✅ Tasdiqlash",
                                    cancel_text: str = "❌ Bekor qilish") -> InlineKeyboardMarkup:
        """
        Tasdiqlash klaviaturasi
        
        Args:
            confirm_callback: Tasdiqlash callback
            cancel_callback: Bekor qilish callback
            confirm_text: Tasdiqlash tugmasi matni
            cancel_text: Bekor qilish tugmasi matni
            
        Returns:
            InlineKeyboardMarkup: Klaviatura
        """
        builder = InlineKeyboardBuilder()
        
        builder.row(
            InlineKeyboardButton(
                text=confirm_text,
                callback_data=confirm_callback
            ),
            InlineKeyboardButton(
                text=cancel_text,
                callback_data=cancel_callback
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def create_payment_method_keyboard() -> InlineKeyboardMarkup:
        """
        To'lov usullari klaviaturasi
        
        Returns:
            InlineKeyboardMarkup: Klaviatura
        """
        builder = InlineKeyboardBuilder()
        
        builder.row(
            InlineKeyboardButton(
                text="💵 Naqd",
                callback_data="payment_cash"
            ),
            InlineKeyboardButton(
                text="💳 Karta",
                callback_data="payment_card"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="🏦 Bank o'tkazmasi",
                callback_data="payment_transfer"
            ),
            InlineKeyboardButton(
                text="📅 Nasiya",
                callback_data="payment_credit"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="🔙 Orqaga",
                callback_data="back_to_customer_info"
            ),
            InlineKeyboardButton(
                text="❌ Bekor qilish",
                callback_data="cancel_sale"
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def create_sales_history_keyboard() -> InlineKeyboardMarkup:
        """
        Sotuvlar tarixi klaviaturasi
        
        Returns:
            InlineKeyboardMarkup: Klaviatura
        """
        builder = InlineKeyboardBuilder()
        
        builder.row(
            InlineKeyboardButton(
                text="📅 Bugungi sotuvlar",
                callback_data="today_sales"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="📊 Oxirgi 7 kun",
                callback_data="last_7_days"
            ),
            InlineKeyboardButton(
                text="📈 Oxirgi 30 kun",
                callback_data="last_30_days"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="🗓️ Tanlangan sana",
                callback_data="select_date"
            ),
            InlineKeyboardButton(
                text="📋 Barcha sotuvlar",
                callback_data="all_sales"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="🔙 Orqaga",
                callback_data="back_to_sales_menu"
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def create_report_period_keyboard() -> InlineKeyboardMarkup:
        """
        Hisobot davri klaviaturasi
        
        Returns:
            InlineKeyboardMarkup: Klaviatura
        """
        builder = InlineKeyboardBuilder()
        
        builder.row(
            InlineKeyboardButton(
                text="📅 Bugungi hisobot",
                callback_data="report_today"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="🗓️ Oxirgi 7 kun",
                callback_data="report_week"
            ),
            InlineKeyboardButton(
                text="📆 Oxirgi 30 kun",
                callback_data="report_month"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="📋 To'liq hisobot",
                callback_data="report_full"
            ),
            InlineKeyboardButton(
                text="📊 Maxsus davr",
                callback_data="report_custom"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="🔙 Orqaga",
                callback_data="back_to_sales_menu"
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def create_category_selection_keyboard(categories: List[str],
                                          callback_prefix: str = "category") -> InlineKeyboardMarkup:
        """
        Kategoriya tanlash klaviaturasi
        
        Args:
            categories: Kategoriyalar ro'yxati
            callback_prefix: Callback data prefiksi
            
        Returns:
            InlineKeyboardMarkup: Klaviatura
        """
        builder = InlineKeyboardBuilder()
        
        # Kategoriyalar tugmalari
        for category in categories:
            builder.row(
                InlineKeyboardButton(
                    text=f"📦 {category}",
                    callback_data=f"{callback_prefix}_{category}"
                )
            )
        
        # Orqaga
        builder.row(
            InlineKeyboardButton(
                text="🔙 Orqaga",
                callback_data="back_to_product_selection"
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def create_admin_sales_menu_keyboard() -> InlineKeyboardMarkup:
        """
        Admin sotuvlar menyusi klaviaturasi
        
        Returns:
            InlineKeyboardMarkup: Klaviatura
        """
        builder = InlineKeyboardBuilder()
        
        builder.row(
            InlineKeyboardButton(
                text="📊 Barcha sotuvlar",
                callback_data="admin_all_sales"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="💰 Kunlik daromad",
                callback_data="admin_daily_income"
            ),
            InlineKeyboardButton(
                text="📈 Oylik statistika",
                callback_data="admin_monthly_stats"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="👥 Mijozlar bazasi",
                callback_data="admin_customers"
            ),
            InlineKeyboardButton(
                text="🏆 Top mahsulotlar",
                callback_data="admin_top_products"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="⚙️ Narx sozlamalari",
                callback_data="admin_price_settings"
            ),
            InlineKeyboardButton(
                text="📊 Tahlillar",
                callback_data="admin_analytics"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="🔙 Asosiy admin menyu",
                callback_data="back_to_admin_main"
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def create_yes_no_keyboard(yes_callback: str,
                              no_callback: str,
                              yes_text: str = "Ha",
                              no_text: str = "Yo'q") -> InlineKeyboardMarkup:
        """
        Ha/Yo'q klaviaturasi
        
        Args:
            yes_callback: Ha tugmasi callback
            no_callback: Yo'q tugmasi callback
            yes_text: Ha tugmasi matni
            no_text: Yo'q tugmasi matni
            
        Returns:
            InlineKeyboardMarkup: Klaviatura
        """
        builder = InlineKeyboardBuilder()
        
        builder.row(
            InlineKeyboardButton(
                text=yes_text,
                callback_data=yes_callback
            ),
            InlineKeyboardButton(
                text=no_text,
                callback_data=no_callback
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def create_cancel_keyboard(cancel_callback: str = "cancel",
                              cancel_text: str = "❌ Bekor qilish") -> InlineKeyboardMarkup:
        """
        Bekor qilish klaviaturasi
        
        Args:
            cancel_callback: Bekor qilish callback
            cancel_text: Bekor qilish tugmasi matni
            
        Returns:
            InlineKeyboardMarkup: Klaviatura
        """
        builder = InlineKeyboardBuilder()
        
        builder.row(
            InlineKeyboardButton(
                text=cancel_text,
                callback_data=cancel_callback
            )
        )
        
        return builder.as_markup()


class AdminKeyboards:
    """Admin klaviaturalari"""
    
    @staticmethod
    def create_admin_main_menu() -> InlineKeyboardMarkup:
        """
        Admin asosiy menyusi
        
        Returns:
            InlineKeyboardMarkup: Klaviatura
        """
        builder = InlineKeyboardBuilder()
        
        # Asosiy bo'limlar
        builder.row(
            InlineKeyboardButton(
                text="👥 Xodimlar",
                callback_data="admin_employees"
            ),
            InlineKeyboardButton(
                text="📊 Statistika",
                callback_data="admin_statistics"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="💰 Sotuvlar",
                callback_data="admin_sales"
            ),
            InlineKeyboardButton(
                text="🏭 Ishlab chiqarish",
                callback_data="admin_production"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="📦 Ombor",
                callback_data="admin_warehouse"
            ),
            InlineKeyboardButton(
                text="🔔 Bildirishnomalar",
                callback_data="admin_notifications"
            )
        )
        
        # Sozlamalar
        builder.row(
            InlineKeyboardButton(
                text="⚙️ Sozlamalar",
                callback_data="admin_settings"
            )
        )
        
        # Asosiy menyuga qaytish
        builder.row(
            InlineKeyboardButton(
                text="🔙 Asosiy menyu",
                callback_data="back_to_main"
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def create_employee_management_keyboard() -> InlineKeyboardMarkup:
        """
        Xodimlarni boshqarish klaviaturasi
        
        Returns:
            InlineKeyboardMarkup: Klaviatura
        """
        builder = InlineKeyboardBuilder()
        
        builder.row(
            InlineKeyboardButton(
                text="➕ Yangi xodim",
                callback_data="admin_add_employee"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="📋 Xodimlar ro'yxati",
                callback_data="admin_list_employees"
            ),
            InlineKeyboardButton(
                text="💰 Ish haqi",
                callback_data="admin_salaries"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="📊 Ish vaqtlari",
                callback_data="admin_work_hours"
            ),
            InlineKeyboardButton(
                text="📈 Samandarolik",
                callback_data="admin_productivity"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="🔙 Admin menyu",
                callback_data="back_to_admin_main"
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def create_warehouse_management_keyboard() -> InlineKeyboardMarkup:
        """
        Ombor boshqaruvi klaviaturasi
        
        Returns:
            InlineKeyboardMarkup: Klaviatura
        """
        builder = InlineKeyboardBuilder()
        
        builder.row(
            InlineKeyboardButton(
                text="📥 Kirim",
                callback_data="admin_warehouse_in"
            ),
            InlineKeyboardButton(
                text="📤 Chiqim",
                callback_data="admin_warehouse_out"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="📊 Qoldiqlar",
                callback_data="admin_inventory"
            ),
            InlineKeyboardButton(
                text="⚠️ Kam qolganlar",
                callback_data="admin_low_stock"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="🔄 Transfer",
                callback_data="admin_transfer"
            ),
            InlineKeyboardButton(
                text="📈 Statistika",
                callback_data="admin_warehouse_stats"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="🔙 Admin menyu",
                callback_data="back_to_admin_main"
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def create_production_management_keyboard() -> InlineKeyboardMarkup:
        """
        Ishlab chiqarish boshqaruvi klaviaturasi
        
        Returns:
            InlineKeyboardMarkup: Klaviatura
        """
        builder = InlineKeyboardBuilder()
        
        builder.row(
            InlineKeyboardButton(
                text="🏭 Yangi buyurtma",
                callback_data="admin_new_production"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="📋 Faol buyurtmalar",
                callback_data="admin_active_orders"
            ),
            InlineKeyboardButton(
                text="✅ Tugallanganlar",
                callback_data="admin_completed_orders"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="📊 Samaradorlik",
                callback_data="admin_production_stats"
            ),
            InlineKeyboardButton(
                text="⚙️ Texnik ko'rsatkichlar",
                callback_data="admin_tech_specs"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="🔙 Admin menyu",
                callback_data="back_to_admin_main"
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def create_settings_keyboard() -> InlineKeyboardMarkup:
        """
        Sozlamalar klaviaturasi
        
        Returns:
            InlineKeyboardMarkup: Klaviatura
        """
        builder = InlineKeyboardBuilder()
        
        builder.row(
            InlineKeyboardButton(
                text="🏢 Korxona ma'lumotlari",
                callback_data="admin_company_info"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="💰 Narxlar va stavkalar",
                callback_data="admin_pricing"
            ),
            InlineKeyboardButton(
                text="⚙️ Texnik sozlamalar",
                callback_data="admin_tech_settings"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="👥 Ruxsatlar",
                callback_data="admin_permissions"
            ),
            InlineKeyboardButton(
                text="📊 KPI sozlamalari",
                callback_data="admin_kpi_settings"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="🔔 Bildirishnoma sozlamalari",
                callback_data="admin_notification_settings"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="🔙 Admin menyu",
                callback_data="back_to_admin_main"
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def create_statistics_keyboard() -> InlineKeyboardMarkup:
        """
        Statistika klaviaturasi
        
        Returns:
            InlineKeyboardMarkup: Klaviatura
        """
        builder = InlineKeyboardBuilder()
        
        builder.row(
            InlineKeyboardButton(
                text="📈 Moliyaviy statistika",
                callback_data="admin_financial_stats"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="🏭 Ishlab chiqarish",
                callback_data="admin_production_stats_main"
            ),
            InlineKeyboardButton(
                text="💰 Sotuvlar",
                callback_data="admin_sales_stats"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="👥 Xodimlar",
                callback_data="admin_employee_stats"
            ),
            InlineKeyboardButton(
                text="📦 Ombor",
                callback_data="admin_warehouse_stats_main"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="📊 KPI ko'rsatkichlari",
                callback_data="admin_kpi_stats"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="🔙 Admin menyu",
                callback_data="back_to_admin_main"
            )
        )
        
        return builder.as_markup()


# Qisqa nomlar va funksiyalar
create_sales_menu = InlineKeyboards.create_sales_menu_keyboard
create_product_selection = InlineKeyboards.create_product_selection_keyboard
create_pagination = InlineKeyboards.create_pagination_keyboard
create_confirmation = InlineKeyboards.create_confirmation_keyboard
create_payment_method = InlineKeyboards.create_payment_method_keyboard
create_sales_history = InlineKeyboards.create_sales_history_keyboard
create_report_period = InlineKeyboards.create_report_period_keyboard
create_category_selection = InlineKeyboards.create_category_selection_keyboard
create_yes_no = InlineKeyboards.create_yes_no_keyboard
create_cancel = InlineKeyboards.create_cancel_keyboard

# Admin klaviaturalari
admin_main_menu = AdminKeyboards.create_admin_main_menu
admin_employee_management = AdminKeyboards.create_employee_management_keyboard
admin_warehouse_management = AdminKeyboards.create_warehouse_management_keyboard
admin_production_management = AdminKeyboards.create_production_management_keyboard
admin_settings = AdminKeyboards.create_settings_keyboard
admin_statistics = AdminKeyboards.create_statistics_keyboard

# Export qilinadigan funksiyalar
__all__ = [
    # Asosiy klaviaturalar
    'InlineKeyboards',
    'create_sales_menu',
    'create_product_selection',
    'create_pagination',
    'create_confirmation',
    'create_payment_method',
    'create_sales_history',
    'create_report_period',
    'create_category_selection',
    'create_yes_no',
    'create_cancel',
    
    # Admin klaviaturalari
    'AdminKeyboards',
    'admin_main_menu',
    'admin_employee_management',
    'admin_warehouse_management',
    'admin_production_management',
    'admin_settings',
    'admin_statistics',
]