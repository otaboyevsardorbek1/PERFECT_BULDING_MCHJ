from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove

from database.db import db
from keyboards.main_menu import get_main_menu, get_products_keyboard, get_confirm_keyboard
import logging

logger = logging.getLogger(__name__)

class WarehouseStates(StatesGroup):
    waiting_material_name = State()
    waiting_material_quantity = State()
    waiting_material_price = State()
    confirm_add_material = State()

async def show_warehouse_status(message: types.Message):
    """Ombordagi holatni ko'rsatish"""
    
    try:
        # Xom ashyolar holati
        raw_materials = db.get_warehouse_status()
        
        # Tayyor mahsulotlar holati
        products = db.get_products_status()
        
        # Xom ashyolarni formatlash
        raw_materials_text = ""
        for row in raw_materials:
            status_icon = "🟢" if "Yetarli" in row['status'] else "🟡" if "Ozgina" in row['status'] else "🔴"
            raw_materials_text += (
                f"{status_icon} **{row['material_name']}**: "
                f"{row['current_stock']} {row['unit']} "
                f"(minimum: {row['min_stock']} {row['unit']})\n"
            )
        
        # Mahsulotlarni formatlash
        products_text = ""
        for row in products:
            produced = row['produced'] or 0
            sold = row['sold'] or 0
            in_stock = produced - sold
            
            products_text += (
                f"📦 **{row['name']}**: "
                f"{in_stock} {row['unit']} mavjud\n"
                f"   💰 Narxi: {row['selling_price']:,} so'm\n"
                f"   📊 Ishlab chiqarilgan: {produced}, Sotilgan: {sold}\n\n"
            )
        
        # Umumiy statistika
        total_raw_materials = sum(row['current_stock'] for row in raw_materials)
        total_products_value = sum((row['produced'] or 0) * row['selling_price'] for row in products)
        
        response = (
            "🏭 **KORXONA OMBORI HOLATI**\n\n"
            
            "📦 **XOM ASHYOLAR:**\n"
            f"{raw_materials_text}\n"
            
            "🏗️ **TAYYOR MAHSULOTLAR:**\n"
            f"{products_text}\n"
            
            "📊 **UMUMIY STATISTIKA:**\n"
            f"• Xom ashyo: {total_raw_materials:,} birlik\n"
            f"• Mahsulotlar qiymati: {total_products_value:,} so'm\n\n"
            
            "⚠️ **OGOHLANTIRISH:** Qizil rangda ko'rsatilgan materiallar yetarli emas!"
        )
        
        await message.answer(response, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error showing warehouse status: {e}")
        await message.answer("❌ Xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.")

async def add_raw_material_start(message: types.Message):
    """Yangi xom ashyo qo'shishni boshlash"""
    await message.answer("Yangi xom ashyo nomini kiriting:", reply_markup=ReplyKeyboardRemove()) # type: ignore
    await WarehouseStates.waiting_material_name.set()

async def process_material_name(message: types.Message, state: FSMContext):
    """Xom ashyo nomini qabul qilish"""
    await state.update_data(material_name=message.text)
    await message.answer("Oʻlchov birligini kiriting (masalan: kg, m, dona):")
    await WarehouseStates.waiting_material_quantity.set()

async def process_material_unit(message: types.Message, state: FSMContext):
    """Oʻlchov birligini qabul qilish"""
    await state.update_data(unit=message.text)
    await message.answer("Narxini kiriting (1 birlik uchun so'mda):")
    await WarehouseStates.waiting_material_price.set()

async def process_material_price(message: types.Message, state: FSMContext):
    """Narxni qabul qilish"""
    try:
        price = float(message.text)
        data = await state.get_data()
        
        # Ma'lumotlarni ko'rsatish
        response = (
            f"📝 **Yangi xom ashyo ma'lumotlari:**\n\n"
            f"🏷️ Nomi: {data['material_name']}\n"
            f"📏 Birlik: {data['unit']}\n"
            f"💰 Narxi: {price:,} so'm\n\n"
            f"Ma'lumotlar to'g'rimi?"
        )
        
        await state.update_data(price=price)
        await message.answer(response, reply_markup=get_confirm_keyboard(), parse_mode="Markdown")
        await WarehouseStates.confirm_add_material.set()
        
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Faqat raqam kiriting:")

async def confirm_add_material(callback_query: types.CallbackQuery, state: FSMContext):
    """Xom ashyo qo'shishni tasdiqlash"""
    await callback_query.answer()
    
    if callback_query.data == "confirm_yes":
        data = await state.get_data()
        
        try:
            # Ma'lumotlar bazasiga qo'shish
            db.cursor.execute('''
            INSERT INTO raw_materials (name, unit, price_per_unit)
            VALUES (?, ?, ?)
            ''', (data['material_name'], data['unit'], data['price']))
            db.conn.commit()
            
            await callback_query.message.answer(
                f"✅ '{data['material_name']}' xom ashyosi muvaffaqiyatli qo'shildi!",
                reply_markup=get_main_menu()
            )
            
        except Exception as e:
            logger.error(f"Error adding raw material: {e}")
            await callback_query.message.answer(
                "❌ Xatolik yuz berdi. Bu nomdagi xom ashyo allaqachon mavjud bo'lishi mumkin.",
                reply_markup=get_main_menu()
            )
    else:
        await callback_query.message.answer(
            "❌ Xom ashyo qoʻshish bekor qilindi.",
            reply_markup=get_main_menu()
        )
    
    await state.finish()

def register_handlers_warehouse(dp: Dispatcher):
    #-- """Register warehouse handlers"""
    dp.register_message_handler(show_warehouse_status, lambda msg: msg.text == "📦 Ombor holati", state="*")
    dp.register_message_handler(add_raw_material_start, lambda msg: msg.text == "➕ Xom ashyo kiritish", state="*")
    
    dp.register_message_handler(process_material_name, state=WarehouseStates.waiting_material_name)
    dp.register_message_handler(process_material_unit, state=WarehouseStates.waiting_material_quantity)
    dp.register_message_handler(process_material_price, state=WarehouseStates.waiting_material_price)
    
    dp.register_callback_query_handler(confirm_add_material, 
                                      lambda c: c.data.startswith('confirm_'), 
                                      state=WarehouseStates.confirm_add_material)