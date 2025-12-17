"""
Sales handlers for construction factory bot
Sotuvlar bo'limi handlerlari
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from aiogram import F, Router, types
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
from database.crud import (
    get_product_by_id,
    create_sale,
    get_sales_by_period,
    get_sales_statistics,
    update_product_quantity,
    get_customer_by_phone,
    create_customer,
    get_sale_by_id,
    create_sale_item
)
from database.models import Sale, SaleItem, Product, Customer
from database.session import get_db
from keyboards.inline_keyboards import (
    create_sales_menu_keyboard,
    create_product_selection_keyboard,
    create_pagination_keyboard,
    create_confirmation_keyboard
)
from keyboards.main_menu import get_main_menu
from utils.excel_reports import generate_sales_report
from utils.charts import create_sales_chart
from utils.helpers import format_currency, validate_phone_number
from utils.notifications import send_sale_notification

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
    
    keyboard = create_sales_menu_keyboard()
    
    await message.answer(
        "💰 <b>Sotuvlar bo'limi</b>\n\n"
        "Quyidagi amallardan birini tanlang:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# ==================== YANGI SOTUV ====================

@sales_router.callback_query(F.data == "new_sale")
async def start_new_sale(callback: CallbackQuery, state: FSMContext):
    """Yangi sotuvni boshlash"""
    
    # Mahsulotlar ro'yxatini olish
    async with get_db() as db:
        products = db.query(Product).filter(
            Product.quantity_available > 0
        ).all()
    
    if not products:
        await callback.message.answer(
            "⚠️ Hozircha sotish uchun mavjud mahsulotlar yo'q.\n"
            "Avval omborda mahsulotlar mavjudligini tekshiring."
        )
        return
    
    # Mahsulotlarni kategoriyalar bo'yicha guruhlash
    products_by_category = {}
    for product in products:
        category = product.product_type
        if category not in products_by_category:
            products_by_category[category] = []
        products_by_category[category].append(product)
    
    # FSM ga ma'lumotlarni saqlash
    await state.update_data(
        products_by_category=products_by_category,
        sale_items=[],
        current_category_index=0
    )
    
    # Birinchi kategoriyani ko'rsatish
    await show_product_category(callback.message, state)
    
    await callback.answer()

async def show_product_category(message: Message, state: FSMContext):
    """Mahsulot kategoriyasini ko'rsatish"""
    
    data = await state.get_data()
    products_by_category = data.get("products_by_category", {})
    categories = list(products_by_category.keys())
    
    if not categories:
        await message.answer("Mahsulotlar topilmadi")
        return
    
    current_index = data.get("current_category_index", 0)
    current_category = categories[current_index]
    products = products_by_category[current_category]
    
    keyboard = create_product_selection_keyboard(products, current_category)
    
    await message.answer(
        f"📦 <b>{current_category}</b>\n"
        f"Jami: {len(products)} ta mahsulot\n\n"
        "Sotmoqchi bo'lgan mahsulotingizni tanlang:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@sales_router.callback_query(F.data.startswith("select_product_"))
async def select_product(callback: CallbackQuery, state: FSMContext):
    """Mahsulotni tanlash"""
    
    product_id = int(callback.data.split("_")[-1])
    
    async with get_db() as db:
        product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        await callback.answer("Mahsulot topilmadi")
        return
    
    # FSM ga tanlangan mahsulotni saqlash
    await state.update_data(selected_product=product)
    await state.set_state(SalesStates.waiting_for_quantity)
    
    await callback.message.answer(
        f"📝 <b>{product.name}</b>\n"
        f"Mavjud: {product.quantity_available} {product.unit}\n"
        f"Narxi: {format_currency(product.selling_price)}\n\n"
        "Sotish miqdorini kiriting:",
        parse_mode="HTML"
    )
    
    await callback.answer()

@sales_router.message(SalesStates.waiting_for_quantity)
async def process_quantity(message: Message, state: FSMContext):
    """Sotish miqdorini qabul qilish"""
    
    try:
        quantity = float(message.text)
        if quantity <= 0:
            raise ValueError
    except ValueError:
        await message.answer(
            "❌ Noto'g'ri format! Iltimos, musbat son kiriting.\n"
            "Masalan: 10, 5.5, 100"
        )
        return
    
    data = await state.get_data()
    product = data.get("selected_product")
    
    # Miqdor tekshiruvi
    if quantity > product.quantity_available:
        await message.answer(
            f"❌ Yetarli mahsulot mavjud emas!\n"
            f"Mavjud: {product.quantity_available} {product.unit}\n"
            f"Sotmoqchi: {quantity} {product.unit}\n\n"
            "Kamroq miqdor kiriting yoki boshqa mahsulot tanlang."
        )
        return
    
    # Sotuv elementini yaratish
    sale_item = {
        "product_id": product.id,
        "product_name": product.name,
        "quantity": quantity,
        "unit": product.unit,
        "price": product.selling_price,
        "total": product.selling_price * quantity
    }
    
    # Sotuv elementlariga qo'shish
    sale_items = data.get("sale_items", [])
    sale_items.append(sale_item)
    
    # Jami summani hisoblash
    total_amount = sum(item["total"] for item in sale_items)
    
    # FSM ga yangilangan ma'lumotlarni saqlash
    await state.update_data(
        sale_items=sale_items,
        total_amount=total_amount
    )
    
    # Qo'shilgan mahsulotni ko'rsatish
    await message.answer(
        f"✅ <b>Qo'shildi:</b> {product.name}\n"
        f"Miqdor: {quantity} {product.unit}\n"
        f"Summa: {format_currency(sale_item['total'])}\n\n"
        f"📊 <b>Jami savat:</b>\n"
        f"Mahsulotlar soni: {len(sale_items)}\n"
        f"Jami summa: {format_currency(total_amount)}\n\n"
        "Yana mahsulot qo'shish uchun kategoriyani tanlang yoki "
        "sotuvni yakunlash uchun '✅ Sotuvni yakunlash' tugmasini bosing.",
        parse_mode="HTML"
    )
    
    # Kategoriyalar ro'yxatini qayta ko'rsatish
    await show_product_category(message, state)

@sales_router.callback_query(F.data == "finish_sale")
async def finish_sale_selection(callback: CallbackQuery, state: FSMContext):
    """Sotuvni yakunlash"""
    
    data = await state.get_data()
    sale_items = data.get("sale_items", [])
    
    if not sale_items:
        await callback.message.answer("Savat bo'sh. Mahsulot tanlang.")
        await show_product_category(callback.message, state)
        return
    
    # Mijoz ma'lumotlarini so'rash
    await state.set_state(SalesStates.waiting_for_customer_phone)
    
    await callback.message.answer(
        "📞 <b>Mijoz telefon raqamini kiriting:</b>\n"
        "Format: +998901234567 yoki 901234567",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )
    
    await callback.answer()

@sales_router.message(SalesStates.waiting_for_customer_phone)
async def process_customer_phone(message: Message, state: FSMContext):
    """Mijoz telefon raqamini qabul qilish"""
    
    phone = message.text.strip()
    
    # Telefon raqamini tekshirish
    if not validate_phone_number(phone):
        await message.answer(
            "❌ Noto'g'ri telefon raqami format!\n"
            "Iltimos, quyidagi formatlardan birida kiriting:\n"
            "+998901234567 yoki 901234567"
        )
        return
    
    # Telefon raqamini standart formatga keltirish
    if phone.startswith("+"):
        formatted_phone = phone
    else:
        formatted_phone = f"+998{phone}" if len(phone) == 9 else f"+{phone}"
    
    # Mijozni bazadan qidirish
    async with get_db() as db:
        customer = db.query(Customer).filter(
            Customer.phone == formatted_phone
        ).first()
    
    if customer:
        # Mijoz topildi
        await state.update_data(
            customer_phone=formatted_phone,
            customer_name=customer.name
        )
        
        await message.answer(
            f"✅ <b>Topildi:</b> {customer.name}\n\n"
            "To'lov usulini tanlang:",
            parse_mode="HTML",
            reply_markup=create_payment_method_keyboard()
        )
        
        await state.set_state(SalesStates.waiting_for_payment_method)
    else:
        # Yangi mijoz
        await state.update_data(customer_phone=formatted_phone)
        await state.set_state(SalesStates.waiting_for_customer_name)
        
        await message.answer(
            "👤 <b>Yangi mijoz</b>\n"
            "Mijozning ismini kiriting:",
            parse_mode="HTML"
        )

@sales_router.message(SalesStates.waiting_for_customer_name)
async def process_customer_name(message: Message, state: FSMContext):
    """Mijoz ismini qabul qilish"""
    
    customer_name = message.text.strip()
    
    if len(customer_name) < 2:
        await message.answer(
            "❌ Ism juda qisqa! Iltimos, to'liq ism kiriting."
        )
        return
    
    await state.update_data(customer_name=customer_name)
    
    await message.answer(
        f"✅ <b>Mijoz:</b> {customer_name}\n\n"
        "To'lov usulini tanlang:",
        parse_mode="HTML",
        reply_markup=create_payment_method_keyboard()
    )
    
    await state.set_state(SalesStates.waiting_for_payment_method)

@sales_router.callback_query(SalesStates.waiting_for_payment_method, F.data.startswith("payment_"))
async def process_payment_method(callback: CallbackQuery, state: FSMContext):
    """To'lov usulini tanlash"""
    
    payment_method = callback.data.split("_")[1]
    payment_methods = {
        "cash": "Naqd",
        "card": "Plastik karta",
        "transfer": "Bank o'tkazmasi",
        "credit": "Nasiya"
    }
    
    payment_name = payment_methods.get(payment_method, "Naqd")
    
    await state.update_data(payment_method=payment_method)
    
    # Sotuvni tasdiqlash
    data = await state.get_data()
    sale_items = data.get("sale_items", [])
    total_amount = data.get("total_amount", 0)
    customer_name = data.get("customer_name", "Noma'lum")
    
    # Sotuv ma'lumotlarini tayyorlash
    items_text = "\n".join([
        f"• {item['product_name']}: {item['quantity']} {item['unit']} = "
        f"{format_currency(item['total'])}"
        for item in sale_items
    ])
    
    await callback.message.answer(
        f"📋 <b>Sotuv ma'lumotlari</b>\n\n"
        f"👤 <b>Mijoz:</b> {customer_name}\n"
        f"💰 <b>To'lov usuli:</b> {payment_name}\n\n"
        f"📦 <b>Mahsulotlar:</b>\n{items_text}\n\n"
        f"💵 <b>Jami summa:</b> {format_currency(total_amount)}\n\n"
        "Sotuvni tasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=create_confirmation_keyboard("confirm_sale", "cancel_sale")
    )
    
    await state.set_state(SalesStates.waiting_for_confirmation)
    await callback.answer()

def create_payment_method_keyboard():
    """To'lov usullari klaviaturasi"""
    
    buttons = [
        [
            types.InlineKeyboardButton(
                text="💵 Naqd",
                callback_data="payment_cash"
            ),
            types.InlineKeyboardButton(
                text="💳 Karta",
                callback_data="payment_card"
            )
        ],
        [
            types.InlineKeyboardButton(
                text="🏦 Bank o'tkazmasi",
                callback_data="payment_transfer"
            ),
            types.InlineKeyboardButton(
                text="📅 Nasiya",
                callback_data="payment_credit"
            )
        ],
        [
            types.InlineKeyboardButton(
                text="❌ Bekor qilish",
                callback_data="cancel_sale"
            )
        ]
    ]
    
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)

