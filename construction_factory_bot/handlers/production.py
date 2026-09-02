from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove
from sqlalchemy import func, extract
from datetime import datetime

from database.session import get_db_session
from database.models import (
    Product, RawMaterial, ProductFormula,
    WarehouseTransaction, ProductionOrder,
    TransactionType, OrderStatus
)
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


async def view_in_progress_orders(message: types.Message):
    """Jarayondagi buyurtmalarni ko'rsatish"""
    with get_db_session() as db:
        orders = db.query(ProductionOrder).filter(
            ProductionOrder.status.in_([OrderStatus.PENDING, OrderStatus.IN_PROGRESS])
        ).order_by(ProductionOrder.created_at.desc()).all()

        if not orders:
            await message.answer("📭 Jarayonda buyurtmalar mavjud emas.", reply_markup=get_production_menu())
            return

        text = "📋 **JARAYONDAGI BUYURTMALAR**\n\n"
        for order in orders:
            product = db.query(Product).filter(Product.id == order.product_id).first()
            product_name = product.name if product else "Noma'lum"
            status_text = order.status.value if order.status else "jarayonda"
            text += (
                f"📋 **{order.order_number or '#' + str(order.id)}**\n"
                f"   🏭 {product_name} x {order.quantity}\n"
                f"   📊 Holat: {status_text}\n"
                f"   💰 Xarajat: {order.total_cost:,.0f} so'm\n\n"
            )
        text += f"📊 Jami: {len(orders)} ta buyurtma"
        await message.answer(text, parse_mode="Markdown", reply_markup=get_production_menu())


