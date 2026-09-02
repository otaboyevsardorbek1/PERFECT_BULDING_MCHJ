"""
Admin Panel - Qurilish Korxonasi Admin Boshqaruvi
"""
from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from datetime import datetime, timedelta
import logging

from database.session import get_db_session
from database import crud, models
from keyboards.admin_menu import get_admin_menu, get_admin_dashboard_keyboard
from keyboards.main_menu import get_main_menu
from config import ADMIN_IDS, MAIN_ADMIN_ID

logger = logging.getLogger(__name__)

# =============== ADMIN STATES ===============
class AdminStates(StatesGroup):
    # User Management
    waiting_new_admin_id = State()
    waiting_admin_name = State()
    waiting_remove_admin = State()
    
    # System Settings
    waiting_system_setting = State()
    waiting_setting_value = State()
    
    # Backup and Restore
    waiting_backup_confirm = State()
    waiting_restore_file = State()
    
    # Audit Logs
    viewing_logs = State()
    
    # Database Management
    waiting_db_action = State()
    waiting_db_confirm = State()

# =============== ADMIN COMMANDS ===============
async def admin_panel(message: types.Message):
    """Admin panelini ochish"""
    
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Sizda admin huquqlari mavjud emas!")
        return
    
    with get_db_session() as db:
        # Admin statistikasini olish
        total_users = db.query(models.Employee).count()
        total_products = db.query(models.Product).filter(models.Product.is_active == True).count()
        total_raw_materials = db.query(models.RawMaterial).count()
        
        # Tizim statistikasi
        system_stats = crud.get_warehouse_statistics(db)
        
        # Oxirgi faollik
        last_log = db.query(models.SystemLog).order_by(models.SystemLog.created_at.desc()).first()
    
    admin_text = f"""
👑 **ADMIN PANELI**

📊 **Tizim Statistikasi:**
├ 👥 Xodimlar: {total_users} ta
├ 🏭 Mahsulotlar: {total_products} ta
├ 📦 Xom ashyolar: {total_raw_materials} ta
├ ⚠️ Yetarli bo'lmaganlar: {system_stats['low_stock_materials_count']} ta
└ 💰 Ombor qiymati: {system_stats['total_raw_materials_value']:,.0f} so'm

🛠 **Oxirgi faollik:**
{'└ ' + last_log.action if last_log else '└ Hech qanday faollik mavjud emas'}

📈 **Admin imkoniyatlari:**
• 👥 Xodimlar boshqaruvi
• ⚙️ Tizim sozlamalari
• 📊 Statistika va hisobotlar
• 🔐 Ruxsatlar boshqaruvi
• 💾 Backup va restore
• 📝 Audit loglari
"""
    
    await message.answer(admin_text, reply_markup=get_admin_menu(), parse_mode="Markdown")

# =============== USER MANAGEMENT ===============
async def admin_user_management(message: types.Message):
    """Xodimlar boshqaruvi"""
    
    if message.from_user.id not in ADMIN_IDS:
        return
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("➕ Yangi admin qo'shish", callback_data="admin_add_admin"),
        InlineKeyboardButton("➖ Adminni olib tashlash", callback_data="admin_remove_admin"),
        InlineKeyboardButton("📋 Adminlar ro'yxati", callback_data="admin_list_admins"),
        InlineKeyboardButton("👥 Barcha xodimlar", callback_data="admin_list_all_users"),
        InlineKeyboardButton("📊 Xodim statistikasi", callback_data="admin_user_stats"),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back")
    )
    
    await message.answer("👥 **Xodimlar Boshqaruvi**\n\nQuyidagi amallardan birini tanlang:", 
                        reply_markup=keyboard, parse_mode="Markdown")

async def add_new_admin(callback_query: types.CallbackQuery, state: FSMContext):
    """Yangi admin qo'shish"""
    
    if callback_query.from_user.id != MAIN_ADMIN_ID:
        await callback_query.answer("❌ Faqat asosiy admin yangi admin qo'shishi mumkin!", show_alert=True)
        return
    
    await callback_query.answer()
    await callback_query.message.answer("Yangi adminning Telegram ID sini kiriting:")
    await AdminStates.waiting_new_admin_id.set()

