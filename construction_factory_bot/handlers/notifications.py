"""
Notifications Handler - Qurilish Korxonasi Bildirishnoma Tizimi
"""
from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from datetime import datetime, timedelta, date
import logging
import asyncio
from typing import List, Dict, Any

from database.session import get_db_session
from database import crud, models
from keyboards.main_menu import get_main_menu
from keyboards.admin_menu import get_notifications_menu
from config import ADMIN_IDS, NOTIFICATION_TYPES
from utils.notifications import (
    send_notification_to_all,
    send_notification_to_user,
    check_low_stock_notifications,
    check_production_notifications,
    check_system_notifications
)

logger = logging.getLogger(__name__)

# =============== NOTIFICATION STATES ===============
class NotificationStates(StatesGroup):
    # Create Notification
    waiting_notification_type = State()
    waiting_notification_title = State()
    waiting_notification_message = State()
    waiting_notification_recipient = State()
    waiting_notification_priority = State()
    waiting_notification_schedule = State()
    confirm_notification = State()
    
    # Manage Notifications
    viewing_notifications = State()
    editing_notification = State()
    
    # Settings
    waiting_notification_settings = State()
    waiting_setting_value = State()

# =============== NOTIFICATIONS MENU ===============
async def notifications_menu(message: types.Message):
    """Bildirishnomalar menyusi"""
    
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Sizda bu amalni bajarish huquqi yo'q!")
        return
    
    with get_db_session() as db:
        # Statistikani olish
        pending_count = db.query(models.Notification).filter(
            models.Notification.status == models.NotificationStatus.PENDING
        ).count()
        
        unread_count = db.query(models.Notification).filter(
            models.Notification.status == models.NotificationStatus.SENT,
            models.Notification.read_time.is_(None)
        ).count()
        
        today_count = db.query(models.Notification).filter(
            models.Notification.created_at >= datetime.utcnow().date()
        ).count()
    
    menu_text = f"""
🔔 **BILDIRISHNOMALAR BOSHQARUVI**

📊 **Statistika:**
├ 📭 Kutilayotgan: {pending_count} ta
├ 📨 Oʻqilmagan: {unread_count} ta
├ 📅 Bugungi: {today_count} ta
└ 📈 Jami: {pending_count + unread_count} ta

📋 **Imkoniyatlar:**
• 📝 Yangi bildirishnoma yaratish
• 📋 Barcha bildirishnomalarni koʻrish
• ⚙️ Sozlamalar
• 🔄 Avtomatik bildirishnomalar
• 📊 Statistika
"""
    
    await message.answer(menu_text, reply_markup=get_notifications_menu(), parse_mode="Markdown")

# =============== CREATE NOTIFICATION ===============
async def create_notification_start(message: types.Message):
    """Yangi bildirishnoma yaratishni boshlash"""
    
    if message.from_user.id not in ADMIN_IDS:
        return
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    for notif_type, notif_name in NOTIFICATION_TYPES.items():
        keyboard.insert(InlineKeyboardButton(notif_name, callback_data=f"type_{notif_type}"))
    
    keyboard.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="notif_back"))
    
    await message.answer("Bildirishnoma turini tanlang:", reply_markup=keyboard)
    await NotificationStates.waiting_notification_type.set()

async def process_notification_type(callback_query: types.CallbackQuery, state: FSMContext):
    """Bildirishnoma turini qabul qilish"""
    
    if callback_query.data == "notif_back":
        await callback_query.answer()
        await notifications_menu(callback_query.message)
        await state.finish()
        return
    
    notif_type = callback_query.data.replace("type_", "")
    notif_name = NOTIFICATION_TYPES.get(notif_type, "Noma'lum")
    
    await state.update_data(notification_type=notif_type)
    await callback_query.answer(f"Tanlangan: {notif_name}")
    
    await callback_query.message.answer("Bildirishnoma sarlavhasini kiriting:")
    await NotificationStates.waiting_notification_title.set()

async def process_notification_title(message: types.Message, state: FSMContext):
    """Bildirishnoma sarlavhasini qabul qilish"""
    
    await state.update_data(title=message.text)
    
    await message.answer("Bildirishnoma matnini kiriting:")
    await NotificationStates.waiting_notification_message.set()

