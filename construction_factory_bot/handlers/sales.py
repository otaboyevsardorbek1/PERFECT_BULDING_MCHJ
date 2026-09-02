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


# ==================== ASOSIY MENYU ====================

@sales_router.message(F.text == "💰 Sotuvlar")
async def sales_main_menu(message: Message):
    """Sotuvlar bo'limining asosiy menyusi"""
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        types.KeyboardButton("🛒 Yangi sotuv"),
        types.KeyboardButton("📋 Sotuvlar tarixi"),
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
        
        await callback.message.answer(
            f"✅ Tanlangan: <b>{product.name}</b>\n"
            f"💰 Narx: {product.selling_price:,.0f} so'm/{product.unit}\n\n"
            f"📦 Necha {product.unit} sotmoqchisiz?",
            parse_mode="HTML"
        )
        await SalesStates.waiting_for_quantity.set()


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
    
    await state.update_data(customer_phone=message.text)
    
    # To'lov usulini tanlash
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="💵 Naqd", callback_data="pay_cash"),
         types.InlineKeyboardButton(text="💳 Kartochka", callback_data="pay_card")],
        [types.InlineKeyboardButton(text="🏦 O'tkazma", callback_data="pay_transfer"),
         types.InlineKeyboardButton(text="📝 Nasiya", callback_data="pay_credit")],
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
        "transfer": "🏦 O'tkazma",
        "credit": "📝 Nasiya"
    }
    
    await state.update_data(payment_method=payment_method)
    
    data = await state.get_data()
    
    # Tasdiqlash uchun xabar
    confirm_text = (
        f"✅ <b>SOTUVNI TASDIQLASH</b>\n\n"
        f"🏭 Mahsulot: {data['product_name']}\n"
        f"📦 Miqdor: {data['quantity']} {data['product_unit']}\n"
        f"💵 Jami: {data['total_amount']:,.0f} so'm\n"
        f"👤 Mijoz: {data['customer_name']}\n"
        f"📞 Telefon: {data['customer_phone']}\n"
        f"💳 To'lov: {payment_names.get(payment_method, payment_method)}\n\n"
        f"Sotuvni tasdiqlaysizmi?"
    )
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="confirm_sale"),
         types.InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_sale")],
    ])
    
    await callback.message.answer(confirm_text, reply_markup=keyboard, parse_mode="HTML")
    await SalesStates.waiting_for_confirmation.set()


@sales_router.callback_query(F.data == "confirm_sale", SalesStates.waiting_for_confirmation)
async def confirm_sale(callback: CallbackQuery, state: FSMContext):
    """Sotuvni tasdiqlash"""
    await callback.answer()
    
    data = await state.get_data()
    
    try:
        with get_db_session() as db:
            # Sotuvni yaratish
            sale = models.Sale(
                invoice_number=f"INV-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}",
                product_id=data['product_id'],
                quantity=data['quantity'],
                unit_price=data['selling_price'],
                total_amount=data['total_amount'],
                customer_name=data['customer_name'],
                customer_phone=data['customer_phone'],
                payment_method=data['payment_method'],
                status="completed",
                sale_date=datetime.utcnow()
            )
            db.add(sale)
            db.commit()
            
            # Ombordagi harakatni kiritish
            transaction = models.WarehouseTransaction(
                product_id=data['product_id'],
                quantity=data['quantity'],
                transaction_type=models.TransactionType.SALE,
                user_id=callback.from_user.id,
                user_name=callback.from_user.full_name,
                notes=f"Sotuv #{sale.invoice_number}"
            )
            db.add(transaction)
            db.commit()
            
            # Chek yaratish
            receipt_text = (
                f"🧾 <b>CHEK</b>\n\n"
                f"📋 Invoice: {sale.invoice_number}\n"
                f"📅 Sana: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                f"🏭 Mahsulot: {data['product_name']}\n"
                f"📦 Miqdor: {data['quantity']} {data['product_unit']}\n"
                f"💰 Narx: {data['selling_price']:,.0f} so'm\n"
                f"💵 Jami: {data['total_amount']:,.0f} so'm\n\n"
                f"👤 Mijoz: {data['customer_name']}\n"
                f"📞 Telefon: {data['customer_phone']}\n"
                f"💳 To'lov: {data['payment_method']}\n\n"
                f"✅ Sotuv muvaffaqiyatli amalga oshirildi!"
            )
            
            await callback.message.answer(receipt_text, reply_markup=get_main_menu(), parse_mode="HTML")
            
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
