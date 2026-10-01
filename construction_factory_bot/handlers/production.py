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
from keyboards.main_menu import (get_main_menu, get_production_menu, get_products_keyboard,
                                  get_confirm_keyboard, get_qc_status_keyboard)
from database import crud
import logging

logger = logging.getLogger(__name__)


class ProductionStates(StatesGroup):
    waiting_product_selection = State()
    waiting_quantity = State()
    confirm_production = State()
    qc_waiting_order = State()      # sifat nazorati: buyurtma raqami kiritilmoqda
    qc_waiting_status = State()     # sifat nazorati: natija tanlanmoqda
    qc_waiting_rejected = State()   # sifat nazorati: rad etilgan miqdor kiritilmoqda
    qc_confirm = State()            # sifat nazorati: tasdiqlash


async def production_menu(message: types.Message):
    """Ishlab chiqarish menyusi"""
    from utils.access import ensure_access
    if not await ensure_access(message, "production"):
        return
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
    from utils.access import ensure_access
    if not await ensure_access(message, "production", edit=True):
        return
    await message.answer("Mahsulot turini tanlang:", reply_markup=get_products_keyboard())
    await ProductionStates.waiting_product_selection.set()


async def process_product_selection(callback_query: types.CallbackQuery, state: FSMContext):
    """Mahsulotni tanlash"""
    await callback_query.answer()

    try:
        product_id = int(callback_query.data.replace("product_", ""))
    except (ValueError, TypeError):
        await callback_query.message.answer("❌ Noto'g'ri tanlov.")
        await state.clear()
        return

    with get_db_session() as db:
        product = db.query(Product).filter(Product.id == product_id).first()

        if product:
            await state.update_data(product_id=product.id, product_name=product.name)

            await callback_query.message.answer(
                f"✅ Tanlangan mahsulot: {product.name}\n\n"
                f"📦 Necha birlik ishlab chiqarmoqchisiz?",
                reply_markup=ReplyKeyboardRemove()
            )
            await ProductionStates.waiting_quantity.set()
        else:
            await callback_query.message.answer("❌ Mahsulot topilmadi.")
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


# =============== SIFAT NAZORATI (QC) — TAYYOR MAHSULOT CHIQISHI ===============
# TZ: "Chiqishda mahsulot sinovdan o'tkaziladi, natija raqamli dalolatnomaga yoziladi"
# Qabul qilingan qism omborga kiradi, rad etilgan qism brak omboriga o'tadi.

_QC_STATUS_TEXT = {
    "✅ Qabul qilindi": "qabul_qilingan",
    "⚠️ Qisman qabul": "qisman",
    "❌ Rad etilgan": "rad_etilgan",
}


def _fmt_qty(value) -> str:
    """Miqdorni chiroyli ko'rsatish"""
    try:
        f = float(value)
        if f.is_integer():
            return f"{int(f):,}".replace(",", " ")
        return f"{f:,.2f}".rstrip("0").rstrip(".").replace(",", " ")
    except (TypeError, ValueError):
        return str(value)