async def process_notification_message(message: types.Message, state: FSMContext):
    """Bildirishnoma matnini qabul qilish"""
    
    await state.update_data(message=message.text)
    
    # Qabul qiluvchini tanlash
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("👥 Barcha foydalanuvchilar", callback_data="recipient_all"),
        InlineKeyboardButton("👑 Adminlar", callback_data="recipient_admins"),
        InlineKeyboardButton("🏭 Ishlab chiqarish boʻlimi", callback_data="recipient_production"),
        InlineKeyboardButton("📦 Ombor boʻlimi", callback_data="recipient_warehouse"),
        InlineKeyboardButton("💰 Buxgalteriya", callback_data="recipient_accounting"),
        InlineKeyboardButton("👤 Maxsus foydalanuvchi", callback_data="recipient_specific"),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="notif_back_to_type")
    )
    
    await message.answer("Kimga yuborilsin?", reply_markup=keyboard)
    await NotificationStates.waiting_notification_recipient.set()

async def process_notification_recipient(callback_query: types.CallbackQuery, state: FSMContext):
    """Qabul qiluvchini qabul qilish"""
    
    if callback_query.data == "notif_back_to_type":
        await callback_query.answer()
        await create_notification_start(callback_query.message)
        return
    
    recipient_type = callback_query.data.replace("recipient_", "")
    
    if recipient_type == "specific":
        await callback_query.answer()
        await callback_query.message.answer("Foydalanuvchi ID sini kiriting:")
        await NotificationStates.waiting_notification_recipient.set()
        await state.update_data(recipient_type="specific")
        return
    
    await state.update_data(recipient_type=recipient_type)
    
    # Recipient ID ni aniqlash
    recipient_id = 0  # 0 = hamma uchun
    
    if recipient_type == "admins":
        # Adminlar uchun alohida belgi
        recipient_id = -1
    elif recipient_type in ["production", "warehouse", "accounting"]:
        # Bo'limlar uchun alohida belgilar
        department_map = {
            "production": -2,
            "warehouse": -3,
            "accounting": -4
        }
        recipient_id = department_map[recipient_type]
    
    await state.update_data(recipient_id=recipient_id)
    await callback_query.answer(f"Tanlangan: {recipient_type}")
    
    # Priority tanlash
    keyboard = InlineKeyboardMarkup(row_width=3)
    keyboard.add(
        InlineKeyboardButton("🟢 Past (1)", callback_data="priority_1"),
        InlineKeyboardButton("🟡 Oʻrta (2)", callback_data="priority_2"),
        InlineKeyboardButton("🟠 Yuqori (3)", callback_data="priority_3"),
        InlineKeyboardButton("🔴 Judayam yuqori (4)", callback_data="priority_4"),
        InlineKeyboardButton("🚨 Favqulodda (5)", callback_data="priority_5")
    )
    
    await callback_query.message.answer("Bildirishnoma ustuvorligini tanlang:", reply_markup=keyboard)
    await NotificationStates.waiting_notification_priority.set()

async def process_notification_priority(callback_query: types.CallbackQuery, state: FSMContext):
    """Ustuvorlikni qabul qilish"""
    
    priority = int(callback_query.data.replace("priority_", ""))
    await state.update_data(priority=priority)
    
    priority_text = {
        1: "🟢 Past",
        2: "🟡 Oʻrta", 
        3: "🟠 Yuqori",
        4: "🔴 Judayam yuqori",
        5: "🚨 Favqulodda"
    }.get(priority, "🟢 Past")
    
    await callback_query.answer(f"Tanlangan: {priority_text}")
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("⏰ Darhol yuborish", callback_data="schedule_now"),
        InlineKeyboardButton("📅 Vaqt belgilash", callback_data="schedule_later"),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="notif_back_to_recipient")
    )
    
    await callback_query.message.answer("Qachon yuborilsin?", reply_markup=keyboard)
    await NotificationStates.waiting_notification_schedule.set()

async def process_notification_schedule(callback_query: types.CallbackQuery, state: FSMContext):
    """Vaqtni qabul qilish"""
    
    if callback_query.data == "notif_back_to_recipient":
        await callback_query.answer()
        data = await state.get_data()
        await process_notification_message(callback_query.message, state)
        return
    
    if callback_query.data == "schedule_now":
        schedule_time = datetime.utcnow()
        await state.update_data(scheduled_time=schedule_time)
        await confirm_notification(callback_query, state)
        return
    
    await callback_query.answer()
    await callback_query.message.answer(
        "Vaqtni kiriting (YYYY-MM-DD HH:MM formatida):\nMasalan: 2024-12-15 14:30",
        reply_markup=ReplyKeyboardRemove()
    )
    await NotificationStates.waiting_notification_schedule.set()

