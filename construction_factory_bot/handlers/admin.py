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
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yangi admin qo'shish", callback_data="admin_add_admin"),
         InlineKeyboardButton(text="➖ Adminni olib tashlash", callback_data="admin_remove_admin")],
        [InlineKeyboardButton(text="📋 Adminlar ro'yxati", callback_data="admin_list_admins"),
         InlineKeyboardButton(text="👥 Barcha xodimlar", callback_data="admin_list_all_users")],
        [InlineKeyboardButton(text="📊 Xodim statistikasi", callback_data="admin_user_stats"),
         InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_back")],
    ])
    
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
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔔 Ogohlantirishlar", callback_data="settings_notifications"),
         InlineKeyboardButton(text="💾 Backup", callback_data="settings_backup")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="settings_stats"),
         InlineKeyboardButton(text="🔐 Ruxsatlar", callback_data="settings_permissions")],
        [InlineKeyboardButton(text="🔄 Yangilash tezligi", callback_data="settings_update"),
         InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_back")],
    ])
    
    await message.answer(settings_text + "\nSozlamani tanlang:", 
                        reply_markup=keyboard, parse_mode="Markdown")

async def backup_database(message: types.Message):
    """Backup boshqaruvi paneli (olish / tarix / tiklash)"""
    
    if message.from_user.id not in ADMIN_IDS:
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Backup olish", callback_data="backup_do")],
        [InlineKeyboardButton(text="📋 Backup tarixi", callback_data="backup_history"),
         InlineKeyboardButton(text="♻️ Backupdan tiklash", callback_data="restore_menu")],
        [InlineKeyboardButton(text="☁️ Bulutdan tiklash (S3)", callback_data="s3restore_menu")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_back")],
    ])
    
    await message.answer(
        "💾 **BACKUP BOSHQARUVI**\n\n"
        "• 💾 Backup olish — hozir zaxira nusxa olish\n"
        "• 📋 Backup tarixi — saqlangan nusxalar (hajmi bilan)\n"
        "• ♻️ Backupdan tiklash — lokal nusxadan databaseni qaytarish (⚠️ ehtiyot bo'ling!)\n"
        "• ☁️ Bulutdan tiklash — S3 bucket'dagi nusxani yuklab olib tiklash\n\n"
        "Amalni tanlang:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

async def perform_backup(callback_query: types.CallbackQuery):
    """Database backup olish (konsistent nusxa + eskilarni tozalash)"""
    
    await callback_query.answer("Backup olinmoqda...")
    
    try:
        from utils.backup import run_database_backup
        result = await run_database_backup(notify=True)
        
        created = result.get("created")
        if created:
            fname = created.split("/")[-1].split("\\")[-1]
            await callback_query.message.answer(
                f"✅ **BACKUP MUVAFFAQIYATLI BAJARILDI!**\n\n"
                f"📁 Fayl: `{fname}`\n"
                f"📦 Hajmi: {backup_size_mb(created):.2f} MB\n"
                f"🧹 Eski nusxalar: {result.get('pruned', 0)} ta o'chirildi\n"
                f"📅 Sana: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"💾 Backup faylini xavfsiz joyda saqlang.",
                parse_mode="Markdown"
            )
        else:
            await callback_query.message.answer(
                f"❌ **BACKUP OLINMADI!**\n\n{result.get('error') or 'Noma\'lum xatolik'}",
                parse_mode="Markdown"
            )
        
        # Tizim logiga yozish
        with get_db_session() as db:
            crud.create_system_log(
                db,
                user_id=callback_query.from_user.id,
                user_name=callback_query.from_user.full_name,
                action=f"Database backup: {created or 'olinmadi'}",
                module="backup"
            )
    
    except Exception as e:
        logger.error(f"Backup error: {e}")
        await callback_query.message.answer(f"❌ Backup jarayonida xatolik: {str(e)}")


def backup_size_mb(path: str) -> float:
    """Fayl hajmini MB da qaytarish"""
    try:
        import os
        return os.path.getsize(path) / (1024 * 1024)
    except OSError:
        return 0.0


async def show_backup_history(callback_query: types.CallbackQuery):
    """Saqlangan backup nusxalar tarixini ko'rsatish (hajmi bilan)"""
    
    await callback_query.answer()
    
    try:
        from utils.backup import list_backup_files
        files = list_backup_files(limit=15)
    except Exception as e:
        files = []
        logger.error(f"Backup tarixini olishda xatolik: {e}")
    
    if not files:
        await callback_query.message.answer(
            "📭 **BACKUP TARIXI**\n\nHozircha backup nusxalar mavjud emas.\n"
            "«💾 Backup olish» tugmasi orqali birinchi nusxani oling.",
            parse_mode="Markdown"
        )
        return
    
    total_mb = sum(f["size_mb"] for f in files)
    text = f"📋 **BACKUP TARIXI** — {len(files)} ta nusxa\n\n"
    for i, f in enumerate(files, 1):
        text += (
            f"{i}. 📁 `{f['filename']}`\n"
            f"   📦 {f['size_mb']:.2f} MB | 🕐 {f['created_at'][:16].replace('T', ' ')}"
        )
        text += "\n\n"
    text += f"💰 Jami: {total_mb:.2f} MB\n\n"
    text += "♻️ Tiklash uchun «Backupdan tiklash» bo'limidan foydalaning."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="♻️ Backupdan tiklash", callback_data="restore_menu")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_back")],
    ])
    await callback_query.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