async def qc_start(message: types.Message, state: FSMContext):
    """🔬 Sifat nazorati — QC o'tkazilmagan tayyor buyurtmalar ro'yxati"""
    from utils.access import ensure_access
    if not await ensure_access(message, "production", edit=True):
        return
    await state.clear()

    with get_db_session() as db:
        orders = crud.list_production_orders_pending_qc(db, limit=20)
        if not orders:
            await message.answer(
                "🔬 <b>Sifat nazorati</b>\n\n"
                "📭 Sifat nazorati kutilayotgan tayyor buyurtma yo'q.\n"
                "Avval yangi ishlab chiqarish buyurtmasini yakunlang.",
                reply_markup=get_production_menu(), parse_mode="HTML",
            )
            return

        text = "🔬 <b>SIFAT NAZORATI — TAYYOR BUYURTMALAR</b>\n\n"
        text += "Qaysi buyurtma tekshiriladi? Buyurtma <b>ID</b> sini yuboring:\n\n"
        for o in orders:
            product = db.query(Product).filter(Product.id == o.product_id).first()
            pname = product.name if product else "Noma'lum"
            text += (
                f"🆔 <b>{o.id}</b> — {o.order_number}\n"
                f"   🏭 {pname} x {_fmt_qty(o.quantity)}\n"
                f"   📅 {o.actual_end.strftime('%d.%m.%Y') if o.actual_end else ''}\n\n"
            )
        await message.answer(text[:3500], reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")
        await ProductionStates.qc_waiting_order.set()


async def qc_pick_order(message: types.Message, state: FSMContext):
    """Buyurtma ID/raqami qabul qilinadi"""
    text = (message.text or "").strip()
    if text in ("❌ Bekor qilish", "⬅️ Orqaga"):
        await message.answer("❌ Sifat nazorati bekor qilindi.", reply_markup=get_production_menu())
        await state.clear()
        return

    with get_db_session() as db:
        if text.isdigit():
            order = db.query(ProductionOrder).filter(ProductionOrder.id == int(text)).first()
        else:
            order = db.query(ProductionOrder).filter(ProductionOrder.order_number == text).first()

        pending_ids = [o.id for o in crud.list_production_orders_pending_qc(db, limit=200)]
        if not order or order.id not in pending_ids:
            await message.answer(
                "❌ Buyurtma topilmadi yoki sifat nazorati allaqachon o'tkazilgan.\n"
                "Qaytadan buyurtma ID sini yuboring yoki ❌ Bekor qilish deb yozing:"
            )
            return

        product = db.query(Product).filter(Product.id == order.product_id).first()
        pname = product.name if product else "Noma'lum"
        await state.update_data(qc_order_id=order.id)
        await message.answer(
            "🔬 <b>SIFAT NAZORATI</b>\n\n"
            f"🧾 Buyurtma: <b>{order.order_number}</b>\n"
            f"🏭 Mahsulot: <b>{pname}</b>\n"
            f"📦 Tekshiriladigan miqdor: <b>{_fmt_qty(order.quantity)}</b>\n\n"
            "Tekshiruv natijasi qanday?",
            reply_markup=get_qc_status_keyboard(), parse_mode="HTML",
        )
        await ProductionStates.qc_waiting_status.set()


async def qc_pick_status(message: types.Message, state: FSMContext):
    """Sifat nazorati natijasi tanlanadi"""
    text = (message.text or "").strip()
    if text == "❌ Bekor qilish":
        await message.answer("❌ Sifat nazorati bekor qilindi.", reply_markup=get_production_menu())
        await state.clear()
        return
    status_key = _QC_STATUS_TEXT.get(text)
    if not status_key:
        await message.answer("❌ Noto'g'ri tanlov. Tugmalardan birini bosing:")
        return

    await state.update_data(qc_status=status_key)
    if status_key == "qisman":
        data = await state.get_data()
        with get_db_session() as db:
            order = db.query(ProductionOrder).filter(
                ProductionOrder.id == data.get("qc_order_id")
            ).first()
        qty = order.quantity if order else 0
        await message.answer(
            f"⚠️ <b>Qisman qabul</b>\n\n"
            f"Nechta birlik <b>rad (brak)</b> chiqdi? "
            f"(0 dan {_fmt_qty(qty)} gacha — raqam kiriting)",
            reply_markup=ReplyKeyboardRemove(), parse_mode="HTML",
        )
        await ProductionStates.qc_waiting_rejected.set()
    else:
        await _qc_show_confirm(message, state)


async def qc_input_rejected(message: types.Message, state: FSMContext):
    """Qisman qabul: rad etilgan miqdor qabul qilinadi"""
    try:
        rejected = float((message.text or "").replace(",", ".").replace(" ", ""))
    except ValueError:
        await message.answer("❌ Raqam kiriting (masalan: 12):")
        return

    data = await state.get_data()
    with get_db_session() as db:
        order = db.query(ProductionOrder).filter(
            ProductionOrder.id == data.get("qc_order_id")
        ).first()
    qty = float(order.quantity or 0) if order else 0

    if rejected <= 0 or rejected >= qty:
        await message.answer(
            f"❌ Rad etilgan miqdor 0 dan katta va {_fmt_qty(qty)} dan kichik bo'lishi kerak. Qayta kiriting:"
        )
        return

    await state.update_data(qc_rejected=rejected)
    await _qc_show_confirm(message, state)


async def _qc_show_confirm(message: types.Message, state: FSMContext):
    """QC natijasini tasdiqlash ekrani"""
    data = await state.get_data()
    status_key = data.get("qc_status", "qabul_qilingan")

    with get_db_session() as db:
        order = db.query(ProductionOrder).filter(
            ProductionOrder.id == data.get("qc_order_id")
        ).first()
        product = db.query(Product).filter(Product.id == order.product_id).first() if order else None
        qty = float(order.quantity or 0) if order else 0

        if status_key == "qisman":
            rejected = float(data.get("qc_rejected") or 0)
        elif status_key == "rad_etilgan":
            rejected = qty
        else:
            rejected = 0.0
        accepted = qty - rejected

        status_label = crud.QC_STATUS_LABELS.get(status_key, status_key)
        pname = product.name if product else "Noma'lum"
        await message.answer(
            "🔬 <b>SIFAT NAZORATI — TASDIQLASH</b>\n\n"
            f"🧾 Buyurtma: {order.order_number if order else '-'}\n"
            f"🏭 Mahsulot: <b>{pname}</b>\n"
            f"📦 Tekshirilgan: <b>{_fmt_qty(qty)}</b>\n"
            f"✅ Qabul: <b>{_fmt_qty(accepted)}</b>\n"
            f"🏚️ Brak (rad): <b>{_fmt_qty(rejected)}</b>\n"
            f"📋 Natija: {status_label}\n\n"
            "Tasdiqlaysizmi?",
            reply_markup=get_confirm_keyboard(), parse_mode="HTML",
        )
        await ProductionStates.qc_confirm.set()


async def qc_confirm_result(callback_query: types.CallbackQuery, state: FSMContext):
    """QC aktini yakunlash (✅ Tasdiqlash / ❌ Bekor qilish tugmalari orqali)"""
    await callback_query.answer()
    data = await state.get_data()

    if callback_query.data != "confirm_yes":
        await callback_query.message.answer(
            "❌ Sifat nazorati bekor qilindi.", reply_markup=get_production_menu()
        )
        await state.clear()
        return

    try:
        with get_db_session() as db:
            rejected = data.get("qc_rejected")
            qc = crud.create_production_qc(
                db,
                order_id=data.get("qc_order_id"),
                quality_status=data.get("qc_status", "qabul_qilingan"),
                rejected_qty=float(rejected) if rejected is not None else None,
                created_by=callback_query.from_user.full_name if callback_query.from_user else None,
                user_id=callback_query.from_user.id if callback_query.from_user else 0,
            )
            order = db.query(ProductionOrder).filter(
                ProductionOrder.id == qc.order_id
            ).first()
            product = db.query(Product).filter(Product.id == qc.product_id).first()
            pname = product.name if product else "Noma'lum"

            await callback_query.message.answer(
                "📄 <b>SIFAT NAZORATI AKTI</b>\n\n"
                f"🧾 Akt: <b>{qc.act_number}</b>\n"
                f"🧾 Buyurtma: {order.order_number if order else '-'}\n"
                f"🏭 Mahsulot: {pname}\n"
                f"📦 Tekshirilgan: {_fmt_qty(qc.quantity_checked)}\n"
                f"✅ Qabul: <b>{_fmt_qty(qc.accepted_qty)}</b> → omborga kirdi\n"
                f"🏚️ Brak: <b>{_fmt_qty(qc.rejected_qty)}</b> → brak omboriga o'tdi\n"
                f"📋 Natija: {crud.QC_STATUS_LABELS.get(qc.quality_status, qc.quality_status)}\n",
                reply_markup=get_main_menu(), parse_mode="HTML",
            )
    except ValueError as e:
        await callback_query.message.answer(f"⛔ {str(e)}", reply_markup=get_production_menu())
    except Exception as e:
        await callback_query.message.answer(
            f"❌ Xatolik yuz berdi: {str(e)}", reply_markup=get_production_menu()
        )

    await state.clear()


async def qc_history(message: types.Message):
    """📋 QC tarixi — so'nggi sifat nazorati aktlari"""
    from utils.access import ensure_access
    if not await ensure_access(message, "production"):
        return

    with get_db_session() as db:
        acts = crud.list_production_qc_acts(db, limit=10)
        if not acts:
            await message.answer("📭 Sifat nazorati aktlari yo'q.", reply_markup=get_production_menu())
            return

        text = "🔬 <b>SIFAT NAZORATI AKTLARI (so'nggi 10):</b>\n\n"
        for qc in acts:
            product = db.query(Product).filter(Product.id == qc.product_id).first()
            pname = product.name if product else "Noma'lum"
            label = crud.QC_STATUS_LABELS.get(qc.quality_status, qc.quality_status)
            text += (
                f"📄 <b>{qc.act_number}</b> | {label}\n"
                f"   🏭 {pname} x {_fmt_qty(qc.quantity_checked)} | "
                f"✅ {_fmt_qty(qc.accepted_qty)} / 🏚️ {_fmt_qty(qc.rejected_qty)}\n"
                f"   📅 {qc.created_at.strftime('%d.%m.%Y %H:%M') if qc.created_at else ''} | "
                f"👤 {qc.created_by or '-'}\n\n"
            )
        await message.answer(text[:3500], reply_markup=get_production_menu(), parse_mode="HTML")


def register_handlers_production(dp: Dispatcher):
    """Register production handlers"""
    dp.message.register(production_menu, F.text == "🏭 Ishlab chiqarish")
    dp.message.register(new_production_order, F.text == "🔄 Yangi buyurtma")
    dp.message.register(view_in_progress_orders, F.text == "📋 Jarayondagilar")
    dp.message.register(view_completed_orders, F.text == "✅ Tayyor buyurtmalar")
    dp.message.register(show_production_statistics, F.text == "📊 Ishlab chiqarish statistikasi")
    dp.message.register(qc_start, F.text == "🔬 Sifat nazorati")
    dp.message.register(qc_history, F.text == "📋 QC tarixi")

    # QC FSM: buyurtma tanlash -> natija -> (qisman) rad miqdori -> tasdiqlash
    dp.message.register(qc_pick_order, ProductionStates.qc_waiting_order)
    dp.message.register(qc_pick_status, ProductionStates.qc_waiting_status)
    dp.message.register(qc_input_rejected, ProductionStates.qc_waiting_rejected)
    dp.callback_query.register(qc_confirm_result, F.data.startswith("confirm_"),
                               ProductionStates.qc_confirm)

    dp.callback_query.register(process_product_selection,
                               F.data.startswith('product_'),
                               ProductionStates.waiting_product_selection)

    dp.message.register(process_quantity, ProductionStates.waiting_quantity)

    dp.callback_query.register(confirm_production,
                               F.data.startswith('confirm_'),
                               ProductionStates.confirm_production)
