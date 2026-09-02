from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove

from database.db import db
from keyboards.main_menu import get_main_menu, get_production_menu, get_products_keyboard, get_confirm_keyboard
import logging

logger = logging.getLogger(__name__)

class ProductionStates(StatesGroup):
    waiting_product_selection = State()
    waiting_quantity = State()
    confirm_production = State()

async def production_menu(message: types.Message):
    """Ishlab chiqarish menyusi"""
    await message.answer("🏭 Ishlab chiqarish bo'limi:", reply_markup=get_production_menu())

async def new_production_order(message: types.Message):
    """Yangi ishlab chiqarish buyurtmasi"""
    await message.answer("Mahsulot turini tanlang:", reply_markup=get_products_keyboard())
    await ProductionStates.waiting_product_selection.set()

async def process_product_selection(callback_query: types.CallbackQuery, state: FSMContext):
    """Mahsulotni tanlash"""
    await callback_query.answer()
    
    product_code = callback_query.data.replace("product_", "")
    
    # Product code bo'yicha product_id ni olish
    product_map = {
        "sement": "Sement M500 (50kg)",
        "rodbin": "Rodbin 12mm",
        "kafel": "Kafel 30x30",
        "nalinoy_pol": "Nalinoy pol",
        "gips": "Gips",
        "keramika": "Keramika plitka"
    }
    
    if product_code in product_map:
        product_name = product_map[product_code]
        
        # Ma'lumotlar bazasidan product_id ni olish
        db.cursor.execute('SELECT id FROM products WHERE name = ?', (product_name,))
        result = db.cursor.fetchone()
        
        if result:
            product_id = result[0]
            await state.update_data(product_id=product_id, product_name=product_name)
            
            await callback_query.message.answer(
                f"✅ Tanlangan mahsulot: {product_name}\n\n"
                f"📦 Necha birlik ishlab chiqarmoqchisiz?",
                reply_markup=ReplyKeyboardRemove()
            )
            await ProductionStates.waiting_quantity.set()
        else:
            await callback_query.message.answer("❌ Mahsulot topilmadi.")
            await state.clear()
    else:
        await callback_query.message.answer("❌ Noto'g'ri tanlov.")
        await state.clear()

async def process_quantity(message: types.Message, state: FSMContext):
    """Ishlab chiqarish miqdorini qabul qilish"""
    try:
        quantity = int(message.text)
        
        if quantity <= 0:
            await message.answer("❌ Miqdor 0 dan katta bo'lishi kerak. Qayta kiriting:")
            return
        
        await state.update_data(quantity=quantity)
        data = await state.get_data()
        
        # Mahsulot formulasi bo'yicha xarajatlarni hisoblash
        product_id = data['product_id']
        
        db.cursor.execute('''
        SELECT rm.name, rm.current_stock, pf.quantity as required_per_unit, rm.price_per_unit
        FROM product_formulas pf
        JOIN raw_materials rm ON pf.raw_material_id = rm.id
        WHERE pf.product_id = ?
        ''', (product_id,))
        
        formula_items = db.cursor.fetchall()
        
        if not formula_items:
            await message.answer("❌ Bu mahsulot uchun formula topilmadi.")
            await state.clear()
            return
        
        # Xarajatlarni hisoblash
        total_cost = 0
        materials_needed = []
        can_produce = True
        missing_materials = []
        
        response = f"📊 **{data['product_name']} - {quantity} birlik uchun hisob-kitob:**\n\n"
        
        for item in formula_items:
            required_total = item['required_per_unit'] * quantity
            available = item['current_stock']
            material_cost = required_total * item['price_per_unit']
            total_cost += material_cost
            
            status = "✅ Yetarli" if available >= required_total else "❌ Yetarli emas"
            
            if available < required_total:
                can_produce = False
                missing_materials.append({
                    'name': item['name'],
                    'required': required_total,
                    'available': available,
                    'deficit': required_total - available
                })
            
            response += (
                f"• **{item['name']}**: {required_total} kg kerak "
                f"(mavjud: {available} kg) - {status}\n"
            )
        
        # Mehnat va energiya xarajatlari (taxminiy)
        labor_cost = total_cost * 0.3
        energy_cost = total_cost * 0.1
        total_with_overhead = total_cost + labor_cost + energy_cost
        unit_cost = total_with_overhead / quantity
        
        # Mahsulot narxini olish
        db.cursor.execute('SELECT selling_price FROM products WHERE id = ?', (product_id,))
        selling_price = db.cursor.fetchone()[0]
        
        profit_per_unit = selling_price - unit_cost
        total_profit = profit_per_unit * quantity
        
        response += (
            f"\n💰 **Xarajatlar hisobi:**\n"
            f"• Xom ashyo: {total_cost:,.0f} so'm\n"
            f"• Mehnat (30%): {labor_cost:,.0f} so'm\n"
            f"• Energiya (10%): {energy_cost:,.0f} so'm\n"
            f"• Jami xarajat: {total_with_overhead:,.0f} so'm\n"
            f"• Birlik xarajati: {unit_cost:,.0f} so'm\n\n"
            
            f"💰 **Daromad hisobi:**\n"
            f"• Sotish narxi: {selling_price:,.0f} so'm/birlik\n"
            f"• Foyda/birlik: {profit_per_unit:,.0f} so'm\n"
            f"• Umumiy foyda: {total_profit:,.0f} so'm\n\n"
        )
        
        if not can_produce:
            response += f"⚠️ **OGOHLANTIRISH:** Quyidagi materiallar yetarli emas:\n"
            for material in missing_materials:
                response += f"• {material['name']}: {material['deficit']} kg yetishmayapti\n"
            response += f"\nIltimos, ombordan xom ashyo kiritib, qayta urinib ko'ring."
        else:
            response += f"✅ **XOM ASHYO YETARLI** - Ishlab chiqarish mumkin!"
        
        await state.update_data(
            total_cost=total_with_overhead,
            can_produce=can_produce,
            missing_materials=missing_materials
        )
        
        await message.answer(response, parse_mode="Markdown")
        
        if can_produce:
            await message.answer("Ishlab chiqarishni boshlaymizmi?", reply_markup=get_confirm_keyboard())
            await ProductionStates.confirm_production.set()
        else:
            await state.clear()
            
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Faqat raqam kiriting:")

