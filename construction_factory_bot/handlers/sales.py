"""
Sales handlers for construction factory bot
Sotuvlar bo'limi handlerlari (soddalashtirilgan versiya)
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from aiogram import F, Router, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardRemove,
    InputFile,
    FSInputFile
)
from sqlalchemy import and_, func, select

from config import ADMINS, PRODUCT_TYPES
from database.session import get_db_session
from database import models
from keyboards.main_menu import get_main_menu
from utils.helpers import format_currency, validate_phone as validate_phone_number

# Router yaratish
sales_router = Router()


def crud_create_log(db, user_id, user_name, action, module):
    """SystemLog'ga yozish (crud.create_system_log o'rami)"""
    from database import crud
    return crud.create_system_log(
        db, user_id=user_id, user_name=user_name,
        action=action, module=module,
    )

# FSM (Finite State Machine) holatlari
class SalesStates(StatesGroup):
    waiting_for_product_selection = State()
    waiting_for_quantity = State()
    waiting_for_customer_info = State()
    waiting_for_payment_method = State()
    waiting_for_confirmation = State()
    waiting_for_report_period = State()
    waiting_for_customer_phone = State()
    waiting_for_customer_name = State()
    waiting_for_nasiya_advance = State()  # nasiya oldindan to'lov qismi
    waiting_for_discount = State()        # chegirma %
    waiting_for_mixed_cash = State()      # aralash to'lov: naqd qismi
    waiting_for_mixed_card = State()      # aralash to'lov: karta qismi
    waiting_for_mixed_remainder = State() # aralash to'lov: qolgan qism usuli


# ==================== ASOSIY MENYU ====================

@sales_router.message(F.text == "💰 Sotuvlar")
async def sales_main_menu(message: Message):
    """Sotuvlar bo'limining asosiy menyusi"""
    from utils.access import ensure_access
    if not await ensure_access(message, "sales"):
        return
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        types.KeyboardButton("🛒 Yangi sotuv"),
        types.KeyboardButton("📋 Sotuvlar tarixi"),
        types.KeyboardButton("↩️ Qaytarish akti"),
        types.KeyboardButton("🧾 Qaytarishlar tarixi"),
        types.KeyboardButton("📊 Sotuvlar statistika"),
        types.KeyboardButton("⬅️ Orqaga")
    ]
    keyboard.add(*buttons)
    
    await message.answer(
        "💰 <b>Sotuvlar bo'limi</b>\n\n"
        "Quyidagi amallardan birini tanlang:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# ==================== YANGI SOTUV ====================

@sales_router.message(F.text == "🛒 Yangi sotuv")
async def new_sale_start(message: Message, state: FSMContext):
    """Yangi sotuvni boshlash"""
    from utils.access import ensure_access
    if not await ensure_access(message, "sales", edit=True):
        return
    
    # Mahsulotlar ro'yxatini ko'rsatish
    with get_db_session() as db:
        products = db.query(models.Product).filter(
            models.Product.is_active == True
        ).all()
        
        product_rows = [[types.InlineKeyboardButton(
            text=f"{product.name} ({product.selling_price:,.0f} so'm)",
            callback_data=f"sale_product_{product.id}"
        )] for product in products]
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=product_rows if product_rows else [[]])
    
    await message.answer(
        "🛒 <b>Yangi sotuv</b>\n\n"
        "Mahsulotni tanlang:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await SalesStates.waiting_for_product_selection.set()


@sales_router.callback_query(F.data.startswith("sale_product_"))
async def process_product_selection(callback: CallbackQuery, state: FSMContext):
    """Mahsulot tanlash"""
    await callback.answer()
    
    product_id = int(callback.data.replace("sale_product_", ""))
    
    with get_db_session() as db:
        product = db.query(models.Product).filter(
            models.Product.id == product_id
        ).first()
        
        if not product:
            await callback.message.answer("❌ Mahsulot topilmadi.")
            await state.clear()
            return
        
        await state.update_data(
            product_id=product.id,
            product_name=product.name,
            product_unit=product.unit,
            selling_price=product.selling_price
        )
        
        # TZ: "O'xshash mahsulot taklifi" — mijoz g'isht olsa, mos sement/armatura tavsiya qilinadi
        from database.crud import get_related_products
        related = get_related_products(db, product.id, limit=3)
        related_text = ""
        if related:
            related_rows = []
            for r in related:
                related_rows.append([types.InlineKeyboardButton(
                    text=f"💡 {r.name} ({r.selling_price:,.0f} so'm)",
                    callback_data=f"sale_related_{r.id}"
                )])
            related_text = (
                f"\n💡 <b>O'xshash takliflar:</b>\n"
                f"Sizga ham {', '.join(r.name for r in related[:2])} kerak bo'lishi mumkin:\n\n"
            )
            related_keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=related_rows + [[types.InlineKeyboardButton(
                    text="✅ Asosiy mahsulotni tanlash", callback_data=f"sale_keep_{product.id}"
                )]]
            )
            await callback.message.answer(
                f"✅ Tanlangan: <b>{product.name}</b>\n"
                f"💰 Narx: {product.selling_price:,.0f} so'm/{product.unit}\n"
                f"📦 Omborda: {crud_get_available_qty(db, product.id):,.0f} {product.unit}\n"
                f"{related_text}"
                f"O'xshash mahsulotni tanlash yoki asosiy mahsulot bilan davom etish:",
                reply_markup=related_keyboard,
                parse_mode="HTML"
            )
            await state.update_data(related_seen=True)
            return
        
        await callback.message.answer(
            f"✅ Tanlangan: <b>{product.name}</b>\n"
            f"💰 Narx: {product.selling_price:,.0f} so'm/{product.unit}\n\n"
            f"📦 Necha {product.unit} sotmoqchisiz?",
            parse_mode="HTML"
        )
        await SalesStates.waiting_for_quantity.set()