async def process_schedule_time(message: types.Message, state: FSMContext):
    """Vaqtni qabul qilish (matn formatida)"""
    
    try:
        schedule_time = datetime.strptime(message.text, "%Y-%m-%d %H:%M")
        
        # Vaqtni UTC ga o'tkazish
        from pytz import timezone
        import pytz
        
        local_tz = timezone('Asia/Tashkent')  # O'zbekiston vaqti
        utc_tz = pytz.utc
        
        local_dt = local_tz.localize(schedule_time)
        utc_dt = local_dt.astimezone(utc_tz)
        
        await state.update_data(scheduled_time=utc_dt)
        await confirm_notification(message, state)
        
    except ValueError:
        await message.answer("❌ Notoʻgʻri vaqt formati. YYYY-MM-DD HH:MM formatida kiriting:")

async def confirm_notification(callback_query_or_message, state: FSMContext):
    """Bildirishnomani tasdiqlash"""
    
    data = await state.get_data()
    
    # Recipient nomini aniqlash
    recipient_map = {
        "all": "👥 Barcha foydalanuvchilar",
        "admins": "👑 Adminlar",
        "production": "🏭 Ishlab chiqarish boʻlimi",
        "warehouse": "📦 Ombor boʻlimi",
        "accounting": "💰 Buxgalteriya",
        "specific": f"👤 Maxsus foydalanuvchi (ID: {data.get('recipient_id', 'Nomaʻlum')})"
    }
    
    recipient_name = recipient_map.get(data['recipient_type'], "Nomaʻlum")
    
    # Priority nomini aniqlash
    priority_names = {
        1: "🟢 Past",
        2: "🟡 Oʻrta",
        3: "🟠 Yuqori",
        4: "🔴 Judayam yuqori",
        5: "🚨 Favqulodda"
    }
    
    priority_name = priority_names.get(data.get('priority', 1), "🟢 Past")
    
    # Schedule vaqtini formatlash
    schedule_time = data.get('scheduled_time', datetime.utcnow())
    if isinstance(schedule_time, datetime):
        schedule_text = schedule_time.strftime("%Y-%m-%d %H:%M")
    else:
        schedule_text = "⏰ Darhol"
    
    summary = f"""
📝 **YANGI BILDIRISHNOMA**

🔤 **Tur:** {NOTIFICATION_TYPES.get(data['notification_type'], 'Nomaʻlum')}
📋 **Sarlavha:** {data['title']}
📄 **Matn:** {data['message']}
👥 **Qabul qiluvchi:** {recipient_name}
🎯 **Ustuvorlik:** {priority_name}
⏰ **Vaqt:** {schedule_text}

Bildirishnomani yuboramizmi?
"""
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Ha, yuborish", callback_data="confirm_notif_yes"),
        InlineKeyboardButton("❌ Yoʻq, bekor qilish", callback_data="confirm_notif_no")
    )
    
    if isinstance(callback_query_or_message, types.CallbackQuery):
        await callback_query_or_message.message.answer(summary, reply_markup=keyboard, parse_mode="Markdown")
        await callback_query_or_message.answer()
    else:
        await callback_query_or_message.answer(summary, reply_markup=keyboard, parse_mode="Markdown")
    
    await NotificationStates.confirm_notification.set()

async def save_notification(callback_query: types.CallbackQuery, state: FSMContext):
    """Bildirishnomani saqlash"""
    
    await callback_query.answer()
    
    if callback_query.data == "confirm_notif_yes":
        data = await state.get_data()
        
        with get_db_session() as db:
            # Bildirishnomani yaratish
            notification_data = {
                'notification_type': data['notification_type'],
                'title': data['title'],
                'message': data['message'],
                'recipient_id': data.get('recipient_id', 0),
                'priority': data.get('priority', 1),
                'scheduled_time': data.get('scheduled_time'),
                'status': models.NotificationStatus.PENDING
            }
            
            notification = crud.create_notification(db, notification_data)
            
            # Tizim logiga yozish
            crud.create_system_log(
                db,
                user_id=callback_query.from_user.id,
                user_name=callback_query.from_user.full_name,
                action=f"Yangi bildirishnoma yaratildi: {data['title']}",
                module="notifications"
            )
        
        # Agar darhol yuborish kerak bo'lsa
        if not data.get('scheduled_time') or data['scheduled_time'] <= datetime.utcnow():
            await send_notification_now(notification.id, callback_query.message)
        
        await callback_query.message.answer(
            f"✅ **Bildirishnoma muvaffaqiyatli yaratildi!**\n\n"
            f"📋 ID: {notification.id}\n"
            f"🔤 Tur: {NOTIFICATION_TYPES.get(data['notification_type'], 'Nomaʻlum')}\n"
            f"📋 Sarlavha: {data['title']}\n"
            f"👥 Qabul qiluvchi: {data['recipient_type']}\n"
            f"⏰ Vaqt: {data.get('scheduled_time', 'Darhol')}\n\n"
            f"📨 Bildirishnoma yuborish rejimga qoʻyildi.",
            parse_mode="Markdown",
            reply_markup=get_notifications_menu()
        )
    
    else:
        await callback_query.message.answer(
            "❌ Bildirishnoma yaratish bekor qilindi.",
            reply_markup=get_notifications_menu()
        )
    
    await state.finish()

