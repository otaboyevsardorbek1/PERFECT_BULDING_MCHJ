"""
Qurilish Materiallari Korxonasi - AIOgram Bot
Asosiy fayl (Aiogram v3.22)
"""
import asyncio
import logging
from datetime import datetime
import sys
import os

# Papka yo'llarini sozlash
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import CommandStart, Command

from config import BOT_TOKEN, ADMIN_IDS, DB_NAME
from database.session import get_db_session
from database import models
from utils.notifications import set_bot_instance, notification_background_task

# =============== LOGGING KONFIGURATSIYASI ===============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/bot_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# =============== BOTNI ISHGA TUSHIRISH ===============
async def on_startup(bot: Bot):
    """Bot ishga tushganda"""
    
    logger.info("=== BOT ISHGA TUSHMOQDA ===")
    
    # Bot instance ni notifications moduliga o'rnatish
    set_bot_instance(bot)
    
    # Database jadvallarini yaratish
    try:
        models.Base.metadata.create_all(bind=models.engine)
        logger.info("✅ Database jadvallari yaratildi/yuklandi")
    except Exception as e:
        logger.error(f"❌ Database yaratishda xatolik: {e}")
    
    # Boshlang'ich ma'lumotlarni yaratish
    await initialize_database()
    
    # Adminlarga bot ishga tushganligi haqida xabar
    await send_startup_message(bot)
    
    # Background tasklarni boshlash
    asyncio.create_task(notification_background_task())
    
    logger.info("✅ Bot muvaffaqiyatli ishga tushdi!")

async def on_shutdown(bot: Bot):
    """Bot to'xtaganda"""
    
    logger.info("=== BOT TO'XTAMOQDA ===")
    
    # Adminlarga bot to'xtaganligi haqida xabar
    await send_shutdown_message(bot)
    
    # Database ulanishini yopish
    models.engine.dispose()
    
    logger.info("✅ Bot to'xtatildi")

async def initialize_database():
    """Database ni boshlang'ich ma'lumotlar bilan to'ldirish"""
    
    with get_db_session() as db:
        try:
            # Xom ashyo turlarini yaratish (agar bo'sh bo'lsa)
            raw_materials_count = db.query(models.RawMaterial).count()
            
            if raw_materials_count == 0:
                raw_materials = [
                    models.RawMaterial(
                        name="Klinker",
                        category="Asosiy",
                        unit="kg",
                        current_stock=10000,
                        min_stock=1000,
                        price_per_unit=500,
                        supplier="O'zbekiston Sement"
                    ),
                    models.RawMaterial(
                        name="Gips",
                        category="Asosiy",
                        unit="kg",
                        current_stock=5000,
                        min_stock=500,
                        price_per_unit=300,
                        supplier="Gips Zavodi"
                    ),
                    models.RawMaterial(
                        name="Qum",
                        category="Qurilish",
                        unit="kg",
                        current_stock=20000,
                        min_stock=2000,
                        price_per_unit=50,
                        supplier="Qum Kon"
                    ),
                    models.RawMaterial(
                        name="Temir sutka",
                        category="Metall",
                        unit="kg",
                        current_stock=8000,
                        min_stock=800,
                        price_per_unit=2000,
                        supplier="Metall Zavodi"
                    ),
                    models.RawMaterial(
                        name="Gil",
                        category="Keramika",
                        unit="kg",
                        current_stock=10000,
                        min_stock=1000,
                        price_per_unit=150,
                        supplier="Gil Kon"
                    ),
                ]
                
                for material in raw_materials:
                    db.add(material)
                
                db.commit()
                logger.info(f"✅ {len(raw_materials)} ta xom ashyo yaratildi")
            
            # Mahsulotlarni yaratish
            products_count = db.query(models.Product).count()
            
            if products_count == 0:
                products = [
                    models.Product(
                        name="Sement M500 (50kg)",
                        category="sement",
                        unit="qop",
                        selling_price=12000,
                        production_cost=7000,
                        profit_margin=0.4,
                        description="Yuqori sifatli qurilish sementi",
                        is_active=True
                    ),
                    models.Product(
                        name="Rodbin 12mm",
                        category="rodbin",
                        unit="metr",
                        selling_price=4500,
                        production_cost=3200,
                        profit_margin=0.3,
                        description="Armatura materiali",
                        is_active=True
                    ),
                    models.Product(
                        name="Kafel 30x30",
                        category="kafel",
                        unit="dona",
                        selling_price=850,
                        production_cost=450,
                        profit_margin=0.47,
                        description="Hovli va xonalar uchun kafel",
                        is_active=True
                    ),
                    models.Product(
                        name="Nalinoy pol",
                        category="pol",
                        unit="m2",
                        selling_price=2800,
                        production_cost=1800,
                        profit_margin=0.36,
                        description="Zamonaviy pol qoplamasi",
                        is_active=True
                    ),
                ]
                
                for product in products:
                    db.add(product)
                
                db.commit()
                logger.info(f"✅ {len(products)} ta mahsulot yaratildi")
            
            # Admin xodimni yaratish (agar yo'q bo'lsa)
            admin_employee = db.query(models.Employee).filter(
                models.Employee.is_admin == True
            ).first()
            
            if not admin_employee and ADMIN_IDS:
                admin = models.Employee(
                    telegram_id=ADMIN_IDS[0],
                    full_name="Asosiy Administrator",
                    phone_number="+998901234567",
                    position="Direktor",
                    department="Rahbariyat",
                    status=models.EmployeeStatus.ACTIVE,
                    hire_date=datetime.now(),
                    salary=0,
                    is_admin=True,
                    notes="Asosiy tizim administratori"
                )
                
                db.add(admin)
                db.commit()
                logger.info("✅ Asosiy admin xodim yaratildi")
            
            logger.info("✅ Database boshlang'ich ma'lumotlar bilan to'ldirildi")
            
        except Exception as e:
            logger.error(f"❌ Database initialization error: {e}")
            db.rollback()

