"""
Push Notifications System - Qurilish Korxonasi Push Bildirishnoma Tizimi
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import asyncio

from aiogram import Bot
from aiogram.types import ParseMode
from sqlalchemy.orm import Session

from database.session import get_db_session
from database import crud, models
from config import ADMIN_IDS, NOTIFICATION_TYPES

logger = logging.getLogger(__name__)

# Global bot instance (main.py dan set qilinadi)
bot_instance: Optional[Bot] = None

def set_bot_instance(bot: Bot):
    """Bot instance ni o'rnatish"""
    global bot_instance
    bot_instance = bot

# =============== BASIC NOTIFICATION FUNCTIONS ===============
async def send_notification_to_user(user_id: int, title: str, message: str, 
                                   notification_type: str = "system_alert") -> bool:
    """
    Foydalanuvchiga push bildirishnoma yuborish
    
    Args:
        user_id: Telegram user ID
        title: Bildirishnoma sarlavhasi
        message: Bildirishnoma matni
        notification_type: Bildirishnoma turi
    
    Returns:
        bool: Muvaffaqiyatli yuborilgan bo'lsa True
    """
    
    if not bot_instance:
        logger.error("Bot instance not set!")
        return False
    
    try:
        # Formatlash
        formatted_message = f"🔔 *{title}*\n\n{message}"
        
        await bot_instance.send_message(
            chat_id=user_id,
            text=formatted_message,
            parse_mode=ParseMode.MARKDOWN
        )
        
        logger.info(f"Notification sent to user {user_id}: {title}")
        
        # Database ga yozish
        with get_db_session() as db:
            crud.create_notification(db, {
                'notification_type': notification_type,
                'title': title,
                'message': message,
                'recipient_id': user_id,
                'status': models.NotificationStatus.SENT,
                'sent_time': datetime.utcnow()
            })
        
        return True
    
    except Exception as e:
        logger.error(f"Error sending notification to user {user_id}: {e}")
        
        # Xatolikni database ga yozish
        with get_db_session() as db:
            crud.create_notification(db, {
                'notification_type': notification_type,
                'title': title,
                'message': message,
                'recipient_id': user_id,
                'status': models.NotificationStatus.FAILED,
                'sent_time': datetime.utcnow(),
                'metadata': {'error': str(e)}
            })
        
        return False