async def send_notification_now(notification_id: int, message: types.Message = None):
    """Bildirishnomani darhol yuborish"""
    
    with get_db_session() as db:
        notification = db.query(models.Notification).filter(
            models.Notification.id == notification_id
        ).first()
        
        if not notification:
            if message:
                await message.answer("❌ Bildirishnoma topilmadi.")
            return
        
        # Qabul qiluvchilarni aniqlash
        recipient_id = notification.recipient_id
        
        try:
            if recipient_id == 0:  # Barcha foydalanuvchilar
                await send_notification_to_all(notification.title, notification.message)
                success = True
                
            elif recipient_id == -1:  # Adminlar
                admins = db.query(models.Employee).filter(
                    models.Employee.is_admin == True,
                    models.Employee.telegram_id.isnot(None)
                ).all()
                
                for admin in admins:
                    if admin.telegram_id:
                        await send_notification_to_user(
                            admin.telegram_id,
                            notification.title,
                            notification.message
                        )
                success = True
                
            elif recipient_id < 0:  # Bo'limlar
                department_map = {
                    -2: "Ishlab chiqarish",
                    -3: "Ombor",
                    -4: "Buxgalteriya"
                }
                
                department = department_map.get(recipient_id)
                if department:
                    employees = db.query(models.Employee).filter(
                        models.Employee.department == department,
                        models.Employee.telegram_id.isnot(None)
                    ).all()
                    
                    for emp in employees:
                        if emp.telegram_id:
                            await send_notification_to_user(
                                emp.telegram_id,
                                notification.title,
                                notification.message
                            )
                    success = True
                else:
                    success = False
                    
            else:  # Maxsus foydalanuvchi
                await send_notification_to_user(
                    recipient_id,
                    notification.title,
                    notification.message
                )
                success = True
            
            if success:
                # Statusni yangilash
                notification.status = models.NotificationStatus.SENT
                notification.sent_time = datetime.utcnow()
                db.commit()
                
                if message:
                    await message.answer(f"✅ Bildirishnoma #{notification_id} yuborildi!")
            else:
                if message:
                    await message.answer(f"❌ Bildirishnoma #{notification_id} yuborilmadi.")
        
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            if message:
                await message.answer(f"❌ Bildirishnoma yuborishda xatolik: {str(e)}")

# =============== VIEW NOTIFICATIONS ===============
async def view_notifications(message: types.Message):
    """Bildirishnomalarni ko'rish"""
    
    with get_db_session() as db:
        # Oxirgi 20 ta bildirishnomani olish
        notifications = db.query(models.Notification).order_by(
            models.Notification.created_at.desc()
        ).limit(20).all()
    
    if not notifications:
        await message.answer("📭 Hozircha bildirishnomalar mavjud emas.")
        return
    
    notifications_text = "📋 **BILDIRISHNOMALAR** (Oxirgi 20 ta)\n\n"
    
    for idx, notif in enumerate(notifications, 1):
        # Status belgisi
        status_icon = {
            models.NotificationStatus.PENDING: "⏳",
            models.NotificationStatus.SENT: "📨",
            models.NotificationStatus.READ: "✅",
            models.NotificationStatus.FAILED: "❌"
        }.get(notif.status, "❓")
        
        # Priority belgisi
        priority_icon = {
            1: "🟢", 2: "🟡", 3: "🟠", 4: "🔴", 5: "🚨"
        }.get(notif.priority, "⚪")
        
        # Vaqtni formatlash
        time_str = notif.created_at.strftime("%m-%d %H:%M")
        
        notifications_text += (
            f"{idx}. {status_icon}{priority_icon} **{notif.title}**\n"
            f"   📅 {time_str} | 👤 {get_recipient_name(notif.recipient_id)}\n"
            f"   📝 {notif.message[:50]}...\n\n"
        )
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📭 Kutilayotganlar", callback_data="view_pending"),
        InlineKeyboardButton("📨 Yuborilganlar", callback_data="view_sent"),
        InlineKeyboardButton("✅ Oʻqilganlar", callback_data="view_read"),
        InlineKeyboardButton("❌ Xatoliklar", callback_data="view_failed"),
        InlineKeyboardButton("📊 Statistika", callback_data="notif_stats"),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="notif_back")
    )
    
    await message.answer(notifications_text, parse_mode="Markdown", reply_markup=keyboard)
    await NotificationStates.viewing_notifications.set()