async def show_restore_menu(callback_query: types.CallbackQuery):
    """Qaysi backup'dan tiklashni tanlash (fayl ro'yxati)"""
    
    await callback_query.answer()
    
    try:
        from utils.backup import list_backup_files
        files = list_backup_files(limit=10)
    except Exception as e:
        files = []
        logger.error(f"Backup ro'yxatini olishda xatolik: {e}")
    
    if not files:
        await callback_query.message.answer(
            "📭 **TIKLASH UCHUN BACKUP YO'Q**\n\nAvval «💾 Backup olish» tugmasi orqali nusxa oling.",
            parse_mode="Markdown"
        )
        return
    
    rows = [
        [InlineKeyboardButton(
            text=f"📁 {f['filename']} ({f['size_mb']:.1f} MB)",
            callback_data=f"restore_pick_{f['filename']}")]
        for f in files
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_back")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
    
    await callback_query.message.answer(
        "⚠️ **DATABASENI TIKLASH**\n\n"
        "Qaysi backup nusxadan tiklamoqchisiz?\n\n"
        "❌ DIQQAT: tiklash joriy barcha ma'lumotlarni almashtiradi! "
        "Tiklashdan oldin joriy holatning xavfsizlik nusxasi avtomatik olinadi.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


async def confirm_restore(callback_query: types.CallbackQuery):
    """Tanlangan backup'dan tiklashni tasdiqlash so'rash"""
    
    filename = callback_query.data.replace("restore_pick_", "", 1)
    await callback_query.answer()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha, tiklash", callback_data=f"restore_confirm_{filename}"),
         InlineKeyboardButton(text="❌ Bekor qilish", callback_data="restore_cancel")],
    ])
    
    await callback_query.message.answer(
        f"⚠️ **TIKLASHNI TASDIQLASH**\n\n"
        f"📁 Fayl: `{filename}`\n\n"
        f"Joriy database ushbu nusxa bilan ALMASHTIRILADI. Amalni qaytarib bo'lmaydi "
        f"(joriy holat nusxasi `backups/` papkasiga avtomatik saqlanadi).\n\n"
        f"Tasdiqlaysizmi?",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


async def perform_restore(callback_query: types.CallbackQuery):
    """Backup'dan databaseni tiklash"""
    
    filename = callback_query.data.replace("restore_confirm_", "", 1)
    await callback_query.answer("Tiklanmoqda...")
    
    try:
        from utils.backup import restore_database
        # Sync (fayl amali) — UI bloklanmasligi uchun thread'da bajariladi
        import asyncio
        result = await asyncio.to_thread(restore_database, filename)
        
        if result.get("success"):
            safety = result.get("safety_backup")
            safety_name = safety.split("/")[-1].split("\\")[-1] if safety else None
            text = (
                f"✅ **DATABASE TIKLANDI!**\n\n"
                f"📁 Manba: `{filename}`\n"
                f"💾 Xavfsizlik nusxasi: `{safety_name or '-'}`\n\n"
                f"⚠️ Eslatma: agar bot va API (uvicorn) bir vaqtda ishlayotgan "
                f"bo'lsa, tiklangan ma'lumot to'liq ko'rinishi uchun ikkala "
                f"jarayonni ham qayta ishga tushiring (ochiq ulanishlar eski "
                f"ma'lumotni ko'rsatishi mumkin). Login sessiyalari ham eskirgan "
                f"bo'lishi mumkin — qayta kirish talab qilinishi ehtimoli bor."
            )
            await callback_query.message.answer(text, parse_mode="Markdown")
            
            # Tizim logiga yozish (tiklangan DB ga — hujjatlash uchun)
            try:
                with get_db_session() as db:
                    crud.create_system_log(
                        db,
                        user_id=callback_query.from_user.id,
                        user_name=callback_query.from_user.full_name,
                        action=f"Database tiklandi: {filename}",
                        module="backup"
                    )
            except Exception as e:
                logger.error(f"Tiklash logini yozishda xatolik: {e}")
        else:
            await callback_query.message.answer(
                f"❌ **TIKLASH BAJARILMADI!**\n\n{result.get('error') or 'Noma\'lum xatolik'}",
                parse_mode="Markdown"
            )
    
    except Exception as e:
        logger.error(f"Restore error: {e}")
        await callback_query.message.answer(f"❌ Tiklash jarayonida xatolik: {str(e)}")


async def cancel_restore(callback_query: types.CallbackQuery):
    """Tiklashni bekor qilish"""
    await callback_query.answer("Bekor qilindi")
    await backup_database(callback_query.message)


async def show_s3_restore_menu(callback_query: types.CallbackQuery):
    """S3 bucket'dagi backup'lardan tiklash — ob'ektlarni tanlash"""

    await callback_query.answer()

    try:
        from utils.backup import list_s3_remote_backups
        objects = list_s3_remote_backups(limit=10)
    except Exception as e:
        objects = []
        logger.error(f"S3 backup ro'yxatini olishda xatolik: {e}")

    if not objects:
        await callback_query.message.answer(
            "☁️ **BULUTDAN TIKLASH (S3)**\n\n"
            "S3 bucket'da backup topilmadi yoki S3 sozlanmagan.\n"
            "`BACKUP_UPLOAD=s3` va `BACKUP_S3_*` sozlamalarini tekshiring.",
            parse_mode="Markdown"
        )
        return

    rows = []
    for i, obj in enumerate(objects, 1):
        name = obj.get("name", obj.get("key", "?"))
        size_mb = obj.get("size_mb", 0)
        enc = " 🔐" if obj.get("encrypted") else ""
        rows.append([InlineKeyboardButton(
            text=f"{i}. {name} ({size_mb:.1f} MB){enc}",
            callback_data=f"s3restore_pick_{i}")])
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_back")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=rows)

    await callback_query.message.answer(
        "☁️ **BULUTDAN TIKLASH (S3)**\n\n"
        "Qaysi bulut nusxadan tiklamoqchisiz?\n\n"
        "⚠️ DIQQAT: tiklash joriy barcha ma'lumotlarni almashtiradi! "
        "Xavfsizlik nusxasi avtomatik olinadi.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


async def confirm_s3_restore(callback_query: types.CallbackQuery):
    """Tanlangan S3 ob'ektdan tiklashni tasdiqlash"""

    idx = int(callback_query.data.replace("s3restore_pick_", "", 1))
    await callback_query.answer()

    try:
        from utils.backup import list_s3_remote_backups
        objects = list_s3_remote_backups(limit=10)
        obj = objects[idx - 1] if 0 < idx <= len(objects) else None
    except Exception:
        obj = None

    if obj is None:
        await callback_query.message.answer(
            "❌ Tanlangan ob'ekt topilmadi. Qaytadan urinib ko'ring.")
        return

    key = obj["key"]
    enc = " 🔐 shifrlangan" if obj.get("encrypted") else ""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Ha, tiklash", callback_data=f"s3restore_confirm_{idx}"),
         InlineKeyboardButton(text="❌ Bekor qilish", callback_data="restore_cancel")],
    ])

    await callback_query.message.answer(
        f"⚠️ **S3 NUSXADAN TIKLASHNI TASDIQLASH**\n\n"
        f"☁️ Ob'ekt: `{key}`{enc}\n\n"
        f"Bu nusxa S3'dan yuklab olinadi va joriy database ALMASHTIRILADI. "
        f"Joriy holat nusxasi `backups/` papkasiga avtomatik saqlanadi.\n\n"
        f"Tasdiqlaysizmi?",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


async def perform_s3_restore(callback_query: types.CallbackQuery):
    """S3'dagi backup'dan databaseni tiklash (yuklab olib)"""

    idx = int(callback_query.data.replace("s3restore_confirm_", "", 1))
    await callback_query.answer("Yuklab olinmoqda va tiklanmoqda...")

    try:
        from utils.backup import list_s3_remote_backups, restore_database_from_s3
        objects = list_s3_remote_backups(limit=10)
        obj = objects[idx - 1] if 0 < idx <= len(objects) else None
        if obj is None:
            raise ValueError("Ob'ekt topilmadi")

        import asyncio
        result = await asyncio.to_thread(
            restore_database_from_s3, obj["key"])

        if result.get("success"):
            safety = result.get("safety_backup")
            safety_name = safety.split("/")[-1].split("\\")[-1] if safety else None
            text = (
                f"✅ **S3 NUSXADAN DATABASE TIKLANDI!**\n\n"
                f"☁️ Manba: `{obj['key']}`\n"
                f"💾 Xavfsizlik nusxasi: `{safety_name or '-'}`\n\n"
                f"⚠️ Eslatma: bot va API (uvicorn) bir vaqtda ishlayotgan bo'lsa, "
                f"tiklangan ma'lumot to'liq ko'rinishi uchun ikkala jarayonni ham "
                f"qayta ishga tushiring."
            )
            await callback_query.message.answer(text, parse_mode="Markdown")
            try:
                with get_db_session() as db:
                    crud.create_system_log(
                        db,
                        user_id=callback_query.from_user.id,
                        user_name=callback_query.from_user.full_name,
                        action=f"S3'dan database tiklandi: {obj['key']}",
                        module="backup"
                    )
            except Exception as e:
                logger.error(f"S3 tiklash logini yozishda xatolik: {e}")
        else:
            await callback_query.message.answer(
                f"❌ **S3 NUSXADAN TIKLASH BAJARILMADI!**\n\n"
                f"{result.get('error') or 'Noma\'lum xatolik'}",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"S3 restore error: {e}")
        await callback_query.message.answer(f"❌ S3 tiklashda xatolik: {str(e)}")


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
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 To'liq loglar", callback_data="logs_full"),
         InlineKeyboardButton(text="🧹 Loglarni tozalash", callback_data="logs_clear")],
        [InlineKeyboardButton(text="📤 Loglarni yuklash", callback_data="logs_download"),
         InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_back")],
    ])
    
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
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Batafsil statistika", callback_data="stats_detailed"),
         InlineKeyboardButton(text="📊 Grafiklar", callback_data="stats_charts")],
        [InlineKeyboardButton(text="📤 Excel hisobot", callback_data="stats_excel"),
         InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_back")],
    ])
    
    await message.answer(stats_text, reply_markup=keyboard, parse_mode="Markdown")