async def process_new_admin_id(message: types.Message, state: FSMContext):
    """Yangi admin ID sini qabul qilish"""
    
    try:
        admin_id = int(message.text)
        
        # ID ni tekshirish
        if admin_id in ADMIN_IDS:
            await message.answer("❌ Bu foydalanuvchi allaqachon admin!")
            await state.finish()
            return
        
        await state.update_data(admin_id=admin_id)
        await message.answer("Adminning ismini kiriting:")
        await AdminStates.waiting_admin_name.set()
        
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Faqat raqam kiriting:")

async def process_admin_name(message: types.Message, state: FSMContext):
    """Admin ismini qabul qilish"""
    
    admin_name = message.text
    data = await state.get_data()
    admin_id = data['admin_id']
    
    # Ma'lumotlar bazasida xodimni topish
    with get_db_session() as db:
        employee = db.query(models.Employee).filter(
            models.Employee.telegram_id == admin_id
        ).first()
        
        if employee:
            # Xodimni admin qilish
            employee.is_admin = True
            db.commit()
            
            # Tizim logiga yozish
            crud.create_system_log(
                db,
                user_id=message.from_user.id,
                user_name=message.from_user.full_name,
                action=f"Yangi admin qo'shildi: {admin_name} (ID: {admin_id})",
                module="admin"
            )
            
            await message.answer(
                f"✅ **{admin_name}** muvaffaqiyatli admin qilindi!\n\n"
                f"📋 Admin ID: {admin_id}\n"
                f"👤 Admin ismi: {admin_name}",
                parse_mode="Markdown"
            )
        else:
            # Yangi xodim yaratish
            new_employee = crud.create_employee(db, {
                'telegram_id': admin_id,
                'full_name': admin_name,
                'phone_number': 'Noma\'lum',
                'position': 'Administrator',
                'department': 'Administratsiya',
                'hire_date': datetime.utcnow(),
                'salary': 0,
                'is_admin': True
            })
            
            # Tizim logiga yozish
            crud.create_system_log(
                db,
                user_id=message.from_user.id,
                user_name=message.from_user.full_name,
                action=f"Yangi admin xodim yaratildi: {admin_name}",
                module="admin"
            )
            
            await message.answer(
                f"✅ **Yangi admin xodim yaratildi!**\n\n"
                f"📋 ID: {admin_id}\n"
                f"👤 Ism: {admin_name}\n"
                f"📋 Lavozim: Administrator\n"
                f"🏢 Bo'lim: Administratsiya",
                parse_mode="Markdown"
            )
    
    await state.finish()
    await message.answer("Admin paneliga qaytish uchun /admin buyrug'ini bering.")

async def list_admins(callback_query: types.CallbackQuery):
    """Adminlar ro'yxatini ko'rsatish"""
    
    await callback_query.answer()
    
    with get_db_session() as db:
        admins = db.query(models.Employee).filter(
            models.Employee.is_admin == True
        ).all()
    
    if not admins:
        await callback_query.message.answer("❌ Hozircha adminlar mavjud emas.")
        return
    
    admin_list = "👑 **ADMINLAR RO'YXATI**\n\n"
    
    for idx, admin in enumerate(admins, 1):
        status = "✅ Faol" if admin.status == models.EmployeeStatus.ACTIVE else "⏸️ Ta'tilda"
        admin_list += (
            f"{idx}. **{admin.full_name}**\n"
            f"   📱 ID: {admin.telegram_id or 'Noma\'lum'}\n"
            f"   📞 Tel: {admin.phone_number}\n"
            f"   🏢 Lavozim: {admin.position}\n"
            f"   📊 Holat: {status}\n"
            f"   📅 Ishga kirgan: {admin.hire_date.strftime('%Y-%m-%d')}\n\n"
        )
    
    await callback_query.message.answer(admin_list, parse_mode="Markdown")