async def send_startup_message(bot: Bot):
    """Bot ishga tushganida adminlarga xabar yuborish"""
    
    startup_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    message = (
        f"🚀 *Bot ishga tushdi!*\n\n"
        f"📅 Sana: {startup_time}\n"
        f"🤖 Qurilish Materiallari Korxonasi Boti\n"
        f"📊 Versiya: 2.0\n\n"
        f"✅ Tizim muvaffaqiyatli ishga tushirildi.\n"
        f"🔧 Barcha modullar yuklandi.\n"
        f"💾 Database faol.\n\n"
        f"📋 *Tayyor funksiyalar:*\n"
        f"• 🏭 Ishlab chiqarish boshqaruvi\n"
        f"• 📦 Ombor boshqaruvi\n"
        f"• 📊 Hisobot va statistika\n"
        f"• 👥 Xodimlar boshqaruvi\n"
        f"• 🔔 Push bildirishnomalar\n"
        f"• 📈 Excel va grafik hisobotlar\n"
        f"• 📄 PDF hisobotlar\n"
        f"• 📱 SMS xizmati\n"
        f"• 🤖 AI bashoratlar\n\n"
        f"🎯 Bot endi foydalanishga tayyor!"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=message,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Admin {admin_id} ga xabar yuborishda xatolik: {e}")

async def send_shutdown_message(bot: Bot):
    """Bot to'xtaganda adminlarga xabar yuborish"""
    
    shutdown_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    message = (
        f"🛑 *Bot to'xtatildi!*\n\n"
        f"📅 Sana: {shutdown_time}\n"
        f"🤖 Qurilish Materiallari Korxonasi Boti\n\n"
        f"🔧 Tizim xavfsiz tarzda to'xtatildi.\n"
        f"💾 Database ulanishlari yopildi.\n\n"
        f"🔄 Bot qayta ishga tushirilganda xabar beriladi."
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=message,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Admin {admin_id} ga xabar yuborishda xatolik: {e}")

# =============== ASOSIY FUNKSIYA ===============
async def main():
    """Asosiy funksiya"""
    
    # Bot va dispatcher yaratish (Aiogram v3)
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Startup/shutdown handlerlarni ro'yxatdan o'tkazish (v3 uslubi)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Handlerlarni ro'yxatdan o'tkazish
    logger.info("Handlerlarni ro'yxatdan o'tkazish...")
    
    # Handler importlari - har biri o'zini register qiladi
    from handlers.start import register_handlers_start
    from handlers.warehouse import register_handlers_warehouse
    from handlers.production import register_handlers_production
    from handlers.reports import register_handlers_reports
    from handlers.admin import register_handlers_admin
    from handlers.employees import register_handlers_employees
    from handlers.notifications import register_handlers_notifications
    from handlers.sales import register_handlers_sales
    from handlers.pdf_reports import register_handlers_pdf
    from handlers.sms import register_handlers_sms
    from handlers.ai_predict import register_handlers_ai
    
    register_handlers_start(dp)
    register_handlers_warehouse(dp)
    register_handlers_production(dp)
    register_handlers_reports(dp)
    register_handlers_admin(dp)
    register_handlers_employees(dp)
    register_handlers_notifications(dp)
    register_handlers_sales(dp)
    register_handlers_pdf(dp)
    register_handlers_sms(dp)
    register_handlers_ai(dp)
    
    logger.info("✅ Barcha handlerlar ro'yxatdan o'tkazildi")
    
    # Komandalarni o'rnatish
    await bot.set_my_commands([
        types.BotCommand(command="start", description="Botni ishga tushirish"),
        types.BotCommand(command="help", description="Yordam olish"),
        types.BotCommand(command="admin", description="Admin paneli"),
        types.BotCommand(command="ombor", description="Ombor holati"),
        types.BotCommand(command="ishlabchiqarish", description="Ishlab chiqarish"),
        types.BotCommand(command="hisobot", description="Hisobotlar"),
        types.BotCommand(command="pdf", description="PDF hisobotlar"),
        types.BotCommand(command="sms", description="SMS yuborish"),
        types.BotCommand(command="ai", description="AI bashoratlar"),
        types.BotCommand(command="xodimlar", description="Xodimlar boshqaruvi"),
        types.BotCommand(command="bildirishnoma", description="Bildirishnomalar"),
        types.BotCommand(command="cancel", description="Joriy amalni bekor qilish"),
    ])
    
    logger.info("✅ Bot komandalari o'rnatildi")
    
    # Botni ishga tushirish (Aiogram v3)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

# =============== ENTRY POINT ===============
if __name__ == "__main__":
    try:
        # Logs papkasini yaratish
        os.makedirs("logs", exist_ok=True)
        os.makedirs("reports/excel", exist_ok=True)
        os.makedirs("reports/charts", exist_ok=True)
        os.makedirs("backups", exist_ok=True)
        
        logger.info("=== QURILISH MATERIALLARI KORXONASI BOTI ===")
        logger.info(f"Bot tokeni: {BOT_TOKEN[:10]}...")
        logger.info(f"Adminlar: {ADMIN_IDS}")
        logger.info(f"Database: {DB_NAME}")
        
        # Asyncio event loop ni ishga tushirish
        asyncio.run(main())
        
    except KeyboardInterrupt:
        logger.info("Bot foydalanuvchi tomonidan to'xtatildi")
    except Exception as e:
        logger.error(f"Botda kritik xatolik: {e}", exc_info=True)
        sys.exit(1)