@sales_router.callback_query(F.data.startswith("sale_related_"))
async def process_related_product(callback: CallbackQuery, state: FSMContext):
    """O'xshash mahsulotlardan birini tanlash"""
    await callback.answer()
    product_id = int(callback.data.replace("sale_related_", ""))
    with get_db_session() as db:
        product = db.query(models.Product).filter(models.Product.id == product_id).first()
        if not product:
            await callback.message.answer("❌ Mahsulot topilmadi.")
            await state.clear()
            return
        await state.update_data(
            product_id=product.id,
            product_name=product.name,
            product_unit=product.unit,
            selling_price=product.selling_price
        )
        await callback.message.answer(
            f"✅ Yangi tanlov: <b>{product.name}</b>\n"
            f"💰 Narx: {product.selling_price:,.0f} so'm/{product.unit}\n\n"
            f"📦 Necha {product.unit} sotmoqchisiz?",
            parse_mode="HTML"
        )
        await SalesStates.waiting_for_quantity.set()


@sales_router.callback_query(F.data.startswith("sale_keep_"))
async def process_keep_product(callback: CallbackQuery, state: FSMContext):
    """O'xshash takliflardan voz kechib, asosiy mahsulotni tanlash"""
    await callback.answer()
    product_id = int(callback.data.replace("sale_keep_", ""))
    with get_db_session() as db:
        product = db.query(models.Product).filter(models.Product.id == product_id).first()
        if not product:
            await callback.message.answer("❌ Mahsulot topilmadi.")
            await state.clear()
            return
        await state.update_data(
            product_id=product.id,
            product_name=product.name,
            product_unit=product.unit,
            selling_price=product.selling_price
        )
        await callback.message.answer(
            f"✅ Tanlangan: <b>{product.name}</b>\n"
            f"💰 Narx: {product.selling_price:,.0f} so'm/{product.unit}\n\n"
            f"📦 Necha {product.unit} sotmoqchisiz?",
            parse_mode="HTML"
        )
        await SalesStates.waiting_for_quantity.set()


def crud_get_available_qty(db, product_id: int) -> float:
    """Mahsulot ombordagi mavjud miqdorini qaytaradi (xato bo'lsa 0)"""
    from database.crud import get_available_product_qty
    try:
        return get_available_product_qty(db, product_id) or 0
    except Exception:
        return 0


@sales_router.message(SalesStates.waiting_for_quantity)
async def process_quantity(message: Message, state: FSMContext):
    """Miqdorni qabul qilish"""
    try:
        quantity = int(message.text)
        if quantity <= 0:
            await message.answer("❌ Miqdor 0 dan katta bo'lishi kerak.")
            return
        
        data = await state.get_data()
        total_amount = data['selling_price'] * quantity
        
        await state.update_data(quantity=quantity, total_amount=total_amount)
        
        await message.answer(
            f"📊 <b>Sotuv ma'lumotlari:</b>\n\n"
            f"🏭 Mahsulot: {data['product_name']}\n"
            f"📦 Miqdor: {quantity} {data['product_unit']}\n"
            f"💰 Narx: {data['selling_price']:,.0f} so'm\n"
            f"💵 Jami: {total_amount:,.0f} so'm\n\n"
            f"👤 Mijoz ismini kiriting:",
            parse_mode="HTML"
        )
        await SalesStates.waiting_for_customer_name.set()
        
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Faqat raqam kiriting:")


