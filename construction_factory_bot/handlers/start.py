from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import CommandStart, Command

from keyboards.main_menu import get_main_menu
from config import ADMIN_IDS

async def cmd_start(message: types.Message, state: FSMContext):
    """Start command handler"""
    await state.finish()
    
    # Foydalanuvchini ADMIN_IDS ro'yxatida tekshirish
    is_admin = message.from_user.id in ADMIN_IDS
    
    welcome_text = f"""
    👋 Assalomu alaykum, {message.from_user.full_name}!

    🏭 **Qurilish Materiallari Korxonasi Botiga xush kelibsiz!**

    🤖 Men sizning ishlab chiqarish jarayoningizni boshqarishga yordam beraman.

    📋 **Mening imkoniyatlarim:**
    • 🏭 Ishlab chiqarishni boshqarish
    • 📦 Ombordagi holatni kuzatish
    • 💰 Xarajatlar hisobini yuritish
    • 📊 Statistika va hisobotlar
    • ➕ Xom ashyo kiritish/chiqarish
    """
    
    if is_admin:
        welcome_text += "\n\n👑 Siz **Administrator** maqomidasiz!"
    
    await message.answer(welcome_text, reply_markup=get_main_menu(), parse_mode="Markdown")

async def cmd_help(message: types.Message):
    """Help command handler"""
    help_text = """
    🤖 **Botdan foydalanish bo'yicha ko'rsatmalar:**

    🏭 **Ishlab chiqarish:**
    • Yangi mahsulot ishlab chiqarish buyurtmasi berish
    • Jarayondagi buyurtmalarni kuzatish
    • Tayyor mahsulotlarni ombarga kiritish

    📦 **Ombor boshqaruvi:**
    • Xom ashyo holatini ko'rish
    • Yangi xom ashyo kiritish
    • Minimum zaxira chegarasini sozlash

    💰 **Moliya va hisob-kitob:**
    • Ishlab chiqarish xarajatlarini hisoblash
    • Foyda-marginal hisob-kitob
    • Narx tahlili

    📊 **Hisobotlar:**
    • Kunlik/haftalik/oylik hisobotlar
    • Excel formatda yuklab olish
    • Grafik va diagrammalar

    ⚙️ **Sozlamalar:**
    • Mahsulot formulalarini sozlash
    • Xodimlar ro'yxati
    • Ruxsatlarni boshqarish

    📞 **Qo'llab-quvvatlash:**
    Muammo yuzaga kelsa, administrator bilan bog'laning.
    """
    
    await message.answer(help_text, parse_mode="Markdown")

async def cmd_cancel(message: types.Message, state: FSMContext):
    """Cancel operation"""
    await state.finish()
    await message.answer("❌ Amal bekor qilindi.", reply_markup=get_main_menu())

def register_handlers_start(dp: Dispatcher):
    """Register start handlers"""
    dp.register_message_handler(cmd_start, CommandStart(), state="*")
    dp.register_message_handler(cmd_help, commands=['help'], state="*")
    dp.register_message_handler(cmd_cancel, commands=['cancel'], state="*")
    dp.register_message_handler(cmd_cancel, lambda msg: msg.text in ["⬅️ Orqaga", "❌ Bekor qilish"], state="*")