async def view_completed_orders(message: types.Message):
    """Tayyor buyurtmalarni ko'rsatish"""
    with get_db_session() as db:
        orders = db.query(ProductionOrder).filter(
            ProductionOrder.status == OrderStatus.COMPLETED
        ).order_by(ProductionOrder.created_at.desc()).limit(10).all()

        if not orders:
            await message.answer("📭 Tayyor buyurtmalar mavjud emas.", reply_markup=get_production_menu())
            return

        text = "✅ **TAYYOR BUYURTMALAR**\n\n"
        for order in orders:
            product = db.query(Product).filter(Product.id == order.product_id).first()
            product_name = product.name if product else "Noma'lum"
            text += (
                f"✅ **{order.order_number or '#' + str(order.id)}**\n"
                f"   🏭 {product_name} x {order.quantity}\n"
                f"   💰 Xarajat: {order.total_cost:,.0f} so'm\n"
                f"   📅 {order.created_at.strftime('%d.%m.%Y') if order.created_at else ''}\n\n"
            )
        await message.answer(text, parse_mode="Markdown", reply_markup=get_production_menu())


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

        with get_db_session() as db:
            product = db.query(Product).filter(Product.name == product_name).first()

            if product:
                await state.update_data(product_id=product.id, product_name=product_name)

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

        product_id = data['product_id']

        with get_db_session() as db:
            # Mahsulot formulasi bo'yicha xarajatlarni hisoblash
            formula_items = db.query(
                RawMaterial.name,
                RawMaterial.current_stock,
                ProductFormula.quantity.label('required_per_unit'),
                RawMaterial.price_per_unit,
                RawMaterial.id.label('material_id')
            ).join(
                RawMaterial, ProductFormula.raw_material_id == RawMaterial.id
            ).filter(
                ProductFormula.product_id == product_id
            ).all()

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
                required_total = item.required_per_unit * quantity
                available = item.current_stock
                material_cost = required_total * item.price_per_unit
                total_cost += material_cost

                status = "✅ Yetarli" if available >= required_total else "❌ Yetarli emas"

                if available < required_total:
                    can_produce = False
                    missing_materials.append({
                        'name': item.name,
                        'required': required_total,
                        'available': available,
                        'deficit': required_total - available
                    })

                response += (
                    f"• **{item.name}**: {required_total:,.0f} kg kerak "
                    f"(mavjud: {available:,.0f} kg) - {status}\n"
                )

            # Mehnat va energiya xarajatlari (taxminiy)
            labor_cost = total_cost * 0.3
            energy_cost = total_cost * 0.1
            total_with_overhead = total_cost + labor_cost + energy_cost
            unit_cost = total_with_overhead / quantity

            # Mahsulot narxini olish
            product = db.query(Product).filter(Product.id == product_id).first()
            selling_price = product.selling_price

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
                    response += f"• {material['name']}: {material['deficit']:,.0f} kg yetishmayapti\n"
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
            with get_db_session() as db:
                # Order raqamini yaratish
                today = datetime.now()
                order_count = db.query(ProductionOrder).filter(
                    extract('year', ProductionOrder.created_at) == today.year,
                    extract('month', ProductionOrder.created_at) == today.month
                ).count() + 1
                order_number = f"PO-{today.strftime('%Y%m')}-{order_count:04d}"

                # Ishlab chiqarish buyurtmasini yaratish
                new_order = ProductionOrder(
                    order_number=order_number,
                    product_id=data['product_id'],
                    quantity=data['quantity'],
                    total_cost=data['total_cost'],
                    status=OrderStatus.IN_PROGRESS
                )
                db.add(new_order)
                db.flush()  # ID ni olish

                order_id = new_order.id

                # Xom ashyolarni ishlatish (ombordan chiqim)
                formula_items = db.query(
                    ProductFormula.raw_material_id,
                    ProductFormula.quantity.label('required_per_unit')
                ).filter(
                    ProductFormula.product_id == data['product_id']
                ).all()

                for item in formula_items:
                    required_total = item.required_per_unit * data['quantity']

                    # Ombordagi harakatni kiritish
                    transaction = WarehouseTransaction(
                        product_id=data['product_id'],
                        raw_material_id=item.raw_material_id,
                        quantity=required_total,
                        transaction_type=TransactionType.PRODUCTION,
                        user_id=callback_query.from_user.id,
                        notes=f"Ishlab chiqarish buyurtmasi #{order_id}"
                    )
                    db.add(transaction)

                    # Xom ashyo zaxirasini kamaytirish
                    material = db.query(RawMaterial).filter(
                        RawMaterial.id == item.raw_material_id
                    ).first()
                    if material:
                        material.current_stock -= required_total

                # Buyurtmani 'tayyor' holatiga o'tkazish
                new_order.status = OrderStatus.COMPLETED
                new_order.actual_end = datetime.utcnow()

                db.commit()

                response = (
                    f"✅ **ISHLAB CHIQARISH MUVOFAQQIYATLI BAJARILDI!**\n\n"
                    f"📋 Buyurtma raqами: {order_number}\n"
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
        with get_db_session() as db:
            stats = db.query(
                Product.name,
                func.count(ProductionOrder.id).label('order_count'),
                func.sum(ProductionOrder.quantity).label('total_quantity'),
                func.sum(ProductionOrder.total_cost).label('total_cost'),
                func.avg(ProductionOrder.total_cost / ProductionOrder.quantity).label('avg_unit_cost')
            ).join(
                Product, ProductionOrder.product_id == Product.id
            ).filter(
                ProductionOrder.status == OrderStatus.COMPLETED
            ).group_by(
                Product.name
            ).order_by(
                func.sum(ProductionOrder.quantity).desc()
            ).all()

            if not stats:
                await message.answer("📭 Hali ishlab chiqarish statistikasi mavjud emas.")
                return

            response = "📊 **ISHLAB CHIQARISH STATISTIKASI**\n\n"

            total_all = 0
            cost_all = 0

            for row in stats:
                response += (
                    f"🏭 **{row.name}:**\n"
                    f"• Buyurtmalar: {row.order_count} ta\n"
                    f"• Jami miqdor: {row.total_quantity:,.0f} birlik\n"
                    f"• Jami xarajat: {row.total_cost:,.0f} so'm\n"
                    f"• O'rtacha birlik xarajati: {row.avg_unit_cost:,.0f} so'm\n\n"
                )

                total_all += row.total_quantity or 0
                cost_all += row.total_cost or 0

            avg_cost = cost_all / total_all if total_all > 0 else 0
            response += (
                f"📈 **UMUMIY KO'RSATKICHLAR:**\n"
                f"• Jami ishlab chiqarilgan: {total_all:,.0f} birlik\n"
                f"• Jami xarajat: {cost_all:,.0f} so'm\n"
                f"• O'rtacha xarajat/birlik: {avg_cost:,.0f} so'm"
            )

        await message.answer(response, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error showing production stats: {e}")
        await message.answer("❌ Xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.")


def register_handlers_production(dp: Dispatcher):
    """Register production handlers"""
    dp.message.register(production_menu, F.text == "🏭 Ishlab chiqarish")
    dp.message.register(new_production_order, F.text == "🔄 Yangi buyurtma")
    dp.message.register(view_in_progress_orders, F.text == "📋 Jarayondagilar")
    dp.message.register(view_completed_orders, F.text == "✅ Tayyor buyurtmalar")
    dp.message.register(show_production_statistics, F.text == "📊 Ishlab chiqarish statistikasi")

    dp.callback_query.register(process_product_selection,
                               F.data.startswith('product_'),
                               ProductionStates.waiting_product_selection)

    dp.message.register(process_quantity, ProductionStates.waiting_quantity)

    dp.callback_query.register(confirm_production,
                               F.data.startswith('confirm_'),
                               ProductionStates.confirm_production)