@sales_router.message(SalesStates.waiting_for_customer_name)
async def process_customer_name(message: Message, state: FSMContext):
    """Mijoz ismini qabul qilish"""
    await state.update_data(customer_name=message.text)
    
    await message.answer(
        "📞 Mijoz telefon raqamini kiriting\n"
        "(masalan: +998901234567):"
    )
    await SalesStates.waiting_for_customer_phone.set()


@sales_router.message(SalesStates.waiting_for_customer_phone)
async def process_customer_phone(message: Message, state: FSMContext):
    """Mijoz telefon raqamini qabul qilish"""
    
    if not validate_phone_number(message.text):
        await message.answer(
            "❌ Noto'g'ri telefon raqam formati.\n"
            "To'g'ri format: +998901234567"
        )
        return
    
    phone = message.text.strip()
    await state.update_data(customer_phone=phone)
    
    # Mavjud mijozni topish (CRM)
    with get_db_session() as db:
        from utils.helpers import normalize_phone
        customer = None
        try:
            customer = db.query(models.Customer).filter(
                models.Customer.phone == normalize_phone(phone)
            ).first()
        except Exception:
            customer = None
        if customer:
            await state.update_data(customer_id=customer.id)
            debt_info = f"\n🔴 Joriy qarzi: {customer.total_debt:,.0f} so'm" if customer.total_debt else ""
            await message.answer(
                f"✅ Mijoz tizimda topildi: <b>{customer.name}</b>{debt_info}\n\n"
                f"💳 To'lov usulini tanlang:",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "🆕 Yangi mijoz (CRM\'da yo'q).\n\n"
                f"💳 To'lov usulini tanlang:",
                parse_mode="HTML"
            )
    
    # To'lov usulini tanlash
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="💵 Naqd", callback_data="pay_cash"),
         types.InlineKeyboardButton(text="💳 Kartochka", callback_data="pay_card")],
        [types.InlineKeyboardButton(text="📱 Payme", callback_data="pay_payme"),
         types.InlineKeyboardButton(text="📱 Click", callback_data="pay_click")],
        [types.InlineKeyboardButton(text="🏦 O'tkazma", callback_data="pay_transfer"),
         types.InlineKeyboardButton(text="📝 Nasiya", callback_data="pay_credit")],
        [types.InlineKeyboardButton(text="🔀 Aralash to'lov", callback_data="pay_mixed")],
    ])
    
    await message.answer(
        "💳 To'lov usulini tanlang:",
        reply_markup=keyboard
    )
    await SalesStates.waiting_for_payment_method.set()


@sales_router.callback_query(F.data.startswith("pay_"))
async def process_payment_method(callback: CallbackQuery, state: FSMContext):
    """To'lov usulini qabul qilish"""
    await callback.answer()
    
    payment_method = callback.data.replace("pay_", "")
    payment_names = {
        "cash": "💵 Naqd pul",
        "card": "💳 Kartochka",
        "payme": "📱 Payme",
        "click": "📱 Click",
        "transfer": "🏦 O'tkazma",
        "credit": "📝 Nasiya (kredit)",
        "mixed": "🔀 Aralash to'lov"
    }
    
    await state.update_data(payment_method=payment_method)
    data = await state.get_data()
    
    # Nasiya: kredit limitini tekshirish + oldindan to'lov
    if payment_method == "credit":
        customer_id = data.get("customer_id")
        with get_db_session() as db:
            customer = None
            if customer_id:
                customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
            
            if not customer:
                await callback.message.answer(
                    "❌ Nasiya uchun mijoz CRM'da ro'yxatdan o'tgan bo'lishi shart!\n"
                    "👥 Mijozlar bo'limida avval mijozni qo'shing (kredit limiti bilan).",
                    reply_markup=get_main_menu()
                )
                await state.clear()
                return
            
            from database.crud import check_credit_limit
            check = check_credit_limit(db, customer, data["total_amount"])
            if not check["allowed"]:
                await callback.message.answer(
                    f"❌ <b>NASIYA BERIB BO'LMAYDI</b>\n\n{check['reason']}\n\n"
                    f"Direktorga xabar yuborildi.",
                    reply_markup=get_main_menu(), parse_mode="HTML"
                )
                # Direktor(lar)ga bildirishnoma
                try:
                    from utils.notifications import send_notification_to_admins
                    from config import ADMINS
                    await send_notification_to_admins(
                        title="🚨 Nasiya so'rovi rad etildi",
                        message=f"{callback.from_user.full_name} {data['customer_name']} uchun "
                                f"{data['total_amount']:,.0f} so'm nasiya bermoqchi edi.\n{check['reason']}"
                    )
                except Exception:
                    pass
                await state.clear()
                return
        
        # Oldindan (naqd) to'lov qancha?
        await callback.message.answer(
            f"💵 <b>NASIYA SOTUVI</b>\n\n"
            f"Jami: {data['total_amount']:,.0f} so'm\n"
            f"Qancha qismi oldindan (naqd/karta) to'lanadi?\n"
            f"0 kiritsangiz — to'liq nasiya.",
            parse_mode="HTML"
        )
        await SalesStates.waiting_for_nasiya_advance.set()
        return
    
    # Naqd/karta/payme/click: chegirma so'rash (sotuvchi 5% gacha)
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Chegirmasiz", callback_data="disc_0"),
         types.InlineKeyboardButton(text="3%", callback_data="disc_3")],
        [types.InlineKeyboardButton(text="5%", callback_data="disc_5"),
         types.InlineKeyboardButton(text="Boshqa %", callback_data="disc_custom")],
    ])
    await callback.message.answer(
        "🏷️ Chegirma foizi:", reply_markup=keyboard
    )
    await SalesStates.waiting_for_discount.set()