# =============== SYSTEM SETTINGS ===============
async def system_settings(message: types.Message):
    """Tizim sozlamalari"""
    
    if message.from_user.id not in ADMIN_IDS:
        return
    
    with get_db_session() as db:
        # Joriy sozlamalarni olish
        settings = {
            "Xom ashyo ogohlantirish": "Yoqilgan",
            "Avtomatik backup": "Yoqilgan",
            "Ishlab chiqarish xatoliklari": "Yoqilgan",
            "Maxsulot narxlari avtomatik yangilash": "O'chirilgan",
            "Ish vaqti nazorati": "Yoqilgan"
        }
    
    settings_text = "⚙️ **TIZIM SOZLAMALARI**\n\n"
    
    for key, value in settings.items():
        settings_text += f"• {key}: **{value}**\n"
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔔 Ogohlantirishlar", callback_data="settings_notifications"),
        InlineKeyboardButton("💾 Backup", callback_data="settings_backup"),
        InlineKeyboardButton("📊 Statistika", callback_data="settings_stats"),
        InlineKeyboardButton("🔐 Ruxsatlar", callback_data="settings_permissions"),
        InlineKeyboardButton("🔄 Yangilash tezligi", callback_data="settings_update"),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back")
    )
    
    await message.answer(settings_text + "\nSozlamani tanlang:", 
                        reply_markup=keyboard, parse_mode="Markdown")

async def backup_database(message: types.Message):
    """Database backup olish"""
    
    if message.from_user.id not in ADMIN_IDS:
        return
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("✅ Ha, backup olish", callback_data="backup_confirm"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data="backup_cancel")
    )
    
    await message.answer(
        "⚠️ **DATABASE BACKUP**\n\n"
        "Database backup jarayoni tizim ishlashiga ta'sir ko'rsatishi mumkin.\n"
        "Backup olishni tasdiqlaysizmi?",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

async def perform_backup(callback_query: types.CallbackQuery):
    """Backup ni amalga oshirish"""
    
    await callback_query.answer()
    
    try:
        import shutil
        import os
        from datetime import datetime
        
        # Backup papkasini yaratish
        backup_dir = "backups"
        os.makedirs(backup_dir, exist_ok=True)
        
        # Backup fayl nomi
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{backup_dir}/backup_{timestamp}.db"
        
        # SQLite database ni nusxalash (PostgreSQL uchun alohida)
        if os.path.exists("construction.db"):
            shutil.copy2("construction.db", backup_file)
            backup_size = os.path.getsize(backup_file) / 1024 / 1024  # MB da
            
            await callback_query.message.answer(
                f"✅ **BACKUP MUVAFFAQIYATLI BAJARILDI!**\n\n"
                f"📁 Fayl: `{backup_file}`\n"
                f"📦 Hajmi: {backup_size:.2f} MB\n"
                f"📅 Sana: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"💾 Backup faylini xavfsiz joyda saqlang.",
                parse_mode="Markdown"
            )
            
            # Tizim logiga yozish
            with get_db_session() as db:
                crud.create_system_log(
                    db,
                    user_id=callback_query.from_user.id,
                    user_name=callback_query.from_user.full_name,
                    action=f"Database backup olindi: {backup_file}",
                    module="admin"
                )
        else:
            await callback_query.message.answer("❌ Database fayli topilmadi!")
    
    except Exception as e:
        logger.error(f"Backup error: {e}")
        await callback_query.message.answer(f"❌ Backup jarayonida xatolik: {str(e)}")

# =============== AUDIT LOGS ===============
async def view_audit_logs(message: types.Message):
    """Audit loglarini ko'rish"""
    
    if message.from_user.id not in ADMIN_IDS:
        return
    
    with get_db_session() as db:
        # Oxirgi 20 ta logni olish
        logs = db.query(models.SystemLog).order_by(
            models.SystemLog.created_at.desc()
        ).limit(20).all()
    
    if not logs:
        await message.answer("❌ Hozircha audit loglari mavjud emas.")
        return
    
    logs_text = "📝 **AUDIT LOGLARI** (Oxirgi 20 ta)\n\n"
    
    for log in logs:
        logs_text += (
            f"⏰ **{log.created_at.strftime('%Y-%m-%d %H:%M')}**\n"
            f"👤 Foydalanuvchi: {log.user_name or 'Tizim'}\n"
            f"📋 Amal: {log.action}\n"
            f"📁 Modul: {log.module}\n"
            f"{'📝 Tafsilot: ' + log.details if log.details else ''}\n"
            f"────────────────────\n"
        )
    
    # Loglarni qismlarga bo'lish
    if len(logs_text) > 4000:
        parts = [logs_text[i:i+4000] for i in range(0, len(logs_text), 4000)]
        for part in parts:
            await message.answer(part, parse_mode="Markdown")
    else:
        await message.answer(logs_text, parse_mode="Markdown")
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("📊 To'liq loglar", callback_data="logs_full"),
        InlineKeyboardButton("🧹 Loglarni tozalash", callback_data="logs_clear"),
        InlineKeyboardButton("📤 Loglarni yuklash", callback_data="logs_download"),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back")
    )
    
    await message.answer("Boshqa amallar:", reply_markup=keyboard)

