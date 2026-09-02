"""
SMS Handler - SMS yuborish boshqaruvi
"""

from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS, INTEGRATION_SETTINGS
from keyboards.main_menu import get_main_menu
from utils.sms_service import sms_service
import logging

logger = logging.getLogger(__name__)


class SMSStates(StatesGroup):
    waiting_phone_number = State()
    waiting_message = State()
    waiting_bulk_phones = State()


async def sms_menu(message: types.Message):
    """SMS menyusi"""
    
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Sizda bu amalni bajarish huquqi yo'q!")
        return
    
    sms_enabled = INTEGRATION_SETTINGS.get('sms_enabled', False)
    status = "✅ Faol" if sms_enabled else "❌ O'chirilgan"
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        "📱 SMS yuborish",
        "📱 Ommaviy SMS",
        "⚙️ SMS sozlamalari",
        "⬅️ Orqaga"
    ]
    keyboard.add(*buttons)
    
    await message.answer(
        f"📱 <b>SMS XIZMATI</b>\n\n"
        f"Holat: {status}\n"
        f"Xizmat: Eskiz.uz\n\n"
        f"Amallardan birini tanlang:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def send_single_sms_start(message: types.Message):
    """Bitta SMS yuborishni boshlash"""
    
    if message.from_user.id not in ADMIN_IDS:
        return
    
    if not INTEGRATION_SETTINGS.get('sms_enabled', False):
        await message.answer(
            "❌ SMS xizmati o'chirilgan.\n"
            "Sozlamalarni tekshiring."
        )
        return
    
    await message.answer(
        "📱 <b>SMS YUBORISH</b>\n\n"
        "Telefon raqamini kiriting\n"
        "(masalan: +998901234567):",
        parse_mode="HTML"
    )
    await SMSStates.waiting_phone_number.set()


async def process_phone_number(message: types.Message, state: FSMContext):
    """Telefon raqamini qabul qilish"""
    
    phone = message.text.strip()
    
    # Telefon raqamini tekshirish
    if not phone.startswith('+998') or len(phone) != 13:
        await message.answer(
            "❌ Noto'g'ri telefon raqam formati.\n"
            "To'g'ri format: +998901234567"
        )
        return
    
    await state.update_data(phone_number=phone)
    
    await message.answer(
        "✏️ SMS matnini kiriting\n"
        "(maksimum 160 belgi):"
    )
    await SMSStates.waiting_message.set()


async def process_sms_message(message: types.Message, state: FSMContext):
    """SMS matnini qabul qilish va yuborish"""
    
    text = message.text.strip()
    
    if len(text) > 160:
        await message.answer(
            "❌ SMS matni 160 belgidan oshmasligi kerak.\n"
            f"Hozirgi uzunlik: {len(text)} belgi"
        )
        return
    
    data = await state.get_data()
    phone = data['phone_number']
    
    await message.answer("⏳ SMS yuborilmoqda...")
    
    # SMS yuborish
    result = await sms_service.send_sms(phone, text)
    
    if result['success']:
        await message.answer(
            f"✅ <b>SMS MUVOFFAQIYATLI YUBORILDI!</b>\n\n"
            f"📞 Qabul qiluvchi: {phone}\n"
            f"📝 Matn: {text}\n"
            f"📊 Uzunlik: {len(text)} belgi",
            reply_markup=get_main_menu(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"❌ <b>SMS YUBORISHDA XATOLIK!</b>\n\n"
            f"📞 Qabul qiluvchi: {phone}\n"
            f"❌ Xatolik: {result.get('error', 'Noma\'lum xatolik')}",
            reply_markup=get_main_menu(),
            parse_mode="HTML"
        )
    
    await state.clear()


async def send_bulk_sms_start(message: types.Message):
    """Ommaviy SMS yuborishni boshlash"""
    
    if message.from_user.id not in ADMIN_IDS:
        return
    
    if not INTEGRATION_SETTINGS.get('sms_enabled', False):
        await message.answer("❌ SMS xizmati o'chirilgan.")
        return
    
    await message.answer(
        "📱 <b>OMMAVIY SMS</b>\n\n"
        "Telefon raqamlarini kiriting\n"
        "(har bir qator alohida raqam):\n\n"
        "Masalan:\n"
        "+998901234567\n"
        "+998901234568\n"
        "+998901234569",
        parse_mode="HTML"
    )
    await SMSStates.waiting_bulk_phones.set()


async def process_bulk_phones(message: types.Message, state: FSMContext):
    """Ommaviy SMS uchun raqamlarni qabul qilish"""
    
    phones = [p.strip() for p in message.text.strip().split('\n') if p.strip()]
    
    # Telefon raqamlarni tekshirish
    valid_phones = []
    for phone in phones:
        if phone.startswith('+998') and len(phone) == 13:
            valid_phones.append(phone)
    
    if not valid_phones:
        await message.answer(
            "❌ Hech qanday to'g'ri telefon raqam topilmadi.\n"
            "Format: +998901234567"
        )
        return
    
    await state.update_data(bulk_phones=valid_phones)
    
    await message.answer(
        f"✅ {len(valid_phones)} ta raqam qabul qilindi.\n\n"
        f"✏️ SMS matnini kiriting\n"
        f"(maksimum 160 belgi):"
    )
    await SMSStates.waiting_message.set()


async def process_bulk_sms_message(message: types.Message, state: FSMContext):
    """Ommaviy SMS matnini qabul qilish va yuborish"""
    
    text = message.text.strip()
    
    if len(text) > 160:
        await message.answer(
            f"❌ SMS matni 160 belgidan oshmasligi kerak.\n"
            f"Hozirgi uzunlik: {len(text)} belgi"
        )
        return
    
    data = await state.get_data()
    phones = data.get('bulk_phones', [])
    
    if not phones:
        await message.answer("❌ Telefon raqamlar topilmadi.")
        await state.clear()
        return
    
    await message.answer(f"⏳ {len(phones)} ta raqamga SMS yuborilmoqda...")
    
    # Ommaviy SMS yuborish
    result = await sms_service.send_bulk_sms(phones, text)
    
    await message.answer(
        f"📊 <b>OMMAVIY SMS NATIJALARI</b>\n\n"
        f"✅ Muvaffaqiyatli: {result['success']} ta\n"
        f"❌ Xatolik: {result['failed']} ta\n"
        f"📈 Jami: {result['total']} ta\n"
        f"🎯 Muvaffaqiyat: {result['success']/result['total']*100 if result['total'] > 0 else 0:.1f}%",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )
    
    await state.clear()


async def sms_settings(message: types.Message):
    """SMS sozlamalari"""
    
    if message.from_user.id not in ADMIN_IDS:
        return
    
    sms_enabled = INTEGRATION_SETTINGS.get('sms_enabled', False)
    sms_provider = INTEGRATION_SETTINGS.get('sms_provider', 'eskiz.uz')
    sms_sender = INTEGRATION_SETTINGS.get('sms_sender', 'KORXONA')
    
    settings_text = (
        f"⚙️ <b>SMS SOZLAMALARI</b>\n\n"
        f"📱 Xizmat: {sms_provider}\n"
        f"📤 Yuboruvchi: {sms_sender}\n"
        f"🔴 Holat: {'✅ Faol' if sms_enabled else '❌ O\'chirilgan'}\n\n"
        f"📝 Sozlamalarni o'zgartirish uchun admin bilan bog'laning."
    )
    
    await message.answer(settings_text, parse_mode="HTML")


def register_handlers_sms(dp: Dispatcher):
    """SMS handlerlarini ro'yxatdan o'tkazish"""
    
    dp.message.register(sms_menu, F.text == "📱 SMS xizmati")
    
    dp.message.register(send_single_sms_start, F.text == "📱 SMS yuborish")
    
    dp.message.register(send_bulk_sms_start, F.text == "📱 Ommaviy SMS")
    
    dp.message.register(sms_settings, F.text == "⚙️ SMS sozlamalari")
    
    dp.message.register(process_phone_number, SMSStates.waiting_phone_number)
    
    dp.message.register(process_bulk_phones, SMSStates.waiting_bulk_phones)
    
    dp.message.register(process_sms_message, SMSStates.waiting_message)