@sales_router.message(SalesStates.waiting_for_nasiya_advance)
async def process_nasiya_advance(message: Message, state: FSMContext):
    """Nasiya: oldindan to'lov miqdorini qabul qilish"""
    try:
        advance = float(message.text)
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Faqat raqam kiriting:")
        return
    
    data = await state.get_data()
    total = data["total_amount"]
    if advance < 0 or advance > total:
        await message.answer(f"❌ Oldindan to'lov 0 dan {total:,.0f} so'mgacha bo'lishi kerak:")
        return
    
    await state.update_data(advance_amount=advance, discount_amount=0)
    
    payment_names = {"credit": "📝 Nasiya"}
    confirm_text = (
        f"✅ <b>SOTUVNI TASDIQLASH</b>\n\n"
        f"🏭 Mahsulot: {data['product_name']}\n"
        f"📦 Miqdor: {data['quantity']} {data['product_unit']}\n"
        f"💵 Jami: {total:,.0f} so'm\n"
        f"👤 Mijoz: {data['customer_name']}\n"
        f"📞 Telefon: {data['customer_phone']}\n"
        f"💳 To'lov: {payment_names.get('credit', 'credit')}\n"
        f"💵 Oldindan: {advance:,.0f} so'm\n"
        f"📝 Nasiya qismi: {total - advance:,.0f} so'm\n\n"
        f"Sotuvni tasdiqlaysizmi?"
    )
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="confirm_sale"),
         types.InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_sale")],
    ])
    await message.answer(confirm_text, reply_markup=keyboard, parse_mode="HTML")
    await SalesStates.waiting_for_confirmation.set()


@sales_router.callback_query(F.data.startswith("disc_"), SalesStates.waiting_for_discount)
async def process_discount(callback: CallbackQuery, state: FSMContext):
    """Chegirma foizini qabul qilish"""
    await callback.answer()
    
    if callback.data == "disc_custom":
        await callback.message.answer("🏷️ Chegirma foizini kiriting (0-100, faqat raqam):")
        return  # xuddi shu state'da qoladi; keyingi xabar raqam sifatida qabul qilinadi
    
    percent = float(callback.data.replace("disc_", ""))
    await _finish_payment_setup(callback.message, state, percent)


@sales_router.message(SalesStates.waiting_for_discount)
async def process_custom_discount(message: Message, state: FSMContext):
    """Maxsus chegirma foizi"""
    try:
        percent = float(message.text)
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Faqat raqam kiriting (0-100):")
        return
    if percent < 0 or percent > 100:
        await message.answer("❌ Chegirma 0-100% orasida bo'lishi kerak:")
        return
    await _finish_payment_setup(message, state, percent)