async def view_notification_details(callback_query: types.CallbackQuery):
    """Bildirishnoma tafsilotlarini ko'rish"""
    
    await callback_query.answer()
    
    # Bu yerda bildirishnoma ID sini aniqlash kerak
    # Hozircha oddiy versiya
    
    await callback_query.message.answer(
        "⚠️ Bu funksiya ishlab chiqilmoqda. Tez orada tayyor boʻladi.",
        reply_markup=get_notifications_menu()
    )

def get_recipient_name(recipient_id: int) -> str:
    """Qabul qiluvchi nomini olish"""
    
    recipient_map = {
        0: "👥 Hammaga",
        -1: "👑 Adminlar",
        -2: "🏭 Ishlab chiqarish",
        -3: "📦 Ombor",
        -4: "💰 Buxgalteriya"
    }
    
    return recipient_map.get(recipient_id, f"👤 ID:{recipient_id}")

# =============== AUTO NOTIFICATIONS ===============
async def auto_notifications(message: types.Message):
    """Avtomatik bildirishnoma sozlamalari"""
    
    if message.from_user.id not in ADMIN_IDS:
        return
    
    with get_db_session() as db:
        # Sozlamalarni olish
        auto_settings = {
            "low_stock": True,
            "production_complete": True,
            "order_delivered": True,
            "salary_payment": True,
            "system_alerts": True
        }
    
    settings_text = "⚙️ **AVTOMATIK BILDIRISHNOMA SOZLAMALARI**\n\n"
    
    for setting, enabled in auto_settings.items():
        status = "✅ Yoqilgan" if enabled else "❌ Oʻchirilgan"
        settings_text += f"• {NOTIFICATION_TYPES.get(setting, setting)}: {status}\n"
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    for setting in auto_settings.keys():
        button_text = f"❌ {NOTIFICATION_TYPES.get(setting, setting)}" if auto_settings[setting] else f"✅ {NOTIFICATION_TYPES.get(setting, setting)}"
        keyboard.insert(InlineKeyboardButton(button_text, callback_data=f"auto_toggle_{setting}"))
    
    keyboard.add(
        InlineKeyboardButton("🔔 Barchasini yoqish", callback_data="auto_enable_all"),
        InlineKeyboardButton("🔕 Barchasini oʻchirish", callback_data="auto_disable_all"),
        InlineKeyboardButton("🔄 Tekshirish", callback_data="auto_check_now"),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="notif_back")
    )
    
    await message.answer(settings_text + "\nSozlamani oʻzgartirish:", reply_markup=keyboard)

async def toggle_auto_setting(callback_query: types.CallbackQuery):
    """Avtomatik sozlamani oʻzgartirish"""
    
    setting = callback_query.data.replace("auto_toggle_", "")
    
    # Bu yerda ma'lumotlar bazasida sozlamani saqlash kerak
    # Hozircha demo versiya
    
    await callback_query.answer(f"{setting} sozlama oʻzgartirildi")
    await auto_notifications(callback_query.message)

async def check_notifications_now(message: types.Message):
    """Bildirishnomalarni darhol tekshirish"""
    
    await message.answer("🔍 Bildirishnomalar tekshirilmoqda...")
    
    try:
        # 1. Xom ashyo tekshiruvi
        low_stock_count = await check_low_stock_notifications()
        
        # 2. Ishlab chiqarish tekshiruvi
        production_count = await check_production_notifications()
        
        # 3. Tizim ogohlantirishlari
        system_count = await check_system_notifications()
        
        total_count = low_stock_count + production_count + system_count
        
        await message.answer(
            f"✅ **Bildirishnomalar tekshirildi!**\n\n"
            f"📊 **Natijalar:**\n"
            f"├ 📦 Xom ashyo: {low_stock_count} ta\n"
            f"├ 🏭 Ishlab chiqarish: {production_count} ta\n"
            f"├ ⚙️ Tizim: {system_count} ta\n"
            f"└ 📈 Jami: {total_count} ta\n\n"
            f"🔔 Yangi bildirishnomalar yaratildi va yuborilmoqda.",
            parse_mode="Markdown"
        )
    
    except Exception as e:
        logger.error(f"Error checking notifications: {e}")
        await message.answer(f"❌ Tekshirishda xatolik: {str(e)}")