@sales_router.callback_query(F.data == "confirm_sale")
async def confirm_sale(callback: CallbackQuery, state: FSMContext):
    """Sotuvni tasdiqlash va bazaga saqlash"""
    
    data = await state.get_data()
    sale_items = data.get("sale_items", [])
    total_amount = data.get("total_amount", 0)
    customer_phone = data.get("customer_phone")
    customer_name = data.get("customer_name", "Noma'lum")
    payment_method = data.get("payment_method", "cash")
    user_id = callback.from_user.id
    
    if not sale_items:
        await callback.answer("Savat bo'sh!")
        return
    
    async with get_db() as db:
        try:
            # Mijozni topish yoki yaratish
            customer = db.query(Customer).filter(
                Customer.phone == customer_phone
            ).first()
            
            if not customer:
                customer = Customer(
                    name=customer_name,
                    phone=customer_phone,
                    created_by=user_id
                )
                db.add(customer)
                db.commit()
                db.refresh(customer)
            
            # Sotuvni yaratish
            sale = Sale(
                customer_id=customer.id,
                total_amount=total_amount,
                payment_method=payment_method,
                created_by=user_id,
                sale_number=f"SALE-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            )
            
            db.add(sale)
            db.commit()
            db.refresh(sale)
            
            # Sotuv elementlarini yaratish
            for item in sale_items:
                sale_item = SaleItem(
                    sale_id=sale.id,
                    product_id=item["product_id"],
                    quantity=item["quantity"],
                    unit_price=item["price"],
                    total_price=item["total"]
                )
                db.add(sale_item)
                
                # Mahsulot miqdorini yangilash
                product = db.query(Product).filter(
                    Product.id == item["product_id"]
                ).first()
                
                if product:
                    product.quantity_available -= item["quantity"]
            
            db.commit()
            
            # Bildirishnoma yuborish
            await send_sale_notification(sale, sale_items, customer)
            
            # Foydalanuvchiga xabar
            await callback.message.answer(
                f"✅ <b>Sotuv muvaffaqiyatli amalga oshirildi!</b>\n\n"
                f"📊 <b>Sotuv raqami:</b> {sale.sale_number}\n"
                f"👤 <b>Mijoz:</b> {customer.name}\n"
                f"💰 <b>Jami summa:</b> {format_currency(total_amount)}\n"
                f"📅 <b>Sana:</b> {sale.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                "Chek olish uchun /get_receipt {sotuv_raqami} buyrug'idan foydalanishingiz mumkin.",
                parse_mode="HTML"
            )
            
            # Foydalanuvchiga chek yuborish
            receipt_text = generate_receipt_text(sale, sale_items, customer)
            await callback.message.answer(
                receipt_text,
                parse_mode="HTML"
            )
            
            # Holatni tozalash
            await state.clear()
            
        except Exception as e:
            db.rollback()
            await callback.message.answer(
                f"❌ Xatolik yuz berdi: {str(e)}"
            )
            print(f"Sale error: {e}")
    
    await callback.answer()

@sales_router.callback_query(F.data == "cancel_sale")
async def cancel_sale(callback: CallbackQuery, state: FSMContext):
    """Sotuvni bekor qilish"""
    
    await state.clear()
    await callback.message.answer(
        "❌ Sotuv bekor qilindi.",
        reply_markup=get_main_menu(callback.from_user.id)
    )
    await callback.answer()

def generate_receipt_text(sale: Sale, sale_items: List[Dict], customer: Customer) -> str:
    """Chek matnini yaratish"""
    
    items_text = "\n".join([
        f"{item['product_name']:<30} {item['quantity']:>5} {item['unit']:<5} "
        f"{format_currency(item['price']):>10} {format_currency(item['total']):>15}"
        for item in sale_items
    ])
    
    payment_methods = {
        "cash": "Naqd",
        "card": "Plastik karta",
        "transfer": "Bank o'tkazmasi",
        "credit": "Nasiya"
    }
    
    receipt = (
        "═══════════════════════════════\n"
        "        💰 SOTUV CHEKI 💰\n"
        "═══════════════════════════════\n"
        f"Sotuv raqami: {sale.sale_number}\n"
        f"Sana: {sale.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"Mijoz: {customer.name}\n"
        f"Telefon: {customer.phone}\n"
        f"To'lov usuli: {payment_methods.get(sale.payment_method, 'Naqd')}\n"
        "═══════════════════════════════\n"
        "Mahsulot          Miqdor  Narxi       Summa\n"
        "═══════════════════════════════\n"
        f"{items_text}\n"
        "═══════════════════════════════\n"
        f"JAMI: {format_currency(sale.total_amount):>48}\n"
        "═══════════════════════════════\n"
        "Rahmat! Siz bilan hamkorlikdan mamnunmiz!\n"
        "═══════════════════════════════"
    )
    
    return f"<pre>{receipt}</pre>"

# ==================== SOTUVLAR TARIXI ====================

@sales_router.callback_query(F.data == "sales_history")
async def show_sales_history(callback: CallbackQuery):
    """Sotuvlar tarixini ko'rsatish"""
    
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="📅 Bugungi sotuvlar",
                    callback_data="today_sales"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="📊 Oxirgi 7 kun",
                    callback_data="last_7_days"
                ),
                types.InlineKeyboardButton(
                    text="📈 Oxirgi 30 kun",
                    callback_data="last_30_days"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="🗓️ Tanlangan sana",
                    callback_data="select_date"
                ),
                types.InlineKeyboardButton(
                    text="📋 Barcha sotuvlar",
                    callback_data="all_sales"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="🔙 Orqaga",
                    callback_data="back_to_sales_menu"
                )
            ]
        ]
    )
    
    await callback.message.answer(
        "📊 <b>Sotuvlar tarixi</b>\n\n"
        "Ko'rmoqchi bo'lgan davrni tanlang:",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    
    await callback.answer()

@sales_router.callback_query(F.data.startswith(("today_sales", "last_7_days", "last_30_days", "all_sales")))
async def show_period_sales(callback: CallbackQuery):
    """Davr bo'yicha sotuvlarni ko'rsatish"""
    
    period = callback.data
    
    async with get_db() as db:
        if period == "today_sales":
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            sales = db.query(Sale).filter(
                Sale.created_at >= start_date
            ).order_by(Sale.created_at.desc()).all()
            title = "Bugungi sotuvlar"
            
        elif period == "last_7_days":
            start_date = datetime.now() - timedelta(days=7)
            sales = db.query(Sale).filter(
                Sale.created_at >= start_date
            ).order_by(Sale.created_at.desc()).all()
            title = "Oxirgi 7 kunlik sotuvlar"
            
        elif period == "last_30_days":
            start_date = datetime.now() - timedelta(days=30)
            sales = db.query(Sale).filter(
                Sale.created_at >= start_date
            ).order_by(Sale.created_at.desc()).all()
            title = "Oxirgi 30 kunlik sotuvlar"
            
        else:  # all_sales
            sales = db.query(Sale).order_by(Sale.created_at.desc()).limit(50).all()
            title = "Barcha sotuvlar (oxirgi 50 ta)"
        
        if not sales:
            await callback.message.answer(
                f"📭 {title} bo'yicha sotuvlar topilmadi."
            )
            return
        
        # Statistikani hisoblash
        total_sales = len(sales)
        total_amount = sum(sale.total_amount for sale in sales)
        
        # Sotuvlarni formatlash
        sales_text = f"📊 <b>{title}</b>\n\n"
        sales_text += f"📈 Jami sotuvlar: {total_sales} ta\n"
        sales_text += f"💰 Jami summa: {format_currency(total_amount)}\n\n"
        
        for i, sale in enumerate(sales[:10], 1):  # Faqat 10 tasini ko'rsatish
            customer = db.query(Customer).filter(
                Customer.id == sale.customer_id
            ).first()
            
            customer_name = customer.name if customer else "Noma'lum"
            
            sales_text += (
                f"{i}. <b>{sale.sale_number}</b>\n"
                f"   👤 {customer_name}\n"
                f"   💰 {format_currency(sale.total_amount)}\n"
                f"   📅 {sale.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            )
        
        if len(sales) > 10:
            sales_text += f"... va yana {len(sales) - 10} ta sotuv"
        
        await callback.message.answer(
            sales_text,
            parse_mode="HTML"
        )
    
    await callback.answer()

# ==================== SOTUV STATISTIKASI ====================

@sales_router.callback_query(F.data == "sales_statistics")
async def show_sales_statistics(callback: CallbackQuery):
    """Sotuv statistikasini ko'rsatish"""
    
    async with get_db() as db:
        # Kunlik statistika
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_sales = db.query(Sale).filter(
            Sale.created_at >= today
        ).all()
        
        # Haftalik statistika
        week_ago = datetime.now() - timedelta(days=7)
        weekly_sales = db.query(Sale).filter(
            Sale.created_at >= week_ago
        ).all()
        
        # Oylik statistika
        month_ago = datetime.now() - timedelta(days=30)
        monthly_sales = db.query(Sale).filter(
            Sale.created_at >= month_ago
        ).all()
        
        # Jami statistika
        total_sales = db.query(Sale).count()
        
        # Summalarni hisoblash
        today_total = sum(sale.total_amount for sale in today_sales)
        weekly_total = sum(sale.total_amount for sale in weekly_sales)
        monthly_total = sum(sale.total_amount for sale in monthly_sales)
        
        # Eng ko'p sotilgan mahsulotlar
        top_products = db.query(
            SaleItem.product_id,
            func.sum(SaleItem.quantity).label('total_quantity'),
            func.sum(SaleItem.total_price).label('total_amount')
        ).group_by(SaleItem.product_id).order_by(
            func.sum(SaleItem.total_price).desc()
        ).limit(5).all()
        
        # Eng ko'p xaridorlar
        top_customers = db.query(
            Sale.customer_id,
            func.count(Sale.id).label('purchase_count'),
            func.sum(Sale.total_amount).label('total_spent')
        ).group_by(Sale.customer_id).order_by(
            func.sum(Sale.total_amount).desc()
        ).limit(5).all()
    
    # Statistikani formatlash
    stats_text = "📊 <b>Sotuv statistikasi</b>\n\n"
    
    stats_text += "📅 <b>Davrlar bo'yicha:</b>\n"
    stats_text += f"• Bugun: {len(today_sales)} ta sotuv, {format_currency(today_total)}\n"
    stats_text += f"• Oxirgi 7 kun: {len(weekly_sales)} ta, {format_currency(weekly_total)}\n"
    stats_text += f"• Oxirgi 30 kun: {len(monthly_sales)} ta, {format_currency(monthly_total)}\n"
    stats_text += f"• Jami: {total_sales} ta sotuv\n\n"
    
    stats_text += "🏆 <b>Eng ko'p sotilgan mahsulotlar:</b>\n"
    for i, (product_id, quantity, amount) in enumerate(top_products, 1):
        async with get_db() as db:
            product = db.query(Product).filter(Product.id == product_id).first()
            product_name = product.name if product else f"Mahsulot #{product_id}"
        
        stats_text += f"{i}. {product_name}: {quantity} birlik, {format_currency(amount)}\n"
    
    stats_text += "\n👥 <b>Eng ko'p xarid qilgan mijozlar:</b>\n"
    for i, (customer_id, count, spent) in enumerate(top_customers, 1):
        async with get_db() as db:
            customer = db.query(Customer).filter(Customer.id == customer_id).first()
            customer_name = customer.name if customer else f"Mijoz #{customer_id}"
        
        stats_text += f"{i}. {customer_name}: {count} ta sotuv, {format_currency(spent)}\n"
    
    # Grafik yaratish
    chart_path = await create_sales_chart(monthly_sales)
    
    if chart_path:
        photo = FSInputFile(chart_path)
        await callback.message.answer_photo(
            photo,
            caption=stats_text,
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            stats_text,
            parse_mode="HTML"
        )
    
    await callback.answer()

# ==================== SOTUV HISOBOTI ====================

@sales_router.callback_query(F.data == "sales_report")
async def request_sales_report(callback: CallbackQuery, state: FSMContext):
    """Sotuv hisoboti so'rovini qabul qilish"""
    
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="📅 Bugungi hisobot",
                    callback_data="report_today"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="🗓️ Oxirgi 7 kun",
                    callback_data="report_week"
                ),
                types.InlineKeyboardButton(
                    text="📆 Oxirgi 30 kun",
                    callback_data="report_month"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="📋 To'liq hisobot",
                    callback_data="report_full"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="🔙 Orqaga",
                    callback_data="back_to_sales_menu"
                )
            ]
        ]
    )
    
    await callback.message.answer(
        "📄 <b>Sotuv hisoboti</b>\n\n"
        "Qaysi davr bo'yicha hisobot kerak?",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    
    await callback.answer()

@sales_router.callback_query(F.data.startswith("report_"))
async def generate_sales_report_file(callback: CallbackQuery):
    """Excel hisobotini yaratish va yuborish"""
    
    period = callback.data
    
    async with get_db() as db:
        if period == "report_today":
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            sales = db.query(Sale).filter(
                Sale.created_at >= start_date
            ).all()
            report_name = "bugungi_sotuvlar"
            
        elif period == "report_week":
            start_date = datetime.now() - timedelta(days=7)
            sales = db.query(Sale).filter(
                Sale.created_at >= start_date
            ).all()
            report_name = "oxirgi_7_kun"
            
        elif period == "report_month":
            start_date = datetime.now() - timedelta(days=30)
            sales = db.query(Sale).filter(
                Sale.created_at >= start_date
            ).all()
            report_name = "oxirgi_30_kun"
            
        else:  # report_full
            sales = db.query(Sale).all()
            report_name = "barcha_sotuvlar"
    
    if not sales:
        await callback.message.answer(
            "📭 Tanlangan davr bo'yicha sotuvlar topilmadi."
        )
        await callback.answer()
        return
    
    # Excel hisobotini yaratish
    report_path = generate_sales_report(sales, report_name)
    
    if report_path:
        # Faylni yuborish
        document = FSInputFile(report_path)
        
        await callback.message.answer_document(
            document,
            caption=f"📊 Sotuv hisoboti: {report_name.replace('_', ' ').title()}\n"
                    f"📅 Sana: {datetime.now().strftime('%d.%m.%Y')}\n"
                    f"📈 Jami sotuvlar: {len(sales)} ta"
        )
    else:
        await callback.message.answer(
            "❌ Hisobot yaratishda xatolik yuz berdi."
        )
    
    await callback.answer()

# ==================== QAYTARISH (RETURN) ====================

@sales_router.callback_query(F.data == "sales_return")
async def sales_return_menu(callback: CallbackQuery, state: FSMContext):
    """Sotuvni qaytarish menyusi"""
    
    await callback.message.answer(
        "🔄 <b>Sotuvni qaytarish</b>\n\n"
        "Qaytarish uchun sotuv raqamini yoki chek raqamini kiriting:\n"
        "Masalan: SALE-20231215-ABC123",
        parse_mode="HTML"
    )
    
    await state.set_state(SalesStates.waiting_for_report_period)
    await callback.answer()

# ==================== YORDAMCHI FUNKSIYALAR ====================

@sales_router.message(Command("get_receipt"))
async def get_receipt_by_number(message: Message):
    """Sotuv raqami bo'yicha chek olish"""
    
    args = message.text.split()
    
    if len(args) < 2:
        await message.answer(
            "❌ Iltimos, sotuv raqamini kiriting:\n"
            "/get_receipt SALE-20231215-ABC123"
        )
        return
    
    sale_number = args[1].strip().upper()
    
    async with get_db() as db:
        sale = db.query(Sale).filter(
            Sale.sale_number == sale_number
        ).first()
        
        if not sale:
            await message.answer(
                f"❌ {sale_number} raqamli sotuv topilmadi."
            )
            return
        
        # Sotuv elementlarini olish
        sale_items = db.query(SaleItem).filter(
            SaleItem.sale_id == sale.id
        ).all()
        
        customer = db.query(Customer).filter(
            Customer.id == sale.customer_id
        ).first()
        
        # Sotuv elementlarini formatlash
        items_list = []
        for item in sale_items:
            product = db.query(Product).filter(
                Product.id == item.product_id
            ).first()
            
            items_list.append({
                "product_id": item.product_id,
                "product_name": product.name if product else "Noma'lum",
                "quantity": item.quantity,
                "unit": product.unit if product else "birlik",
                "price": item.unit_price,
                "total": item.total_price
            })
        
        # Chek yaratish
        receipt_text = generate_receipt_text(sale, items_list, customer)
        
        await message.answer(
            receipt_text,
            parse_mode="HTML"
        )

# ==================== ORQAGA QAYTISH ====================

@sales_router.callback_query(F.data == "back_to_sales_menu")
async def back_to_sales_menu(callback: CallbackQuery, state: FSMContext):
    """Sotuvlar menyusiga qaytish"""
    
    await state.clear()
    await sales_main_menu(callback.message)
    await callback.answer()

@sales_router.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    """Asosiy menyuga qaytish"""
    
    await state.clear()
    await callback.message.answer(
        "Asosiy menyu:",
        reply_markup=get_main_menu(callback.from_user.id)
    )
    await callback.answer()