async def _finish_payment_setup(message: Message, state: FSMContext, percent: float):
    """Chegirma qo'llab tasdiqlash ekranini ko'rsatish"""
    data = await state.get_data()
    payment_method = data["payment_method"]
    payment_names = {
        "cash": "💵 Naqd pul", "card": "💳 Kartochka", "payme": "📱 Payme",
        "click": "📱 Click", "transfer": "🏦 O'tkazma", "credit": "📝 Nasiya"
    }
    
    # Sotuvchining chegirma limiti
    from config import role_can_edit
    max_discount = 100
    with get_db_session() as db:
        from utils.access import get_user_role
        role = get_user_role(db, message.from_user.id)
    from config import ROLES
    if role in ROLES:
        max_discount = ROLES[role].get("discount_limit", 100)
    
    total = data["total_amount"]
    if percent > max_discount:
        # TZ: "Ikki bosqichli tasdiq — katta chegirma (>5%) direktorni SMS orqali tasdiqlatadi."
        # Sotuvchi limitdan oshsa: sotuv bekor qilinadi va direktor(lar)ga ogohlantirish ketadi.
        await message.answer(
            f"❌ Sizning rolingiz ({ROLES.get(role, {}).get('label', role)}) uchun "
            f"maksimal chegirma {max_discount}%! Direktor ruxsatisiz ko'proq chegirma berib bo'lmaydi."
        )
        try:
            from utils.notifications import send_notification_to_admins
            await send_notification_to_admins(
                title="🚨 Katta chegirma urinishi",
                message=f"{message.from_user.full_name} ({role}) {data['total_amount']:,.0f} so'mli "
                        f"sotuvga {percent}% chegirma bermoqchi edi (limit: {max_discount}%).\n"
                        f"Mahsulot: {data.get('product_name', '-')}",
                notification_type="system_alert",
            )
        except Exception:
            pass
        with get_db_session() as db:
            crud_create_log(db, message.from_user.id, message.from_user.full_name,
                            f"Chegirma limitidan oshish urinishi: {percent}% (limit {max_discount}%)",
                            "sales")
            # TZ: Xavfsizlik — shubhali harakat detektori
            try:
                crud.log_suspicious_activity(
                    db, "big_discount", severity="high",
                    description=f"{message.from_user.full_name} {data['total_amount']:,.0f} so'mli sotuvga "
                                f"{percent}% chegirma bermoqchi edi (limit {max_discount}%)",
                    user_name=message.from_user.full_name,
                    user_id=message.from_user.id,
                )
            except Exception:
                pass
        await state.clear()
        await message.answer("Sotuv bekor qilindi.", reply_markup=get_main_menu())
        return
    
    discount_amount = total * percent / 100
    final_total = total - discount_amount
    await state.update_data(discount_amount=discount_amount, advance_amount=final_total)
    
    # Aralash to'lov: chegirmadan keyin qismlarga bo'linadi
    if payment_method == "mixed":
        await message.answer(
            f"🔀 <b>ARALASH TO'LOV</b>\n\n"
            f"Jami: {final_total:,.0f} so'm\n\n"
            f"💵 <b>Naqd</b> qancha? (0 — naqd yo'q):",
            parse_mode="HTML"
        )
        await SalesStates.waiting_for_mixed_cash.set()
        return
    
    confirm_text = (
        f"✅ <b>SOTUVNI TASDIQLASH</b>\n\n"
        f"🏭 Mahsulot: {data['product_name']}\n"
        f"📦 Miqdor: {data['quantity']} {data['product_unit']}\n"
        f"💵 Summa: {total:,.0f} so'm\n"
        f"🏷️ Chegirma: {percent}% ({discount_amount:,.0f} so'm)\n"
        f"💵 Jami: {final_total:,.0f} so'm\n"
        f"👤 Mijoz: {data['customer_name']}\n"
        f"📞 Telefon: {data['customer_phone']}\n"
        f"💳 To'lov: {payment_names.get(payment_method, payment_method)}\n\n"
        f"Sotuvni tasdiqlaysizmi?"
    )
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="confirm_sale"),
         types.InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_sale")],
    ])
    await message.answer(confirm_text, reply_markup=keyboard, parse_mode="HTML")
    await SalesStates.waiting_for_confirmation.set()


# ==================== ARALASH TO'LOV (MIXED PAYMENT) ====================

@sales_router.message(SalesStates.waiting_for_mixed_cash)
async def process_mixed_cash(message: Message, state: FSMContext):
    """Aralash to'lov: naqd qismini qabul qilish"""
    try:
        cash = float(message.text)
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Faqat raqam kiriting:")
        return
    data = await state.get_data()
    final_total = data["total_amount"] - (data.get("discount_amount") or 0)
    if cash < 0 or cash > final_total:
        await message.answer(f"❌ Naqd 0 dan {final_total:,.0f} so'mgacha bo'lishi kerak:")
        return
    await state.update_data(mixed_cash=cash)
    await message.answer(
        f"💳 <b>Karta</b> qancha? (0 — karta yo'q)\n"
        f"Qolgan: {final_total - cash:,.0f} so'm",
        parse_mode="HTML"
    )
    await SalesStates.waiting_for_mixed_card.set()