# =============== CALLBACK HANDLERS ===============
async def remove_admin(callback_query: types.CallbackQuery, state: FSMContext):
    """Adminni olib tashlash"""
    
    if callback_query.from_user.id != MAIN_ADMIN_ID:
        await callback_query.answer("❌ Faqat asosiy admin adminni olib tashlaydi!", show_alert=True)
        return
    
    await callback_query.answer()
    
    with get_db_session() as db:
        admins = db.query(models.Employee).filter(
            models.Employee.is_admin == True
        ).all()
    
    if len(admins) <= 1:
        await callback_query.message.answer("❌ Kamida bitta admin bo'lishi kerak!")
        return
    
    admin_rows = [
        [InlineKeyboardButton(text=f"➖ {admin.full_name} (ID: {admin.telegram_id})", callback_data=f"confirm_remove_admin_{admin.id}")] 
        for admin in admins if admin.telegram_id != MAIN_ADMIN_ID
    ]
    admin_rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_back")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=admin_rows)
    
    await callback_query.message.answer(
        "➖ **ADMINNI OLIB TASHLASH**\n\n"
        "Qaysi adminni olib tashlamoqchisiz?",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


async def confirm_remove_admin(callback_query: types.CallbackQuery):
    """Adminni olib tashlashni tasdiqlash"""
    employee_id = int(callback_query.data.replace("confirm_remove_admin_", ""))
    
    with get_db_session() as db:
        employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
        if employee:
            employee.is_admin = False
            db.commit()
            
            crud.create_system_log(
                db,
                user_id=callback_query.from_user.id,
                user_name=callback_query.from_user.full_name,
                action=f"Admin olib tashlandi: {employee.full_name}",
                module="admin"
            )
            
            await callback_query.message.answer(
                f"✅ **{employee.full_name}** adminlikdan olib tashlandi.",
                parse_mode="Markdown"
            )
    
    await admin_panel(callback_query.message)


async def list_all_users(callback_query: types.CallbackQuery):
    """Barcha foydalanuvchilarni ko'rsatish"""
    await callback_query.answer()
    
    with get_db_session() as db:
        employees = db.query(models.Employee).order_by(
            models.Employee.department
        ).all()
    
    if not employees:
        await callback_query.message.answer("❌ Hozircha xodimlar mavjud emas.")
        return
    
    users_text = "👥 **BARCHA XODIMLAR**\n\n"
    
    for idx, emp in enumerate(employees, 1):
        status_icon = "🟢" if emp.status == models.EmployeeStatus.ACTIVE else "🔴"
        admin_badge = " 👑" if emp.is_admin else ""
        
        users_text += (
            f"{idx}. {status_icon} **{emp.full_name}**{admin_badge}\n"
            f"   📋 {emp.position} | 🏢 {emp.department}\n"
            f"   📞 {emp.phone_number} | 💰 {emp.salary:,.0f} so'm\n\n"
        )
    
    users_text += f"\n📊 Jami: {len(employees)} ta xodim"
    
    await callback_query.message.answer(users_text, parse_mode="Markdown")


async def admin_callback_handler(callback_query: types.CallbackQuery, state: FSMContext):
    """Admin callback handler"""
    
    data = callback_query.data
    
    if data == "admin_back":
        await callback_query.answer()
        await admin_panel(callback_query.message)
        return
    
    elif data == "admin_add_admin":
        await add_new_admin(callback_query, state)
    
    elif data == "admin_remove_admin":
        await remove_admin(callback_query, state)
    
    elif data.startswith("confirm_remove_admin_"):
        await confirm_remove_admin(callback_query)
    
    elif data == "admin_list_admins":
        await list_admins(callback_query)
    
    elif data == "admin_list_all_users":
        await list_all_users(callback_query)
    
    elif data == "admin_user_stats":
        await system_statistics(callback_query.message)
    
    elif data == "settings_notifications":
        from handlers.notifications import notifications_menu
        await notifications_menu(callback_query.message)
    
    elif data == "settings_backup":
        await backup_database(callback_query.message)
    
    elif data == "backup_do" or data == "backup_confirm":
        await perform_backup(callback_query)
    
    elif data == "backup_cancel":
        await callback_query.answer("Backup bekor qilindi")
        await backup_database(callback_query.message)
    
    elif data == "backup_history":
        await show_backup_history(callback_query)
    
    elif data == "restore_menu":
        await show_restore_menu(callback_query)
    
    elif data.startswith("restore_pick_"):
        await confirm_restore(callback_query)
    
    elif data.startswith("restore_confirm_"):
        await perform_restore(callback_query)
    
    elif data == "restore_cancel":
        await cancel_restore(callback_query)
    
    elif data == "s3restore_menu":
        await show_s3_restore_menu(callback_query)
    
    elif data.startswith("s3restore_pick_"):
        await confirm_s3_restore(callback_query)
    
    elif data.startswith("s3restore_confirm_"):
        await perform_s3_restore(callback_query)
    
    elif data == "logs_full":
        await view_full_logs(callback_query.message)
    
    elif data == "logs_clear":
        with get_db_session() as db:
            db.query(models.SystemLog).delete()
            db.commit()
        await callback_query.answer("✅ Loglar tozalandi")
        await admin_panel(callback_query.message)
    
    elif data == "logs_download":
        await view_full_logs(callback_query.message)
    
    elif data == "stats_detailed":
        await detailed_statistics(callback_query.message)
    
    elif data == "stats_charts":
        await callback_query.answer("📈 Grafiklar tayyorlanmoqda...")
        await system_statistics(callback_query.message)
    
    elif data == "stats_excel":
        await callback_query.answer("📊 Excel hisobot tayyorlanmoqda...")
        await system_statistics(callback_query.message)
    
    elif data == "settings_stats":
        await system_statistics(callback_query.message)
    
    elif data == "settings_permissions":
        permissions_text = (
            "🔐 **RUXSATLAR TIZIMI**\n\n"
            "👥 **Admin:**\n"
            "• Barcha funksiyalarga ruxsat\n"
            "• Xodimlarni boshqarish\n"
            "• Sozlamalarni o'zgartirish\n\n"
            "👤 **Xodim:**\n"
            "• Ombor holatini ko'rish\n"
            "• Buyurtma berish\n"
            "• Hisobotlarni ko'rish\n"
            "• Bildirishnomalarni ko'rish"
        )
        await callback_query.message.answer(permissions_text, parse_mode="Markdown")
    
    elif data == "settings_update":
        update_text = (
            "🔄 **YANGILANISH TIZIMI**\n\n"
            "📊 **Joriy versiya:** 2.0\n"
            "📅 **Oxirgi yangilanish:** 2024-01-15\n"
            "✅ **Holat:** Yangiroq versiya mavjud emas\n\n"
            "🔧 Yangilanishlar avtomatik ravishda amalga oshiriladi."
        )
        await callback_query.message.answer(update_text, parse_mode="Markdown")
    
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
    
    # Backup boshqaruvi (olish / tarix / tiklash)
    dp.message.register(backup_database, F.text == "💾 Backup va tiklash")
    
    # Callback handlers
    dp.callback_query.register(admin_callback_handler, 
                               F.data.startswith('admin_') | 
                               F.data.startswith('settings_') |
                               F.data.startswith('backup_') |
                               F.data.startswith('restore_') |
                               F.data.startswith('s3restore_') |
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