# =============== NOTIFICATION STATISTICS ===============
async def notification_statistics(message: types.Message):
    """Bildirishnomalar statistikasi"""
    
    with get_db_session() as db:
        # Umumiy statistika
        total_count = db.query(models.Notification).count()
        
        # Status bo'yicha
        pending_count = db.query(models.Notification).filter(
            models.Notification.status == models.NotificationStatus.PENDING
        ).count()
        
        sent_count = db.query(models.Notification).filter(
            models.Notification.status == models.NotificationStatus.SENT
        ).count()
        
        read_count = db.query(models.Notification).filter(
            models.Notification.status == models.NotificationStatus.READ
        ).count()
        
        failed_count = db.query(models.Notification).filter(
            models.Notification.status == models.NotificationStatus.FAILED
        ).count()
        
        # Tur bo'yicha
        type_stats = {}
        notifications = db.query(models.Notification).all()
        
        for notif in notifications:
            if notif.notification_type not in type_stats:
                type_stats[notif.notification_type] = 0
            type_stats[notif.notification_type] += 1
        
        # Oxirgi 7 kun
        week_ago = datetime.utcnow() - timedelta(days=7)
        weekly_count = db.query(models.Notification).filter(
            models.Notification.created_at >= week_ago
        ).count()
        
        # Bugungi
        today = datetime.utcnow().date()
        today_count = db.query(models.Notification).filter(
            models.Notification.created_at >= today
        ).count()
    
    stats_text = f"""
📊 **BILDIRISHNOMALAR STATISTIKASI**

📈 **Umumiy:**
├ Jami: {total_count} ta
├ Bugungi: {today_count} ta
└ Haftalik: {weekly_count} ta

📊 **Holat boʻyicha:**
├ ⏳ Kutilayotgan: {pending_count} ta
├ 📨 Yuborilgan: {sent_count} ta
├ ✅ Oʻqilgan: {read_count} ta
└ ❌ Xatolik: {failed_count} ta

🔤 **Tur boʻyicha:**
"""
    
    for notif_type, count in type_stats.items():
        type_name = NOTIFICATION_TYPES.get(notif_type, notif_type)
        percentage = (count / total_count * 100) if total_count > 0 else 0
        stats_text += f"├ {type_name}: {count} ta ({percentage:.1f}%)\n"
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📈 Grafik", callback_data="notif_stats_chart"),
        InlineKeyboardButton("📋 Excel hisobot", callback_data="notif_stats_excel"),
        InlineKeyboardButton("🔄 Yangilash", callback_data="notif_stats_refresh"),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="notif_back")
    )
    
    await message.answer(stats_text, parse_mode="Markdown", reply_markup=keyboard)

# =============== MY NOTIFICATIONS ===============
async def my_notifications(message: types.Message):
    """Foydalanuvchining bildirishnomalari"""
    
    with get_db_session() as db:
        # Foydalanuvchini aniqlash
        employee = db.query(models.Employee).filter(
            models.Employee.telegram_id == message.from_user.id
        ).first()
        
        if not employee:
            await message.answer("❌ Siz xodim sifatida roʻyxatdan oʻtmagansiz.")
            return
        
        # Foydalanuvchiga tegishli bildirishnomalarni olish
        notifications = db.query(models.Notification).filter(
            or_(
                models.Notification.recipient_id == 0,  # Hammaga
                models.Notification.recipient_id == -1,  # Adminlarga (agar admin boʻlsa)
                models.Notification.recipient_id == employee.id,  # Shaxsiy
                # Boʻlim bildirishnomalari
                and_(
                    models.Notification.recipient_id < 0,
                    models.Notification.recipient_id != -1,
                    models.Employee.department == {
                        -2: "Ishlab chiqarish",
                        -3: "Ombor", 
                        -4: "Buxgalteriya"
                    }.get(models.Notification.recipient_id)
                )
            )
        ).order_by(models.Notification.created_at.desc()).limit(10).all()
    
    if not notifications:
        await message.answer("📭 Sizda yangi bildirishnomalar yoʻq.")
        return
    
    my_notifs_text = "📨 **MENING BILDIRISHNOMALARIM**\n\n"
    
    for idx, notif in enumerate(notifications, 1):
        # Oʻqilganligini tekshirish
        read_icon = "✅ " if notif.read_time else "🆕 "
        
        # Vaqtni formatlash
        time_str = notif.created_at.strftime("%m-%d %H:%M")
        
        my_notifs_text += (
            f"{idx}. {read_icon}**{notif.title}**\n"
            f"   📅 {time_str} | {NOTIFICATION_TYPES.get(notif.notification_type, 'Bildirishnoma')}\n"
            f"   📝 {notif.message[:80]}...\n\n"
        )
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📖 Barchasini koʻrish", callback_data="my_notifs_all"),
        InlineKeyboardButton("✅ Barchasini oʻqildi deb belgilash", callback_data="my_notifs_mark_read"),
        InlineKeyboardButton("🗑️ Barchasini oʻchirish", callback_data="my_notifs_clear"),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="notif_back")
    )
    
    await message.answer(my_notifs_text, parse_mode="Markdown", reply_markup=keyboard)