@sales_router.message(SalesStates.waiting_for_mixed_card)
async def process_mixed_card(message: Message, state: FSMContext):
    """Aralash to'lov: karta qismini qabul qilish"""
    try:
        card = float(message.text)
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Faqat raqam kiriting:")
        return
    data = await state.get_data()
    final_total = data["total_amount"] - (data.get("discount_amount") or 0)
    cash = data.get("mixed_cash") or 0
    if card < 0 or card > final_total - cash:
        await message.answer(f"❌ Karta 0 dan {final_total - cash:,.0f} so'mgacha bo'lishi kerak:")
        return
    await state.update_data(mixed_card=card)
    remainder = round(final_total - cash - card, 2)
    if remainder <= 0.01:
        await state.update_data(mixed_remainder_method=None)
        await _show_mixed_confirm(message, state)
        return
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📝 Nasiya", callback_data="mixed_rem_credit"),
         types.InlineKeyboardButton(text="📱 Payme", callback_data="mixed_rem_payme")],
        [types.InlineKeyboardButton(text="📱 Click", callback_data="mixed_rem_click"),
         types.InlineKeyboardButton(text="🏦 O'tkazma", callback_data="mixed_rem_transfer")],
    ])
    await message.answer(
        f"Qolgan <b>{remainder:,.0f} so'm</b> qanday to'lanadi?",
        reply_markup=keyboard, parse_mode="HTML"
    )
    await SalesStates.waiting_for_mixed_remainder.set()


@sales_router.callback_query(F.data.startswith("mixed_rem_"), SalesStates.waiting_for_mixed_remainder)
async def process_mixed_remainder(callback: CallbackQuery, state: FSMContext):
    """Aralash to'lov: qolgan qism usulini tanlash"""
    await callback.answer()
    method = callback.data.replace("mixed_rem_", "")
    data = await state.get_data()
    final_total = data["total_amount"] - (data.get("discount_amount") or 0)
    remainder = round(final_total - (data.get("mixed_cash") or 0) - (data.get("mixed_card") or 0), 2)

    # Nasiya qismi uchun kredit limiti tekshiruvi
    if method == "credit":
        customer_id = data.get("customer_id")
        with get_db_session() as db:
            customer = None
            if customer_id:
                customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
            if not customer:
                await callback.message.answer(
                    "❌ Nasiya uchun mijoz CRM'da ro'yxatdan o'tgan bo'lishi shart!\n"
                    "👥 Mijozlar bo'limida avval mijozni qo'shing (kredit limiti bilan).",
                    reply_markup=get_main_menu()
                )
                await state.clear()
                return
            from database.crud import check_credit_limit
            check = check_credit_limit(db, customer, remainder)
            if not check["allowed"]:
                await callback.message.answer(
                    f"❌ <b>NASIYA BERIB BO'LMAYDI</b>\n\n{check['reason']}",
                    reply_markup=get_main_menu(), parse_mode="HTML"
                )
                await state.clear()
                return

    await state.update_data(mixed_remainder_method=method)
    await _show_mixed_confirm(callback.message, state)


async def _show_mixed_confirm(message: Message, state: FSMContext):
    """Aralash to'lov: qismlar bo'yicha tasdiqlash ekrani"""
    data = await state.get_data()
    total = data["total_amount"]
    discount = data.get("discount_amount") or 0
    final_total = total - discount
    cash = data.get("mixed_cash") or 0
    card = data.get("mixed_card") or 0
    rem_method = data.get("mixed_remainder_method")
    remainder = round(final_total - cash - card, 2)

    rem_names = {"credit": "📝 Nasiya", "payme": "📱 Payme", "click": "📱 Click", "transfer": "🏦 O'tkazma"}
    parts = [f"💵 Naqd: {cash:,.0f} so'm", f"💳 Karta: {card:,.0f} so'm"]
    if rem_method and remainder > 0:
        parts.append(f"{rem_names.get(rem_method, rem_method)}: {remainder:,.0f} so'm")

    confirm_text = (
        f"✅ <b>SOTUVNI TASDIQLASH</b>\n\n"
        f"🏭 Mahsulot: {data['product_name']}\n"
        f"📦 Miqdor: {data['quantity']} {data['product_unit']}\n"
        f"💵 Summa: {total:,.0f} so'm\n"
        f"🏷️ Chegirma: {discount:,.0f} so'm\n"
        f"💵 Jami: {final_total:,.0f} so'm\n"
        f"👤 Mijoz: {data['customer_name']}\n"
        f"📞 Telefon: {data['customer_phone']}\n"
        f"🔀 <b>Aralash to'lov:</b>\n"
    )
    for part in parts:
        confirm_text += f"   {part}\n"
    confirm_text += "\nSotuvni tasdiqlaysizmi?"

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="confirm_sale"),
         types.InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_sale")],
    ])
    await message.answer(confirm_text, reply_markup=keyboard, parse_mode="HTML")
    await SalesStates.waiting_for_confirmation.set()