# =============== SYSTEM STATISTICS ===============
async def system_statistics(message: types.Message):
    """Tizim statistikasi"""
    
    if message.from_user.id not in ADMIN_IDS:
        return
    
    with get_db_session() as db:
        # Umumiy statistikalar
        stats = crud.get_warehouse_statistics(db)
        
        # Xodimlar statistikasi
        total_employees = db.query(models.Employee).count()
        active_employees = db.query(models.Employee).filter(
            models.Employee.status == models.EmployeeStatus.ACTIVE
        ).count()
        
        # Ishlab chiqarish statistikasi
        total_orders = db.query(models.ProductionOrder).count()
        completed_orders = db.query(models.ProductionOrder).filter(
            models.ProductionOrder.status == models.OrderStatus.COMPLETED
        ).count()
        
        # Sotuvlar statistikasi
        total_sales = db.query(models.Sale).count()
        total_sales_amount = db.query(func.sum(models.Sale.total_amount)).scalar() or 0
        
        # Loglar statistikasi
        today = datetime.utcnow().date()
        todays_logs = db.query(models.SystemLog).filter(
            func.date(models.SystemLog.created_at) == today
        ).count()
    
    stats_text = f"""
📊 **TIZIM STATISTIKASI**

👥 **Xodimlar:**
├ Jami: {total_employees} ta
├ Faol: {active_employees} ta
└ Faol emas: {total_employees - active_employees} ta

🏭 **Ishlab chiqarish:**
├ Jami buyurtmalar: {total_orders} ta
├ Bajarilgan: {completed_orders} ta
└ Bajarilish darajasi: {completed_orders/total_orders*100 if total_orders > 0 else 0:.1f}%

💰 **Sotuvlar:**
├ Jami sotuvlar: {total_sales} ta
└ Jami daromad: {total_sales_amount:,.0f} so'm

📦 **Ombor:**
├ Xom ashyo turi: {stats['total_materials_count']} ta
├ Yetarli bo'lmagan: {stats['low_stock_materials_count']} ta
└ Umumiy qiymat: {stats['total_raw_materials_value']:,.0f} so'm

📝 **Faollik:**
└ Bugungi loglar: {todays_logs} ta
"""
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📈 Batafsil statistika", callback_data="stats_detailed"),
        InlineKeyboardButton("📊 Grafiklar", callback_data="stats_charts"),
        InlineKeyboardButton("📤 Excel hisobot", callback_data="stats_excel"),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back")
    )
    
    await message.answer(stats_text, reply_markup=keyboard, parse_mode="Markdown")

# =============== CALLBACK HANDLERS ===============
async def admin_callback_handler(callback_query: types.CallbackQuery, state: FSMContext):
    """Admin callback handler"""
    
    data = callback_query.data
    
    if data == "admin_back":
        await callback_query.answer()
        await admin_panel(callback_query.message)
        return
    
    elif data == "admin_add_admin":
        await add_new_admin(callback_query, state)
    
    elif data == "admin_list_admins":
        await list_admins(callback_query)
    
    elif data == "admin_user_stats":
        await system_statistics(callback_query.message)
    
    elif data == "settings_notifications":
        await callback_query.answer("⚠️ Bu funksiya hozircha ishlamaydi", show_alert=True)
    
    elif data == "settings_backup":
        await backup_database(callback_query.message)
    
    elif data == "backup_confirm":
        await perform_backup(callback_query)
    
    elif data == "backup_cancel":
        await callback_query.answer("Backup bekor qilindi")
        await admin_panel(callback_query.message)
    
    elif data == "logs_full":
        await view_full_logs(callback_query.message)
    
    elif data == "stats_detailed":
        await detailed_statistics(callback_query.message)
    
    else:
        await callback_query.answer("⚠️ Bu funksiya hozircha ishlamaydi", show_alert=True)