async def send_notification_to_all(title: str, message: str, 
                                  notification_type: str = "system_alert") -> Dict[str, int]:
    """
    Barcha foydalanuvchilarga push bildirishnoma yuborish
    
    Args:
        title: Bildirishnoma sarlavhasi
        message: Bildirishnoma matni
        notification_type: Bildirishnoma turi
    
    Returns:
        Dict: Natijalar statistikasi
    """
    
    if not bot_instance:
        logger.error("Bot instance not set!")
        return {'success': 0, 'failed': 0, 'total': 0}
    
    with get_db_session() as db:
        # Barcha aktiv xodimlarni olish
        employees = db.query(models.Employee).filter(
            models.Employee.telegram_id.isnot(None),
            models.Employee.status == models.EmployeeStatus.ACTIVE
        ).all()
    
    total = len(employees)
    success = 0
    failed = 0
    
    await bot_instance.send_message(
        chat_id=ADMIN_IDS[0] if ADMIN_IDS else 0,
        text=f"📢 *Ommaviy bildirishnoma boshlanmoqda...*\n\n"
             f"*Sarlavha:* {title}\n"
             f"*Qabul qiluvchilar:* {total} ta",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Har bir xodimga yuborish
    for employee in employees:
        try:
            await send_notification_to_user(
                employee.telegram_id,
                title,
                message,
                notification_type
            )
            success += 1
            
            # Har 10 ta yuborilganda progressni ko'rsatish
            if success % 10 == 0:
                progress = (success / total) * 100
                await bot_instance.send_message(
                    chat_id=ADMIN_IDS[0] if ADMIN_IDS else 0,
                    text=f"📊 *Progress:* {success}/{total} ({progress:.1f}%)",
                    parse_mode=ParseMode.MARKDOWN
                )
            
        except Exception as e:
            logger.error(f"Error sending to employee {employee.id}: {e}")
            failed += 1
        
        # To avoid flooding
        await asyncio.sleep(0.1)
    
    # Natijalarni adminlarga yuborish
    result_message = (
        f"✅ *Ommaviy bildirishnoma yakunlandi!*\n\n"
        f"📊 *Natijalar:*\n"
        f"• ✅ Muvaffaqiyatli: {success} ta\n"
        f"• ❌ Xatolik: {failed} ta\n"
        f"• 📈 Jami: {total} ta\n\n"
        f"🎯 *Muvaffaqiyat darajasi:* {(success/total*100) if total > 0 else 0:.1f}%"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await bot_instance.send_message(
                chat_id=admin_id,
                text=result_message,
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
    
    return {'success': success, 'failed': failed, 'total': total}

async def send_notification_to_admins(title: str, message: str, 
                                     notification_type: str = "system_alert") -> bool:
    """
    Barcha adminlarga push bildirishnoma yuborish
    
    Args:
        title: Bildirishnoma sarlavhasi
        message: Bildirishnoma matni
        notification_type: Bildirishnoma turi
    
    Returns:
        bool: Muvaffaqiyatli yuborilgan bo'lsa True
    """
    
    if not bot_instance:
        logger.error("Bot instance not set!")
        return False
    
    with get_db_session() as db:
        # Barcha admin xodimlarni olish
        admins = db.query(models.Employee).filter(
            models.Employee.is_admin == True,
            models.Employee.telegram_id.isnot(None),
            models.Employee.status == models.EmployeeStatus.ACTIVE
        ).all()
    
    success_count = 0
    
    for admin in admins:
        try:
            await send_notification_to_user(
                admin.telegram_id, # type: ignore
                title,
                message,
                notification_type
            )
            success_count += 1
        except Exception as e:
            logger.error(f"Error sending to admin {admin.id}: {e}")
    
    return success_count > 0

async def send_notification_to_department(department: str, title: str, message: str,
                                         notification_type: str = "system_alert") -> Dict[str, int]:
    """
    Ma'lum bo'limdagi barcha xodimlarga push bildirishnoma yuborish
    
    Args:
        department: Bo'lim nomi
        title: Bildirishnoma sarlavhasi
        message: Bildirishnoma matni
        notification_type: Bildirishnoma turi
    
    Returns:
        Dict: Natijalar statistikasi
    """
    
    if not bot_instance:
        logger.error("Bot instance not set!")
        return {'success': 0, 'failed': 0, 'total': 0}
    
    with get_db_session() as db:
        # Bo'limdagi barcha xodimlarni olish
        employees = db.query(models.Employee).filter(
            models.Employee.department == department,
            models.Employee.telegram_id.isnot(None),
            models.Employee.status == models.EmployeeStatus.ACTIVE
        ).all()
    
    total = len(employees)
    success = 0
    failed = 0
    
    for employee in employees:
        try:
            await send_notification_to_user(
                employee.telegram_id,
                title,
                message,
                notification_type
            )
            success += 1
        except Exception as e:
            logger.error(f"Error sending to employee {employee.id}: {e}")
            failed += 1
    
    return {'success': success, 'failed': failed, 'total': total}

# =============== AUTOMATED NOTIFICATION CHECKS ===============
async def check_low_stock_notifications() -> int:
    """
    Yetarli bo'lmagan xom ashyolar uchun bildirishnoma yuborish
    
    Returns:
        int: Yuborilgan bildirishnomalar soni
    """
    
    with get_db_session() as db:
        # Yetarli bo'lmagan xom ashyolarni topish
        low_stock_materials = crud.check_low_stock_materials(db)
        
        if not low_stock_materials:
            return 0
        
        notification_count = 0
        
        for material in low_stock_materials:
            # Har bir material uchun alohida bildirishnoma
            title = f"⚠️ Xom ashyo tugab qolmoqda: {material.name}"
            message = (
                f"*{material.name}* xom ashyosi tugab qolmoqda!\n\n"
                f"📊 *Joriy qoldiq:* {material.current_stock} {material.unit}\n"
                f"📉 *Minimal qoldiq:* {material.min_stock} {material.unit}\n"
                f"💰 *Narxi:* {material.price_per_unit:,.0f} so'm/{material.unit}\n\n"
                f"🚨 *Zarur amallar:*\n"
                f"1. Yangi xom ashyo buyurtma qiling\n"
                f"2. Ishlab chiqarishni rejalashtiring\n"
                f"3. Boshqa materiallarni tekshiring"
            )
            
            # Adminlarga yuborish
            await send_notification_to_admins(title, message, "low_stock")
            
            # Ombor bo'limiga yuborish
            await send_notification_to_department("Ombor", title, message, "low_stock")
            
            notification_count += 1
        
        # Umumiy xabar
        if len(low_stock_materials) > 3:
            total_title = f"⚠️ {len(low_stock_materials)} ta xom ashyo tugab qolmoqda"
            total_message = (
                f"Diqqat! {len(low_stock_materials)} ta xom ashyo tugab qolmoqda:\n\n"
            )
            
            for material in low_stock_materials[:5]:  # Faqat 5 tasini ko'rsatish
                total_message += f"• {material.name}: {material.current_stock}/{material.min_stock} {material.unit}\n"
            
            if len(low_stock_materials) > 5:
                total_message += f"\n... va yana {len(low_stock_materials) - 5} ta\n"
            
            total_message += "\n🔄 Tez orada to'ldirishni rejalashtiring!"
            
            await send_notification_to_admins(total_title, total_message, "low_stock")
        
        return notification_count

async def check_production_notifications() -> int:
    """
    Ishlab chiqarish jarayonlari uchun bildirishnoma yuborish
    
    Returns:
        int: Yuborilgan bildirishnomalar soni
    """
    
    with get_db_session() as db:
        # 1. Jarayondagi buyurtmalarni tekshirish
        in_progress_orders = db.query(models.ProductionOrder).filter(
            models.ProductionOrder.status == models.OrderStatus.IN_PROGRESS
        ).all()
        
        # 2. Rejalashtirilgan vaqt o'tgan buyurtmalar
        overdue_orders = db.query(models.ProductionOrder).filter(
            models.ProductionOrder.status == models.OrderStatus.IN_PROGRESS,
            models.ProductionOrder.planned_end < datetime.utcnow()
        ).all()
        
        # 3. Bugun tugashi kerak bo'lgan buyurtmalar
        today = datetime.utcnow().date()
        tomorrow = today + timedelta(days=1)
        
        due_today_orders = db.query(models.ProductionOrder).filter(
            models.ProductionOrder.status == models.OrderStatus.IN_PROGRESS,
            models.ProductionOrder.planned_end >= today,
            models.ProductionOrder.planned_end < tomorrow
        ).all()
        
        notification_count = 0
        
        # Overdue buyurtmalar uchun
        if overdue_orders:
            title = f"⏰ {len(overdue_orders)} ta buyurtma vaqti o'tdi"
            message = f"Diqqat! {len(overdue_orders)} ta ishlab chiqarish buyurtmasi vaqti o'tdi:\n\n"
            
            for order in overdue_orders[:3]:
                message += (
                    f"• #{order.order_number} - {order.product.name}\n"
                    f"  Miqdor: {order.quantity} {order.product.unit}\n"
                    f"  Rejalashtirilgan: {order.planned_end.strftime('%Y-%m-%d')}\n\n"
                )
            
            if len(overdue_orders) > 3:
                message += f"... va yana {len(overdue_orders) - 3} ta\n\n"
            
            message += "🚨 Darhol chora ko'ring!"
            
            await send_notification_to_department("Ishlab chiqarish", title, message, "production_complete")
            await send_notification_to_admins(title, message, "production_complete")
            
            notification_count += 1
        
        # Bugun tugashi kerak bo'lganlar uchun
        if due_today_orders:
            title = f"📅 Bugun {len(due_today_orders)} ta buyurtma tugashi kerak"
            message = f"Eslatma! Bugun {len(due_today_orders)} ta ishlab chiqarish buyurtmasi tugashi kerak:\n\n"
            
            for order in due_today_orders[:3]:
                hours_left = (order.planned_end - datetime.utcnow()).total_seconds() / 3600
                message += (
                    f"• #{order.order_number} - {order.product.name}\n"
                    f"  Miqdor: {order.quantity} {order.product.unit}\n"
                    f"  Qolgan vaqt: {hours_left:.1f} soat\n\n"
                )
            
            if len(due_today_orders) > 3:
                message += f"... va yana {len(due_today_orders) - 3} ta\n\n"
            
            message += "⏱️ Vaqtni samarali boshqaring!"
            
            await send_notification_to_department("Ishlab chiqarish", title, message, "production_complete")
            
            notification_count += 1
        
        return notification_count

async def check_system_notifications() -> int:
    """
    Tizim ogohlantirishlari uchun bildirishnoma yuborish
    
    Returns:
        int: Yuborilgan bildirishnomalar soni
    """
    
    with get_db_session() as db:
        notification_count = 0
        
        # 1. Database hajmini tekshirish
        # (Bu PostgreSQL uchun, SQLite uchun boshqa query)
        
        # 2. Xatolik loglarini tekshirish
        error_logs = db.query(models.SystemLog).filter(
            models.SystemLog.created_at >= datetime.utcnow() - timedelta(hours=24)
        ).all()
        
        error_count = len([log for log in error_logs if "error" in log.action.lower() or "xatolik" in log.action.lower()])
        
        if error_count > 10:
            title = f"🚨 {error_count} ta xatolik aniqlandi (24 soat)"
            message = (
                f"Tizimda 24 soat ichida {error_count} ta xatolik aniqlandi.\n\n"
                f"📊 *Statistika:*\n"
                f"• Jami loglar: {len(error_logs)} ta\n"
                f"• Xatoliklar: {error_count} ta\n"
                f"• Xatolik foizi: {(error_count/len(error_logs)*100) if error_logs else 0:.1f}%\n\n"
                f"🔍 *Tavsiyalar:*\n"
                "1. Tizim loglarini tekshiring\n"
                "2. Muammoni bartaraf eting\n"
                "3. Foydalanuvchilarni xabardor qiling"
            )
            
            await send_notification_to_admins(title, message, "system_alert")
            notification_count += 1
        
        # 3. Faollik darajasini tekshirish
        active_users = db.query(models.SystemLog.user_id).filter(
            models.SystemLog.created_at >= datetime.utcnow() - timedelta(hours=24)
        ).distinct().count()
        
        total_users = db.query(models.Employee).filter(
            models.Employee.status == models.EmployeeStatus.ACTIVE
        ).count()
        
        activity_rate = (active_users / total_users * 100) if total_users > 0 else 0
        
        if activity_rate < 30 and total_users > 5:
            title = f"📉 Faollik darajasi past: {activity_rate:.1f}%"
            message = (
                f"Tizim faollik darajasi past ko'rsatkichga tushdi.\n\n"
                f"📊 *Statistika:*\n"
                f"• Faol foydalanuvchilar: {active_users} ta\n"
                f"• Jami foydalanuvchilar: {total_users} ta\n"
                f"• Faollik darajasi: {activity_rate:.1f}%\n\n"
                f"🎯 *Tavsiyalar:*\n"
                "1. Xodimlarni tizimdan foydalanishga rag'batlantiring\n"
                "2. Treninglar o'tkazing\n"
                "3. Tizimning qulayligini oshiring"
            )
            
            await send_notification_to_admins(title, message, "system_alert")
            notification_count += 1
        
        return notification_count

async def check_salary_notifications() -> int:
    """
    Maosh to'lovlari uchun bildirishnoma yuborish
    
    Returns:
        int: Yuborilgan bildirishnomalar soni
    """
    
    today = datetime.utcnow().date()
    current_month = today.month
    current_year = today.year
    
    with get_db_session() as db:
        notification_count = 0
        
        # 1. Bu oy uchun to'lanmagan maoshlar
        unpaid_salaries = db.query(models.SalaryPayment).filter(
            models.SalaryPayment.month == current_month,
            models.SalaryPayment.year == current_year,
            models.SalaryPayment.status != "paid"
        ).all()
        
        if unpaid_salaries:
            title = f"💰 {len(unpaid_salaries)} ta maosh to'lanmagan"
            message = f"Diqqat! {current_month}/{current_year} oyi uchun {len(unpaid_salaries)} ta maosh to'lanmagan:\n\n"
            
            total_amount = sum([salary.total_amount for salary in unpaid_salaries])
            
            for salary in unpaid_salaries[:3]:
                employee = db.query(models.Employee).filter(
                    models.Employee.id == salary.employee_id
                ).first()
                
                if employee:
                    message += (
                        f"• {employee.full_name}\n"
                        f"  Miqdor: {salary.total_amount:,.0f} so'm\n"
                        f"  Holat: {salary.status}\n\n"
                    )
            
            if len(unpaid_salaries) > 3:
                message += f"... va yana {len(unpaid_salaries) - 3} ta\n\n"
            
            message += f"💰 Jami to'lanmagan summa: {total_amount:,.0f} so'm\n\n"
            message += "🏦 Darhol to'lashni rejalashtiring!"
            
            await send_notification_to_admins(title, message, "salary_payment")
            await send_notification_to_department("Buxgalteriya", title, message, "salary_payment")
            
            notification_count += 1
        
        # 2. Keyingi 3 kunda maosh to'lash kuni
        salary_day = 5  # Har oyning 5-kuni maosh kuni deb hisoblaymiz
        
        if today.day >= salary_day - 3 and today.day < salary_day:
            days_left = salary_day - today.day
            
            title = f"⏰ Maosh to'lash kuni yaqin: {days_left} kun qoldi"
            message = (
                f"Eslatma! Maosh to'lash kuni yaqinlashmoqda.\n\n"
                f"📅 *Maosh kuni:* {salary_day}-{current_month}-{current_year}\n"
                f"⏰ *Qolgan vaqt:* {days_left} kun\n\n"
                f"📋 *Tayyorgarlik ko'rish kerak:*\n"
                "1. Xodimlar ro'yxatini tekshiring\n"
                "2. Mablag'ni tayyorlang\n"
                "3. Bank operatsiyalari uchun vaqt ajrating\n"
                "4. Hujjatlarni tayyorlang"
            )
            
            await send_notification_to_admins(title, message, "salary_payment")
            await send_notification_to_department("Buxgalteriya", title, message, "salary_payment")
            
            notification_count += 1
        
        return notification_count

async def check_delivery_notifications() -> int:
    """
    Yetkazib berishlar uchun bildirishnoma yuborish
    
    Returns:
        int: Yuborilgan bildirishnomalar soni
    """
    
    with get_db_session() as db:
        notification_count = 0
        
        # Bugun yetkazib berilishi kerak bo'lgan buyurtmalar
        today = datetime.utcnow().date()
        
        deliveries_today = db.query(models.Sale).filter(
            models.Sale.status == "pending",
            func.date(models.Sale.sale_date) == today
        ).all()
        
        if deliveries_today:
            title = f"🚚 Bugun {len(deliveries_today)} ta yetkazib berish kerak"
            message = f"Bugun {len(deliveries_today)} ta mahsulot yetkazib berilishi kerak:\n\n"
            
            total_amount = sum([sale.total_amount for sale in deliveries_today])
            
            for sale in deliveries_today[:3]:
                product = db.query(models.Product).filter(
                    models.Product.id == sale.product_id
                ).first()
                
                if product:
                    message += (
                        f"• {sale.customer_name}\n"
                        f"  Mahsulot: {product.name}\n"
                        f"  Miqdor: {sale.quantity} {product.unit}\n"
                        f"  Narx: {sale.total_amount:,.0f} so'm\n\n"
                    )
            
            if len(deliveries_today) > 3:
                message += f"... va yana {len(deliveries_today) - 3} ta\n\n"
            
            message += f"💰 Jami summa: {total_amount:,.0f} so'm\n\n"
            message += "📦 Yetkazib berishni rejalashtiring!"
            
            await send_notification_to_department("Logistika", title, message, "order_delivered")
            await send_notification_to_admins(title, message, "order_delivered")
            
            notification_count += 1
        
        return notification_count

# =============== SCHEDULED NOTIFICATIONS ===============
async def send_daily_report() -> bool:
    """
    Kundalik hisobotni push bildirishnoma sifatida yuborish
    
    Returns:
        bool: Muvaffaqiyatli yuborilgan bo'lsa True
    """
    
    yesterday = datetime.utcnow().date() - timedelta(days=1)
    
    with get_db_session() as db:
        # Kunlik statistikani hisoblash
        daily_sales = db.query(models.Sale).filter(
            func.date(models.Sale.sale_date) == yesterday
        ).all()
        
        daily_orders = db.query(models.ProductionOrder).filter(
            func.date(models.ProductionOrder.created_at) == yesterday
        ).all()
        
        daily_transactions = db.query(models.WarehouseTransaction).filter(
            func.date(models.WarehouseTransaction.date) == yesterday
        ).all()
        
        # Hisobot tayyorlash
        title = f"📊 Kundalik hisobot: {yesterday.strftime('%Y-%m-%d')}"
        
        message = (
            f"📅 *Sana:* {yesterday.strftime('%Y-%m-%d')}\n\n"
            
            f"💰 *Sotuvlar:*\n"
            f"• Jami sotuvlar: {len(daily_sales)} ta\n"
            f"• Daromad: {sum([s.total_amount for s in daily_sales]):,.0f} so'm\n\n"
            
            f"🏭 *Ishlab chiqarish:*\n"
            f"• Yangi buyurtmalar: {len(daily_orders)} ta\n"
            f"• Jami miqdor: {sum([o.quantity for o in daily_orders])} birlik\n\n"
            
            f"📦 *Ombor harakatlari:*\n"
            f"• Jami harakatlar: {len(daily_transactions)} ta\n"
            f"• Kirimlar: {len([t for t in daily_transactions if t.transaction_type.value == 'kirim'])} ta\n"
            f"• Chiqimlar: {len([t for t in daily_transactions if t.transaction_type.value == 'chiqim'])} ta\n\n"
        )
        
        # Xom ashyo holati
        low_stock_count = db.query(models.RawMaterial).filter(
            models.RawMaterial.current_stock <= models.RawMaterial.min_stock
        ).count()
        
        if low_stock_count > 0:
            message += f"⚠️ *Ogohlantirish:* {low_stock_count} ta xom ashyo tugab qolmoqda!\n\n"
        
        message += "📈 Batafsil hisobotlar uchun botdan foydalaning."
    
    # Adminlarga yuborish
    return await send_notification_to_admins(title, message, "system_alert")

async def send_weekly_report() -> bool:
    """
    Haftalik hisobotni push bildirishnoma sifatida yuborish
    
    Returns:
        bool: Muvaffaqiyatli yuborilgan bo'lsa True
    """
    
    week_ago = datetime.utcnow().date() - timedelta(days=7)
    
    with get_db_session() as db:
        # Haftalik statistikani hisoblash
        weekly_sales = db.query(models.Sale).filter(
            models.Sale.sale_date >= week_ago
        ).all()
        
        weekly_orders = db.query(models.ProductionOrder).filter(
            models.ProductionOrder.created_at >= week_ago
        ).all()
        
        # Hisobot tayyorlash
        title = f"📈 Haftalik hisobot: {week_ago.strftime('%Y-%m-%d')} - {datetime.utcnow().date().strftime('%Y-%m-%d')}"
        
        total_sales_amount = sum([s.total_amount for s in weekly_sales])
        total_production_cost = sum([o.total_cost or 0 for o in weekly_orders])
        total_profit = total_sales_amount - total_production_cost
        
        message = (
            f"📅 *Davr:* {week_ago.strftime('%Y-%m-%d')} - {datetime.utcnow().date().strftime('%Y-%m-%d')}\n\n"
            
            f"💰 *Moliya ko'rsatkichlari:*\n"
            f"• Sotuv daromadi: {total_sales_amount:,.0f} so'm\n"
            f"• Ishlab chiqarish xarajati: {total_production_cost:,.0f} so'm\n"
            f"• Sof foyda: {total_profit:,.0f} so'm\n"
            f"• Foyda marjasi: {(total_profit/total_sales_amount*100) if total_sales_amount > 0 else 0:.1f}%\n\n"
            
            f"📊 *Faollik ko'rsatkichlari:*\n"
            f"• Sotuvlar soni: {len(weekly_sales)} ta\n"
            f"• Buyurtmalar soni: {len(weekly_orders)} ta\n"
            f"• O'rtacha kunlik sotuv: {len(weekly_sales)/7:.1f} ta\n\n"
        )
        
        # Eng ko'p sotilgan mahsulotlar
        from sqlalchemy import func
        
        top_products = db.query(
            models.Product.name,
            func.sum(models.Sale.quantity).label('total_sold')
        ).join(models.Sale).filter(
            models.Sale.sale_date >= week_ago
        ).group_by(models.Product.id).order_by(
            func.sum(models.Sale.quantity).desc()
        ).limit(3).all()
        
        if top_products:
            message += f"🏆 *Eng ko'p sotilgan mahsulotlar:*\n"
            for product in top_products:
                message += f"• {product.name}: {product.total_sold} dona\n"
            message += "\n"
        
        message += "📈 Batafsil statistika va grafiklar uchun botdan foydalaning."
    
    # Barcha adminlarga va rahbariyatga yuborish
    await send_notification_to_admins(title, message, "system_alert")
    await send_notification_to_department("Rahbariyat", title, message, "system_alert")
    
    return True

async def send_monthly_report() -> bool:
    """
    Oylik hisobotni push bildirishnoma sifatida yuborish
    
    Returns:
        bool: Muvaffaqiyatli yuborilgan bo'lsa True
    """
    
    first_day_of_month = datetime.utcnow().replace(day=1).date()
    
    with get_db_session() as db:
        # Oylik statistikani hisoblash
        monthly_sales = db.query(models.Sale).filter(
            models.Sale.sale_date >= first_day_of_month
        ).all()
        
        monthly_orders = db.query(models.ProductionOrder).filter(
            models.ProductionOrder.created_at >= first_day_of_month
        ).all()
        
        # Hisobot tayyorlash
        title = f"📊 Oylik hisobot: {datetime.utcnow().strftime('%Y-%m')}"
        
        total_sales_amount = sum([s.total_amount for s in monthly_sales])
        total_production_cost = sum([o.total_cost or 0 for o in monthly_orders])
        total_profit = total_sales_amount - total_production_cost
        
        # Xodimlar statistikasi
        total_employees = db.query(models.Employee).filter(
            models.Employee.status == models.EmployeeStatus.ACTIVE
        ).count()
        
        total_salary_cost = db.query(func.sum(models.SalaryPayment.total_amount)).filter(
            models.SalaryPayment.month == datetime.utcnow().month,
            models.SalaryPayment.year == datetime.utcnow().year,
            models.SalaryPayment.status == "paid"
        ).scalar() or 0
        
        message = (
            f"📅 *Oy:* {datetime.utcnow().strftime('%Y-%m')}\n\n"
            
            f"💰 *Moliya ko'rsatkichlari:*\n"
            f"• Sotuv daromadi: {total_sales_amount:,.0f} so'm\n"
            f"• Ishlab chiqarish xarajati: {total_production_cost:,.0f} so'm\n"
            f"• Maosh xarajatlari: {total_salary_cost:,.0f} so'm\n"
            f"• Sof foyda: {total_profit:,.0f} so'm\n"
            f"• Foyda marjasi: {(total_profit/total_sales_amount*100) if total_sales_amount > 0 else 0:.1f}%\n\n"
            
            f"📊 *Ishlab chiqarish ko'rsatkichlari:*\n"
            f"• Sotuvlar soni: {len(monthly_sales)} ta\n"
            f"• Buyurtmalar soni: {len(monthly_orders)} ta\n"
            f"• Ishlab chiqarilgan miqdor: {sum([o.quantity for o in monthly_orders])} birlik\n\n"
            
            f"👥 *Xodimlar:*\n"
            f"• Faol xodimlar: {total_employees} kishi\n"
            f"• O'rtacha maosh: {total_salary_cost/total_employees if total_employees > 0 else 0:,.0f} so'm\n\n"
        )
        
        # Rejalashtirish
        next_month = datetime.utcnow().month + 1
        if next_month > 12:
            next_month = 1
        
        message += (
            f"🎯 *Keyingi oy uchun rejalar:*\n"
            f"1. Sotuvni {total_sales_amount * 1.1:,.0f} so'm ga oshirish\n"
            f"2. Foyda marjasini {((total_profit/total_sales_amount*100)+1) if total_sales_amount > 0 else 0:.1f}% ga oshirish\n"
            f"3. Xarajatlarni {total_production_cost * 0.95:,.0f} so'm ga kamaytirish\n\n"
            
            f"📈 Batafsil hisobot va grafiklar uchun botdan foydalaning."
        )
    
    # Barcha rahbariyat va adminlarga yuborish
    await send_notification_to_admins(title, message, "system_alert")
    await send_notification_to_department("Rahbariyat", title, message, "system_alert")
    
    return True

# =============== SPECIAL NOTIFICATIONS ===============
async def send_emergency_notification(title: str, message: str) -> Dict[str, int]:
    """
    Favqulodda vaziyatlar uchun bildirishnoma yuborish
    
    Args:
        title: Bildirishnoma sarlavhasi
        message: Bildirishnoma matni
    
    Returns:
        Dict: Natijalar statistikasi
    """
    
    emergency_message = f"🚨 *Favqulodda bildirishnoma!* 🚨\n\n{message}"
    
    # Barcha foydalanuvchilarga yuborish
    result = await send_notification_to_all(
        f"🚨 {title}",
        emergency_message,
        "system_alert"
    )
    
    # Qo'shimcha ravishda telefon orqali xabar berish (agar kerak bo'lsa)
    # Bu yerda SMS yoki telefon qo'ng'irog'i API ni qo'shishingiz mumkin
    
    return result

async def send_holiday_greetings():
    """
    Bayram tabriklari uchun bildirishnoma yuborish
    """
    
    holidays = {
        "01-01": "🎉 Yangi Yilingiz bilan!",
        "03-08": "🌸 Xalqaro Xotin-qizlar kuni bilan!",
        "03-21": "🌷 Navro'z bayramingiz bilan!",
        "05-09": "🎖️ G'alaba kuni bilan!",
        "09-01": "📚 Mustaqillik kuni bilan!",
        "12-08": "📜 Konstitutsiya kuni bilan!",
        "12-31": "🎇 Yangi Yil arafasida!"
    }
    
    today = datetime.utcnow().strftime("%m-%d")
    
    if today in holidays:
        title = holidays[today]
        message = (
            f"🎊 Hurmatli jamoamiz a'zolari!\n\n"
            f"Bot sizni {holidays[today].replace('!', '')} muborakbod etadi!\n\n"
            f"💝 Sizning mehnatingiz va sadoqatingiz uchun minnatdormiz.\n"
            f"✨ Yangi muvaffaqiyatlar, sog'lik va baxt tilaymiz!\n\n"
            f"🏢 Qurilish Materiallari Korxonasi rahbariyati"
        )
        
        await send_notification_to_all(title, message, "system_alert")
        
        return True
    
    return False

async def send_birthday_greetings():
    """
    Tug'ilgan kun tabriklari uchun bildirishnoma yuborish
    """
    
    today = datetime.utcnow().date()
    
    with get_db_session() as db:
        # Bugun tug'ilgan xodimlarni topish
        # (Eslatma: Employee modelida tug'ilgan kuni maydoni yo'q, 
        # ammo siz qo'shishingiz mumkin yoki boshqa usuldan foydalanishingiz mumkin)
        
        # Demo uchun:
        birthday_employees = []  # Bu yerda bugun tug'ilgan xodimlar ro'yxati
        
        if birthday_employees:
            for employee in birthday_employees:
                title = f"🎂 {employee.full_name} - Tug'ilgan kuningiz bilan!"
                message = (
                    f"🎉 Hurmatli {employee.full_name}!\n\n"
                    f"Bot sizni tug'ilgan kuningiz bilan chin qalbdan tabriklaydi!\n\n"
                    f"✨ Sog'lik, baxt, omad va yanada katta muvaffaqiyatlar tilaymiz!\n"
                    f"💝 Yoshingizga muvofiq yanada go'zal kunlar, ilhom va quvonchlar!\n\n"
                    f"🏢 Qurilish Materiallari Korxonasi jamoasi"
                )
                
                await send_notification_to_user(employee.telegram_id, title, message, "system_alert")
                
                # Jamoaga ham xabar berish
                team_message = (
                    f"🎉 Bugun bizning jamoamiz a'zosi {employee.full_name}ning "
                    f"tug'ilgan kuni!\n\n"
                    f"👏 Keling, unga tabriklarimizni bildiramiz!\n"
                    f"✨ {employee.full_name}, sizni yana bir yoshga kirganingiz bilan tabriklaymiz!"
                )
                
                await send_notification_to_department(
                    employee.department,
                    f"🎂 {employee.full_name}ning tug'ilgan kuni!",
                    team_message,
                    "system_alert"
                )
        
        return len(birthday_employees)

# =============== NOTIFICATION TEMPLATES ===============
class NotificationTemplates:
    """Bildirishnoma shablonlari"""
    
    @staticmethod
    def low_stock_template(material_name: str, current: float, minimum: float, unit: str) -> Dict[str, str]:
        """Xom ashyo tugashi shabloni"""
        return {
            'title': f'⚠️ {material_name} tugab qolmoqda',
            'message': (
                f'*{material_name}* xom ashyosi tugab qolmoqda!\n\n'
                f'📊 *Joriy qoldiq:* {current} {unit}\n'
                f'📉 *Minimal qoldiq:* {minimum} {unit}\n\n'
                f'🚨 *Zarur amallar:*\n'
                '1. Yangi xom ashyo buyurtma qiling\n'
                '2. Ishlab chiqarishni rejalashtiring\n'
                '3. Boshqa materiallarni tekshiring'
            )
        }
    
    @staticmethod
    def production_complete_template(order_number: str, product_name: str, quantity: int) -> Dict[str, str]:
        """Ishlab chiqarish tugashi shabloni"""
        return {
            'title': f'✅ #{order_number} buyurtma tayyor',
            'message': (
                f'🎉 #{order_number} raqamli buyurtma muvaffaqiyatli yakunlandi!\n\n'
                f'📋 *Mahsulot:* {product_name}\n'
                f'📦 *Miqdor:* {quantity} birlik\n\n'
                f'📦 Mahsulotlar omborga joylashtirildi.\n'
                f'💰 Sotish uchun tayyor.'
            )
        }
    
    @staticmethod
    def order_delivered_template(customer_name: str, product_name: str, amount: float) -> Dict[str, str]:
        """Buyurtma yetkazib berilishi shabloni"""
        return {
            'title': f'🚚 {customer_name} ga buyurtma yetkazildi',
            'message': (
                f'✅ {customer_name} mijoziga buyurtma muvaffaqiyatli yetkazib berildi!\n\n'
                f'📋 *Mahsulot:* {product_name}\n'
                f'💰 *Summa:* {amount:,.0f} so\'m\n\n'
                f'🎉 Mijoz qoniqdi.\n'
                f'💳 To\'lov qabul qilindi.'
            )
        }
    
    @staticmethod
    def salary_paid_template(employee_name: str, month: int, year: int, amount: float) -> Dict[str, str]:
        """Maosh to'langanligi shabloni"""
        return {
            'title': f'💰 {employee_name} ga maosh to\'landi',
            'message': (
                f'✅ {employee_name} xodimiga maosh to\'lovi amalga oshirildi!\n\n'
                f'📅 *Oy:* {month}/{year}\n'
                f'💳 *Miqdor:* {amount:,.0f} so\'m\n\n'
                f'🏦 Bank orqali o\'tkazildi.\n'
                f'📋 To\'lov hujjatlari tuzildi.'
            )
        }
    
    @staticmethod
    def system_alert_template(alert_type: str, details: str, action: str) -> Dict[str, str]:
        """Tizim ogohlantirishi shabloni"""
        return {
            'title': f'⚙️ Tizim ogohlantirishi: {alert_type}',
            'message': (
                f'⚠️ Tizimda ogohlantirish aniqlandi!\n\n'
                f'🔤 *Tur:* {alert_type}\n'
                f'📝 *Tafsilotlar:* {details}\n\n'
                f'🎯 *Kerakli amallar:*\n{action}'
            )
        }

# =============== NOTIFICATION MANAGER ===============
class NotificationManager:
    """Bildirishnoma menejeri"""
    
    def __init__(self, bot: Bot = None):
        if bot:
            set_bot_instance(bot)
    
    async def send_template_notification(self, template_name: str, **kwargs) -> bool:
        """Shablon asosida bildirishnoma yuborish"""
        
        templates = {
            'low_stock': NotificationTemplates.low_stock_template,
            'production_complete': NotificationTemplates.production_complete_template,
            'order_delivered': NotificationTemplates.order_delivered_template,
            'salary_paid': NotificationTemplates.salary_paid_template,
            'system_alert': NotificationTemplates.system_alert_template
        }
        
        if template_name not in templates:
            logger.error(f"Template {template_name} not found")
            return False
        
        template = templates[template_name]
        notification_data = template(**kwargs)
        
        return await send_notification_to_admins(
            notification_data['title'],
            notification_data['message'],
            template_name
        )
    
    async def check_all_notifications(self) -> Dict[str, int]:
        """
        Barcha avtomatik bildirishnomalarni tekshirish
        
        Returns:
            Dict: Har bir tur bo'yicha yuborilgan bildirishnomalar soni
        """
        
        results = {
            'low_stock': 0,
            'production': 0,
            'system': 0,
            'salary': 0,
            'delivery': 0
        }
        
        try:
            results['low_stock'] = await check_low_stock_notifications()
            results['production'] = await check_production_notifications()
            results['system'] = await check_system_notifications()
            results['salary'] = await check_salary_notifications()
            results['delivery'] = await check_delivery_notifications()
            
            logger.info(f"Notification check completed: {results}")
            
        except Exception as e:
            logger.error(f"Error checking notifications: {e}")
        
        return results
    
    async def send_scheduled_reports(self) -> Dict[str, bool]:
        """
        Rejalashtirilgan hisobotlarni yuborish
        
        Returns:
            Dict: Har bir hisobotning muvaffaqiyati
        """
        
        results = {
            'daily': False,
            'weekly': False,
            'monthly': False,
            'holiday': False,
            'birthday': False
        }
        
        try:
            # Kunlik hisobot (har kuni ertalab 9:00)
            now = datetime.utcnow()
            if now.hour == 9 and now.minute == 0:
                results['daily'] = await send_daily_report()
            
            # Haftalik hisobot (har yakshanba 10:00)
            if now.weekday() == 6 and now.hour == 10 and now.minute == 0:
                results['weekly'] = await send_weekly_report()
            
            # Oylik hisobot (har oyning 1-kuni 11:00)
            if now.day == 1 and now.hour == 11 and now.minute == 0:
                results['monthly'] = await send_monthly_report()
            
            # Bayram tabriklari
            results['holiday'] = await send_holiday_greetings()
            
            # Tug'ilgan kun tabriklari
            birthday_count = await send_birthday_greetings()
            results['birthday'] = birthday_count > 0
            
            logger.info(f"Scheduled reports sent: {results}")
            
        except Exception as e:
            logger.error(f"Error sending scheduled reports: {e}")
        
        return results

# =============== BACKGROUND TASK ===============
async def notification_background_task():
    """Bildirishnoma fon vazifasi"""
    
    manager = NotificationManager()
    
    while True:
        try:
            # Har 5 daqiqada avtomatik tekshiruv
            await asyncio.sleep(300)
            
            # Barcha bildirishnomalarni tekshirish
            await manager.check_all_notifications()
            
            # Rejalashtirilgan hisobotlarni yuborish
            await manager.send_scheduled_reports()
        
        except Exception as e:
            logger.error(f"Error in notification background task: {e}")
            await asyncio.sleep(60)  # Xatolik bo'lsa, 1 daqiqa kutish