@sales_router.callback_query(F.data == "confirm_sale", SalesStates.waiting_for_confirmation)
async def confirm_sale(callback: CallbackQuery, state: FSMContext):
    """Sotuvni tasdiqlash"""
    await callback.answer()
    
    data = await state.get_data()
    payment_method = data.get('payment_method', 'cash')
    
    try:
        with get_db_session() as db:
            from utils.helpers import normalize_phone
            is_credit = payment_method == "credit"
            
            # Aralash to'lov: qismlar bo'yicha payments ro'yxatini tuzish
            payments = None
            if payment_method == "mixed":
                cash = data.get('mixed_cash') or 0
                card = data.get('mixed_card') or 0
                rem_method = data.get('mixed_remainder_method')
                discount = data.get('discount_amount', 0) or 0
                final_total = data['total_amount'] - discount
                remainder = round(final_total - cash - card, 2)
                payments = []
                if round(cash, 2) > 0:
                    payments.append({"method": "cash", "amount": round(cash, 2)})
                if round(card, 2) > 0:
                    payments.append({"method": "card", "amount": round(card, 2)})
                if rem_method and remainder > 0:
                    payments.append({"method": rem_method, "amount": remainder})
                is_credit = rem_method == "credit"
            
            # Mijozni CRM'ga ro'yxatga olish/bog'lash
            customer_id = data.get('customer_id')
            customer = None
            if customer_id:
                customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
            
            if not customer and data.get('customer_phone'):
                customer = db.query(models.Customer).filter(
                    models.Customer.phone == normalize_phone(data['customer_phone'])
                ).first()
                if customer:
                    customer_id = customer.id
            
            discount = data.get('discount_amount', 0) or 0
            total = data['total_amount']
            final_total = total - discount
            
            # Sotuvni yozib olish (crud: chegirma, avans/qarz, to'lov, ballar, log)
            from database.crud import create_sale_record
            sale = create_sale_record(
                db,
                product_id=data['product_id'],
                quantity=data['quantity'],
                unit_price=data['selling_price'],
                total_amount=total,
                discount_amount=discount,
                advance_amount=data.get('advance_amount'),
                payment_method=payment_method,
                payments=payments,
                customer=customer,
                customer_name=data['customer_name'],
                customer_phone=data['customer_phone'],
                user_id=callback.from_user.id,
                user_name=callback.from_user.full_name,
            )
            debt_amount = sale.total_amount - sale.paid_amount
            
            # Chek yaratish
            pay_names = {"cash": "💵 Naqd", "card": "💳 Karta", "payme": "📱 Payme",
                         "click": "📱 Click", "transfer": "🏦 O'tkazma", "credit": "📝 Nasiya",
                         "mixed": "🔀 Aralash"}
            receipt_text = (
                f"🧾 <b>CHEK</b>\n\n"
                f"📋 Invoice: {sale.invoice_number}\n"
                f"🔖 Tranzaksiya: {sale.transaction_code}\n"
                f"📅 Sana: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                f"🏭 Mahsulot: {data['product_name']}\n"
                f"📦 Miqdor: {data['quantity']} {data['product_unit']}\n"
                f"💰 Narx: {data['selling_price']:,.0f} so'm\n"
                f"💵 Summa: {total:,.0f} so'm\n"
                f"🏷️ Chegirma: {discount:,.0f} so'm\n"
                f"💵 Jami: {final_total:,.0f} so'm\n"
                f"👤 Mijoz: {data['customer_name']}\n"
                f"📞 Telefon: {data['customer_phone']}\n"
                f"💳 To'lov: {pay_names.get(payment_method, payment_method)}\n"
            )
            if payment_method == "mixed":
                for p in payments or []:
                    receipt_text += f"   {pay_names.get(p['method'], p['method'])}: {p['amount']:,.0f} so'm\n"
                if is_credit:
                    receipt_text += (
                        f"\n📝 <b>NASIYA:</b> {debt_amount:,.0f} so'm\n"
                        f"⏳ Muddat: 30 kun (gacha {sale.due_date.strftime('%d.%m.%Y')})"
                    )
                else:
                    receipt_text += f"\n✅ To'lov qabul qilindi"
            elif is_credit:
                receipt_text += (
                    f"\n📝 <b>NASIYA:</b> {debt_amount:,.0f} so'm\n"
                    f"⏳ Muddat: 30 kun (gacha {sale.due_date.strftime('%d.%m.%Y')})"
                )
            else:
                receipt_text += f"\n✅ To'lov qabul qilindi"
            
            await callback.message.answer(receipt_text, reply_markup=get_main_menu(), parse_mode="HTML")

            # TZ: Xavfsizlik — tungi katta sotuv / uzluksiz urinishlar detektori
            try:
                hour = datetime.now().hour
                if hour < 6 or hour >= 23:
                    crud.log_suspicious_activity(
                        db, "night_sale", severity="medium",
                        description=f"Tungi vaqtda ({hour}:00) {final_total:,.0f} so'mli sotuv "
                                    f"({data['customer_name']})",
                        user_name=callback.from_user.full_name,
                        user_id=callback.from_user.id,
                        entity_id=sale.id,
                    )
            except Exception:
                pass

    except Exception as e:
        await callback.message.answer(
            f"❌ Xatolik yuz berdi: {str(e)}",
            reply_markup=get_main_menu()
        )
    
    await state.clear()