async def mark_as_read(callback_query: types.CallbackQuery):
    """Bildirishnomani oʻqildi deb belgilash"""
    
    await callback_query.answer("✅ Barcha bildirishnomalar oʻqildi deb belgilandi")
    
    with get_db_session() as db:
        # Foydalanuvchining barcha bildirishnomalarini topish
        notifications = db.query(models.Notification).filter(
            models.Notification.status == models.NotificationStatus.SENT,
            models.Notification.read_time.is_(None)
        ).all()
        
        for notif in notifications:
            notif.status = models.NotificationStatus.READ
            notif.read_time = datetime.utcnow()
        
        db.commit()
    
    await callback_query.message.answer("✅ Barcha bildirishnomalar oʻqildi deb belgilandi.")

# =============== CALLBACK HANDLERS ===============
async def notification_callback_handler(callback_query: types.CallbackQuery, state: FSMContext):
    """Notification callback handler"""
    
    data = callback_query.data
    
    if data == "notif_back":
        await callback_query.answer()
        await notifications_menu(callback_query.message)
        await state.finish()
        return
    
    elif data.startswith("type_"):
        await process_notification_type(callback_query, state)
    
    elif data.startswith("recipient_"):
        await process_notification_recipient(callback_query, state)
    
    elif data.startswith("priority_"):
        await process_notification_priority(callback_query, state)
    
    elif data.startswith("schedule_"):
        await process_notification_schedule(callback_query, state)
    
    elif data.startswith("confirm_notif_"):
        await save_notification(callback_query, state)
    
    elif data.startswith("view_"):
        await view_notification_details(callback_query)
    
    elif data.startswith("auto_"):
        if data.startswith("auto_toggle_"):
            await toggle_auto_setting(callback_query)
        elif data == "auto_check_now":
            await check_notifications_now(callback_query.message)
        elif data == "auto_enable_all":
            await callback_query.answer("Barcha avtomatik bildirishnomalar yoqildi")
        elif data == "auto_disable_all":
            await callback_query.answer("Barcha avtomatik bildirishnomalar oʻchirildi")
    
    elif data.startswith("notif_stats"):
        if data == "notif_stats":
            await notification_statistics(callback_query.message)
        elif data == "notif_stats_chart":
            await generate_notification_chart(callback_query.message)
        elif data == "notif_stats_excel":
            await generate_notification_excel(callback_query.message)
    
    elif data.startswith("my_notifs"):
        if data == "my_notifs_mark_read":
            await mark_as_read(callback_query)
        elif data == "my_notifs_all":
            await view_all_my_notifications(callback_query.message)
        elif data == "my_notifs_clear":
            await clear_my_notifications(callback_query.message)
    
    else:
        await callback_query.answer("⚠️ Bu funksiya hozircha ishlamaydi", show_alert=True)

# =============== YORDAMCHI FUNKSIYALAR ===============
async def generate_notification_chart(message: types.Message):
    """Bildirishnomalar grafigi"""
    
    await message.answer("📈 Bildirishnomalar grafigi tayyorlanmoqda...")
    
    # Bu yerda grafik yaratish kodi boʻlishi kerak
    # Hozircha demo
    
    await message.answer("⚠️ Bu funksiya hozircha ishlamaydi. Tez orada tayyor boʻladi.")