# =============== REGISTER HANDLERS ===============
def register_handlers_admin(dp: Dispatcher):
    """Admin handlers ni ro'yxatdan o'tkazish"""
    
    # Admin paneli
    dp.message.register(admin_panel, Command('admin', 'adm'))
    dp.message.register(admin_panel, F.text == "👑 Admin paneli")
    
    # User management
    dp.message.register(admin_user_management, F.text == "👥 Xodimlar boshqaruvi")
    
    # System settings
    dp.message.register(system_settings, F.text == "⚙️ Tizim sozlamalari")
    
    # Audit logs
    dp.message.register(view_audit_logs, F.text == "📝 Audit loglari")
    
    # System statistics
    dp.message.register(system_statistics, F.text == "📊 Tizim statistika")
    
    # Backup database
    dp.message.register(backup_database, F.text == "💾 Backup olish")
    
    # Callback handlers
    dp.callback_query.register(admin_callback_handler, 
                               F.data.startswith('admin_') | 
                               F.data.startswith('settings_') |
                               F.data.startswith('backup_') |
                               F.data.startswith('logs_') |
                               F.data.startswith('stats_'))
    
    # Admin state handlers
    dp.message.register(process_new_admin_id, AdminStates.waiting_new_admin_id)
    dp.message.register(process_admin_name, AdminStates.waiting_admin_name)

# =============== YORDAMCHI FUNKSIYALAR ===============
async def detailed_statistics(message: types.Message):
    """Batafsil statistika"""
    
    with get_db_session() as db:
        # Haftalik statistika
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        weekly_orders = db.query(models.ProductionOrder).filter(
            models.ProductionOrder.created_at >= week_ago
        ).count()
        
        weekly_sales = db.query(models.Sale).filter(
            models.Sale.sale_date >= week_ago
        ).count()
        
        weekly_sales_amount = db.query(func.sum(models.Sale.total_amount)).filter(
            models.Sale.sale_date >= week_ago
        ).scalar() or 0
        
        # Eng ko'p sotilgan mahsulotlar
        top_products = db.query(
            models.Product.name,
            func.sum(models.Sale.quantity).label('total_sold')
        ).join(models.Sale).group_by(models.Product.id).order_by(
            func.sum(models.Sale.quantity).desc()
        ).limit(5).all()
    
    detailed_text = f"""
📈 **BATAFSIL STATISTIKA**

📅 **Haftalik ko'rsatkichlar (oxirgi 7 kun):**
├ Buyurtmalar: {weekly_orders} ta
├ Sotuvlar: {weekly_sales} ta
└ Daromad: {weekly_sales_amount:,.0f} so'm

🏆 **Eng ko'p sotilgan mahsulotlar:**
"""
    
    for product in top_products:
        detailed_text += f"├ {product.name}: {product.total_sold} dona\n"
    
    await message.answer(detailed_text, parse_mode="Markdown")

async def view_full_logs(message: types.Message):
    """To'liq audit loglari"""
    
    with get_db_session() as db:
        logs = db.query(models.SystemLog).order_by(
            models.SystemLog.created_at.desc()
        ).all()
    
    if not logs:
        await message.answer("❌ Hech qanday log mavjud emas.")
        return
    
    # Excel hisobot yaratish
    import pandas as pd
    from datetime import datetime
    
    log_data = []
    for log in logs:
        log_data.append({
            'Sana': log.created_at.strftime('%Y-%m-%d %H:%M'),
            'Foydalanuvchi': log.user_name or 'Tizim',
            'Amal': log.action,
            'Modul': log.module,
            'Tafsilot': log.details or '',
            'IP': log.ip_address or ''
        })
    
    df = pd.DataFrame(log_data)
    
    # Excel fayl yaratish
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"audit_logs_{timestamp}.xlsx"
    filepath = f"reports/excel/{filename}"
    
    df.to_excel(filepath, index=False)
    
    await message.answer_document(
        document=types.InputFile(filepath),
        caption=f"📋 To'liq audit loglari ({len(logs)} ta yozuv)"
    )