@sales_router.callback_query(F.data == "cancel_sale")
async def cancel_sale(callback: CallbackQuery, state: FSMContext):
    """Sotuvni bekor qilish"""
    await callback.answer()
    await state.clear()
    await callback.message.answer("❌ Sotuv bekor qilindi.", reply_markup=get_main_menu())


# ==================== SOTUVLAR TARIXI ====================

@sales_router.message(F.text == "📋 Sotuvlar tarixi")
async def sales_history(message: Message):
    """Sotuvlar tarixini ko'rsatish"""
    
    with get_db_session() as db:
        sales = db.query(models.Sale).order_by(
            models.Sale.created_at.desc()
        ).limit(10).all()
        
        if not sales:
            await message.answer("📭 Sotuvlar tarixi bo'sh.")
            return
        
        text = "📋 <b>SO'NGGI SOTUVLAR:</b>\n\n"
        
        for sale in sales:
            product = db.query(models.Product).filter(
                models.Product.id == sale.product_id
            ).first()
            
            product_name = product.name if product else "Noma'lum"
            
            text += (
                f"🧾 #{sale.invoice_number}\n"
                f"   🏭 {product_name} x {sale.quantity}\n"
                f"   💵 {sale.total_amount:,.0f} so'm\n"
                f"   📅 {sale.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            )
        
        await message.answer(text, parse_mode="HTML")


# ==================== SOTUVLAR STATISTIKASI ====================

@sales_router.message(F.text == "📊 Sotuvlar statistika")
async def sales_statistics(message: Message):
    """Sotuvlar statistikasini ko'rsatish"""
    
    with get_db_session() as db:
        # Umumiy statistika
        total_sales = db.query(models.Sale).count()
        total_amount = db.query(func.sum(models.Sale.total_amount)).scalar() or 0
        
        # Bugungi sotuvlar
        today = datetime.utcnow().date()
        today_sales = db.query(models.Sale).filter(
            func.date(models.Sale.sale_date) == today
        ).count()
        today_amount = db.query(func.sum(models.Sale.total_amount)).filter(
            func.date(models.Sale.sale_date) == today
        ).scalar() or 0
        
        # Eng ko'p sotilgan mahsulotlar
        top_products = db.query(
            models.Product.name,
            func.sum(models.Sale.quantity).label('total_sold')
        ).join(models.Sale).group_by(
            models.Product.id
        ).order_by(
            func.sum(models.Sale.quantity).desc()
        ).limit(5).all()
        
        text = (
            f"📊 <b>SOTUVLAR STATISTIKASI</b>\n\n"
            f"📈 <b>Umumiy ko'rsatkichlar:</b>\n"
            f"• Jami sotuvlar: {total_sales} ta\n"
            f"• Jami summa: {total_amount:,.0f} so'm\n\n"
            f"📅 <b>Bugun:</b>\n"
            f"• Sotuvlar: {today_sales} ta\n"
            f"• Summa: {today_amount:,.0f} so'm\n\n"
            f"🏆 <b>Eng ko'p sotilganlar:</b>\n"
        )
        
        for product in top_products:
            text += f"• {product.name}: {product.total_sold} dona\n"
        
        await message.answer(text, parse_mode="HTML")


# ==================== ORQAGA QAYTISH ====================

@sales_router.message(F.text == "⬅️ Orqaga")
async def back_to_main(message: Message, state: FSMContext):
    """Asosiy menyuga qaytish"""
    await state.clear()
    await message.answer("Asosiy menyu:", reply_markup=get_main_menu())


# ==================== REGISTER FUNCTION ====================

def register_handlers_sales(dp: Dispatcher):
    """Register sales handlers - Router ni Dispatcher ga qo'shish"""
    dp.include_router(sales_router)