async def confirm_production(callback_query: types.CallbackQuery, state: FSMContext):
    """Ishlab chiqarishni tasdiqlash"""
    await callback_query.answer()
    
    if callback_query.data == "confirm_yes":
        data = await state.get_data()
        
        try:
            # Ishlab chiqarish buyurtmasini yaratish
            db.cursor.execute('''
            INSERT INTO production_orders (product_id, quantity, total_cost, status)
            VALUES (?, ?, ?, 'jarayonda')
            ''', (data['product_id'], data['quantity'], data['total_cost']))
            
            order_id = db.cursor.lastrowid
            
            # Xom ashyolarni ishlatish (ombordan chiqim)
            product_id = data['product_id']
            
            db.cursor.execute('''
            SELECT rm.id, pf.quantity as required_per_unit
            FROM product_formulas pf
            JOIN raw_materials rm ON pf.raw_material_id = rm.id
            WHERE pf.product_id = ?
            ''', (product_id,))
            
            formula_items = db.cursor.fetchall()
            
            for item in formula_items:
                required_total = item['required_per_unit'] * data['quantity']
                
                # Ombordagi harakatni kiritish
                db.add_transaction(
                    product_id=data['product_id'],
                    raw_material_id=item['id'],
                    quantity=required_total,
                    transaction_type='ishlab_chiqarish',
                    user_id=callback_query.from_user.id,
                    notes=f"Ishlab chiqarish buyurtmasi #{order_id}"
                )
            
            # Buyurtmani 'tayyor' holatiga o'tkazish
            db.cursor.execute('''
            UPDATE production_orders 
            SET status = 'tayyor', completed_date = CURRENT_TIMESTAMP
            WHERE id = ?
            ''', (order_id,))
            
            db.conn.commit()
            
            response = (
                f"✅ **ISHLAB CHIQARISH MUVOFAQQIYATLI BAJARILDI!**\n\n"
                f"📋 Buyurtma raqami: #{order_id}\n"
                f"🏭 Mahsulot: {data['product_name']}\n"
                f"📦 Miqdor: {data['quantity']} birlik\n"
                f"💰 Jami xarajat: {data['total_cost']:,.0f} so'm\n\n"
                f"🎉 Tabriklaymiz! Mahsulotlar omboringizga qo'shildi."
            )
            
            await callback_query.message.answer(response, reply_markup=get_main_menu(), parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Error confirming production: {e}")
            await callback_query.message.answer(
                "❌ Xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.",
                reply_markup=get_main_menu()
            )
    else:
        await callback_query.message.answer(
            "❌ Ishlab chiqarish bekor qilindi.",
            reply_markup=get_main_menu()
        )
    
    await state.clear()

async def show_production_statistics(message: types.Message):
    """Ishlab chiqarish statistikasi"""
    try:
        db.cursor.execute('''
        SELECT 
            p.name,
            COUNT(po.id) as order_count,
            SUM(po.quantity) as total_quantity,
            SUM(po.total_cost) as total_cost,
            AVG(po.total_cost / po.quantity) as avg_unit_cost
        FROM production_orders po
        JOIN products p ON po.product_id = p.id
        WHERE po.status = 'tayyor'
        GROUP BY p.name
        ORDER BY total_quantity DESC
        ''')
        
        stats = db.cursor.fetchall()
        
        if not stats:
            await message.answer("📭 Hali ishlab chiqarish statistikasi mavjud emas.")
            return
        
        response = "📊 **ISHLAB CHIQARISH STATISTIKASI**\n\n"
        
        total_all = 0
        cost_all = 0
        
        for row in stats:
            response += (
                f"🏭 **{row['name']}:**\n"
                f"• Buyurtmalar: {row['order_count']} ta\n"
                f"• Jami miqdor: {row['total_quantity']} birlik\n"
                f"• Jami xarajat: {row['total_cost']:,.0f} so'm\n"
                f"• O'rtacha birlik xarajati: {row['avg_unit_cost']:,.0f} so'm\n\n"
            )
            
            total_all += row['total_quantity']
            cost_all += row['total_cost']
        
        response += (
            f"📈 **UMUMIY KO'RSATKICHLAR:**\n"
            f"• Jami ishlab chiqarilgan: {total_all} birlik\n"
            f"• Jami xarajat: {cost_all:,.0f} so'm\n"
            f"• O'rtacha xarajat/birlik: {cost_all/total_all:,.0f} so'm"
        )
        
        await message.answer(response, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error showing production stats: {e}")
        await message.answer("❌ Xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.")

def register_handlers_production(dp: Dispatcher):
    """Register production handlers"""
    dp.message.register(production_menu, F.text == "🏭 Ishlab chiqarish")
    dp.message.register(new_production_order, F.text == "🔄 Yangi buyurtma")
    dp.message.register(show_production_statistics, F.text == "📊 Ishlab chiqarish statistikasi")
    
    dp.callback_query.register(process_product_selection, 
                               F.data.startswith('product_'),
                               ProductionStates.waiting_product_selection)
    
    dp.message.register(process_quantity, ProductionStates.waiting_quantity)
    
    dp.callback_query.register(confirm_production, 
                               F.data.startswith('confirm_'),
                               ProductionStates.confirm_production)
