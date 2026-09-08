from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove
from sqlalchemy import func

from database.session import get_db_session
from database.models import RawMaterial, Product, WarehouseTransaction, TransactionType, ProductPriceHistory
from database import crud_v5
from keyboards.main_menu import get_main_menu, get_confirm_keyboard
import logging

logger = logging.getLogger(__name__)


class WarehouseStates(StatesGroup):
    waiting_material_name = State()
    waiting_material_quantity = State()
    waiting_material_price = State()
    confirm_add_material = State()


async def show_price_history(message: types.Message):
    """Narx tarixi (TZ: 'Sana bo'yicha narx tarixi') — so'nggi o'zgarishlar"""
    from utils.access import ensure_access
    if not await ensure_access(message, "warehouse"):
        return
    try:
        with get_db_session() as db:
            history = crud_v5.list_price_history(db, limit=15)
            if not history:
                await message.answer(
                    "💱 Narx tarixi bo'sh.\n\n"
                    "Narx o'zgarishlari web dashboard (Mahsulotlar → narxni o'zgartirish) "
                    "yoki API orqali yoziladi."
                )
                return
            lines = ["💱 *So'nggi narx o'zgarishlari:*\n"]
            for h in history:
                old = f"{h['old_price']:,.0f}" if h.get("old_price") is not None else "—"
                typ = {"selling": "sotuv", "wholesale": "ulgurji",
                       "retail": "chakana", "cost": "tannarx"}.get(h["price_type"], h["price_type"])
                lines.append(
                    f"▫️ {h['product_name']} ({typ})\n"
                    f"   {old} → {h['new_price']:,.0f} so'm\n"
                    f"   🕐 {h['changed_at'][:16].replace('T', ' ')} | {h['changed_by'] or '—'}\n"
                )
            await message.answer("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.exception("Narx tarixi ko'rsatishda xatolik")
        await message.answer(f"❌ Xatolik: {e}")


async def show_warehouse_status(message: types.Message):
    """Ombordagi holatni ko'rsatish"""
    from utils.access import ensure_access
    if not await ensure_access(message, "warehouse"):
        return

    try:
        with get_db_session() as db:
            # Xom ashyolar holati
            raw_materials = db.query(RawMaterial).order_by(RawMaterial.name).all()

            # Tayyor mahsulotlar holati (ishlab chiqarilgan va sotilgan)
            products = db.query(Product).filter(Product.is_active == True).all()

            # Xom ashyolarni formatlash
            raw_materials_text = ""
            total_raw_materials = 0
            for mat in raw_materials:
                total_raw_materials += mat.current_stock
                if mat.current_stock < mat.min_stock:
                    status_icon = "🔴"
                    status_text = "Yetarli emas"
                elif mat.current_stock < mat.min_stock * 1.5:
                    status_icon = "🟡"
                    status_text = "Ozgina"
                else:
                    status_icon = "🟢"
                    status_text = "Yetarli"

                raw_materials_text += (
                    f"{status_icon} **{mat.name}**: "
                    f"{mat.current_stock:,.0f} {mat.unit} "
                    f"(minimum: {mat.min_stock:,.0f} {mat.unit}) [{status_text}]\n"
                )

            # Mahsulotlarni formatlash
            products_text = ""
            total_products_value = 0
            for prod in products:
                produced = db.query(func.coalesce(func.sum(WarehouseTransaction.quantity), 0)).filter(
                    WarehouseTransaction.product_id == prod.id,
                    WarehouseTransaction.transaction_type == TransactionType.PRODUCTION
                ).scalar()
                sold = db.query(func.coalesce(func.sum(WarehouseTransaction.quantity), 0)).filter(
                    WarehouseTransaction.product_id == prod.id,
                    WarehouseTransaction.transaction_type == TransactionType.SALE
                ).scalar()
                in_stock = produced - sold
                total_products_value += produced * prod.selling_price

                products_text += (
                    f"📦 **{prod.name}**: "
                    f"{in_stock:,.0f} {prod.unit} mavjud\n"
                    f"   💰 Narxi: {prod.selling_price:,.0f} so'm\n"
                    f"   📊 Ishlab chiqarilgan: {produced:,.0f}, Sotilgan: {sold:,.0f}\n\n"
                )

            # Umumiy statistika
            response = (
                "🏭 **KORXONA OMBORI HOLATI**\n\n"

                "📦 **XOM ASHYOLAR:**\n"
                f"{raw_materials_text}\n"

                "🏗️ **TAYYOR MAHSULOTLAR:**\n"
                f"{products_text}\n"

                "📊 **UMUMIY STATISTIKA:**\n"
                f"• Xom ashyo: {total_raw_materials:,.0f} birlik\n"
                f"• Mahsulotlar qiymati: {total_products_value:,.0f} so'm\n\n"

                "⚠️ **OGOHLANTIRISH:** Qizil rangda ko'rsatilgan materiallar yetarli emas!"
            )

        await message.answer(response, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error showing warehouse status: {e}")
        await message.answer("❌ Xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.")


async def add_raw_material_start(message: types.Message):
    """Yangi xom ashyo qo'shishni boshlash"""
    from utils.access import ensure_access
    if not await ensure_access(message, "warehouse", edit=True):
        return
    await message.answer("Yangi xom ashyo nomini kiriting:", reply_markup=ReplyKeyboardRemove())
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
            f"💰 Narxi: {price:,.0f} so'm\n\n"
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
            with get_db_session() as db:
                # Tekshirish - allaqachon mavjudmi?
                existing = db.query(RawMaterial).filter(
                    RawMaterial.name == data['material_name']
                ).first()

                if existing:
                    await callback_query.message.answer(
                        "❌ Bu nomdagi xom ashyo allaqachon mavjud!",
                        reply_markup=get_main_menu()
                    )
                else:
                    new_material = RawMaterial(
                        name=data['material_name'],
                        unit=data['unit'],
                        price_per_unit=data['price']
                    )
                    db.add(new_material)
                    db.commit()

                    await callback_query.message.answer(
                        f"✅ '{data['material_name']}' xom ashyosi muvaffaqiyatli qo'shildi!",
                        reply_markup=get_main_menu()
                    )

        except Exception as e:
            logger.error(f"Error adding raw material: {e}")
            await callback_query.message.answer(
                "❌ Xatolik yuz berdi.",
                reply_markup=get_main_menu()
            )
    else:
        await callback_query.message.answer(
            "❌ Xom ashyo qoʻshish bekor qilindi.",
            reply_markup=get_main_menu()
        )

    await state.clear()


def register_handlers_warehouse(dp: Dispatcher):
    """Register warehouse handlers"""
    dp.message.register(show_warehouse_status, F.text == "📦 Ombor holati")
    dp.message.register(add_raw_material_start, F.text == "➕ Xom ashyo kiritish")
    dp.message.register(show_price_history, F.text == "💱 Narx tarixi")

    dp.message.register(process_material_name, WarehouseStates.waiting_material_name)
    dp.message.register(process_material_unit, WarehouseStates.waiting_material_quantity)
    dp.message.register(process_material_price, WarehouseStates.waiting_material_price)

    dp.callback_query.register(confirm_add_material,
                               F.data.startswith('confirm_'),
                               WarehouseStates.confirm_add_material)