async def generate_notification_excel(message: types.Message):
    """Bildirishnomalar Excel hisoboti"""
    
    with get_db_session() as db:
        notifications = db.query(models.Notification).all()
        
        notif_data = []
        for notif in notifications:
            notif_data.append({
                'ID': notif.id,
                'Tur': NOTIFICATION_TYPES.get(notif.notification_type, notif.notification_type),
                'Sarlavha': notif.title,
                'Matn': notif.message,
                'Qabul qiluvchi': get_recipient_name(notif.recipient_id),
                'Ustuvorlik': notif.priority,
                'Holat': notif.status.value,
                'Yaratilgan': notif.created_at.strftime('%Y-%m-%d %H:%M'),
                'Yuborilgan': notif.sent_time.strftime('%Y-%m-%d %H:%M') if notif.sent_time else '',
                'Oʻqilgan': notif.read_time.strftime('%Y-%m-%d %H:%M') if notif.read_time else ''
            })
    
    import pandas as pd
    from datetime import datetime
    
    df = pd.DataFrame(notif_data)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"bildirishnomalar_{timestamp}.xlsx"
    filepath = f"reports/excel/{filename}"
    
    df.to_excel(filepath, index=False)
    
    await message.answer_document(
        document=types.InputFile(filepath),
        caption=f"📋 Bildirishnomalar hisoboti ({len(notifications)} ta)"
    )

async def view_all_my_notifications(message: types.Message):
    """Barcha shaxsiy bildirishnomalarni koʻrish"""
    
    await message.answer("📋 Barcha shaxsiy bildirishnomalaringiz tayyorlanmoqda...")
    # Toʻliq implementatsiya kerak

async def clear_my_notifications(message: types.Message):
    """Shaxsiy bildirishnomalarni tozalash"""
    
    await message.answer("🗑️ Shaxsiy bildirishnomalaringiz tozalanmoqda...")
    # Toʻliq implementatsiya kerak

# =============== BACKGROUND TASKS ===============
async def background_notification_checker():
    """Fon bildirishnoma tekshiruvchi"""
    
    while True:
        try:
            await asyncio.sleep(300)  # Har 5 daqiqa
            
            with get_db_session() as db:
                # Vaqti oʻtgan bildirishnomalarni yuborish
                pending_notifs = db.query(models.Notification).filter(
                    models.Notification.status == models.NotificationStatus.PENDING,
                    or_(
                        models.Notification.scheduled_time.is_(None),
                        models.Notification.scheduled_time <= datetime.utcnow()
                    )
                ).all()
                
                for notif in pending_notifs:
                    await send_notification_now(notif.id)
        
        except Exception as e:
            logger.error(f"Background notification error: {e}")

# =============== REGISTER HANDLERS ===============
def register_handlers_notifications(dp: Dispatcher):
    """Notification handlers ni roʻyxatdan oʻtkazish"""
    
    # Notifications menu
    dp.register_message_handler(notifications_menu, 
                               lambda msg: msg.text == "🔔 Bildirishnomalar", 
                               state="*")
    
    # Create notification
    dp.register_message_handler(create_notification_start, 
                               lambda msg: msg.text == "📝 Yangi bildirishnoma", 
                               state="*")
    
    # View notifications
    dp.register_message_handler(view_notifications, 
                               lambda msg: msg.text == "📋 Barcha bildirishnomalar", 
                               state="*")
    
    # Auto notifications
    dp.register_message_handler(auto_notifications, 
                               lambda msg: msg.text == "⚙️ Avtomatik bildirishnomalar", 
                               state="*")
    
    # Statistics
    dp.register_message_handler(notification_statistics, 
                               lambda msg: msg.text == "📊 Bildirishnomalar statistika", 
                               state="*")
    
    # My notifications
    dp.register_message_handler(my_notifications, 
                               lambda msg: msg.text == "📨 Mening bildirishnomalarim", 
                               state="*")
    
    # Check now
    dp.register_message_handler(check_notifications_now, 
                               lambda msg: msg.text == "🔄 Darhol tekshirish", 
                               state="*")
    
    # State handlers
    dp.register_message_handler(process_notification_title, state=NotificationStates.waiting_notification_title)
    dp.register_message_handler(process_notification_message, state=NotificationStates.waiting_notification_message)
    dp.register_message_handler(process_schedule_time, state=NotificationStates.waiting_notification_schedule)
    
    # Callback handlers
    dp.register_callback_query_handler(notification_callback_handler,
                                      lambda c: c.data.startswith('notif_') or 
                                               c.data.startswith('type_') or
                                               c.data.startswith('recipient_') or
                                               c.data.startswith('priority_') or
                                               c.data.startswith('schedule_') or
                                               c.data.startswith('confirm_notif_') or
                                               c.data.startswith('view_') or
                                               c.data.startswith('auto_') or
                                               c.data.startswith('my_notifs_'),
                                      state="*")
    
    # Background task
    from main import bot
    asyncio.create_task(background_notification_checker())