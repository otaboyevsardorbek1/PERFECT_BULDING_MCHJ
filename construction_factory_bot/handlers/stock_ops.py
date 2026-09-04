"""
Ombor operatsiyalari moduli — v3
Rezervatsiya, omborlararo ko'chirish, inventarizatsiya, konvertatsiya
"""
from datetime import datetime, timedelta

from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.session import get_db_session
from database import models, crud
from keyboards.main_menu import get_stock_ops_menu, get_main_menu
from utils.access import ensure_access
from utils.helpers import parse_float_input
from config import WAREHOUSE_TYPES


class StockOpsStates(StatesGroup):
    # Rezervatsiya
    waiting_rsv_product = State()
    waiting_rsv_qty = State()
    waiting_rsv_hours = State()
    waiting_rsv_customer = State()
    # Ko'chirish
    waiting_tr_item_type = State()
    waiting_tr_item = State()
    waiting_tr_qty = State()
    waiting_tr_source = State()
    waiting_tr_target = State()
    # Inventarizatsiya
    waiting_inv_type = State()
    waiting_inv_item = State()
    waiting_inv_qty = State()
    # Konvertatsiya
    waiting_cv_product = State()
    waiting_cv_from = State()
    waiting_cv_qty = State()
    waiting_cv_to = State()


# =============== ENTRY ===============
async def stock_ops_menu(message: types.Message):
    if not await ensure_access(message, "stock_ops"):
        return
    await message.answer(
        "📦 <b>OMBOR OPERATSIYALARI</b>\n\n"
        "• 🔒 Rezervatsiya — mahsulotni 2-24 soatga bloklash\n"
        "• 🔄 Ko'chirish — omborlararo tovar harakati\n"
        "• 📋 Inventarizatsiya — qoldiqni sanab tekshirish\n"
        "• 💱 Konvertatsiya — o'lchov birliklarini o'zgartirish",
        reply_markup=get_stock_ops_menu(), parse_mode="HTML"
    )


def _product_keyboard(db, prefix: str, label_price: bool = False):
    products = db.query(models.Product).filter(models.Product.is_active == True).order_by(
        models.Product.name
    ).all()
    rows = []
    for p in products:
        available = crud.get_available_product_qty(db, p.id)
        text = f"{p.name} (mavjud: {available:,.0f} {p.unit})"
        if label_price:
            text += f" | {p.selling_price:,.0f} so'm"
        rows.append([types.InlineKeyboardButton(text=text, callback_data=f"{prefix}_{p.id}")])
    return rows


# =====================================================
#  REZERVATSIYA
# =====================================================
async def reservation_create_start(message: types.Message, state: FSMContext):
    if not await ensure_access(message, "stock_ops", edit=True):
        return
    await state.clear()
    with get_db_session() as db:
        rows = _product_keyboard(db, "rsvp")
    if not rows:
        await message.answer("❌ Mahsulotlar yo'q.", reply_markup=get_stock_ops_menu())
        return
    await message.answer("🔒 <b>REZERVATSIYA</b>\n\nQaysi mahsulotni bloklash kerak?",
                         reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows),
                         parse_mode="HTML")
    await StockOpsStates.waiting_rsv_product.set()


async def rsv_pick_product(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    pid = int(callback.data.replace("rsvp_", ""))
    await state.update_data(rsv_product_id=pid)
    await callback.message.answer("📦 Nechta birlik bloklanadi?")
    await StockOpsStates.waiting_rsv_qty.set()


async def rsv_qty(message: types.Message, state: FSMContext):
    qty = parse_float_input(message.text)
    if qty is None:
        await message.answer("❌ Faqat raqam kiriting:")
        return
    if qty <= 0:
        await message.answer("❌ Miqdor 0 dan katta bo'lishi kerak:")
        return
    await state.update_data(rsv_qty=qty)
    rows = [
        [types.InlineKeyboardButton(text="⏰ 2 soat", callback_data="hours_2"),
         types.InlineKeyboardButton(text="⏰ 6 soat", callback_data="hours_6")],
        [types.InlineKeyboardButton(text="⏰ 12 soat", callback_data="hours_12"),
         types.InlineKeyboardButton(text="⏰ 24 soat", callback_data="hours_24")],
    ]
    await message.answer("⏳ Qancha muddatga bloklanadi?",
                         reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows))
    await StockOpsStates.waiting_rsv_hours.set()


async def rsv_hours(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    hours = int(callback.data.replace("hours_", ""))
    data = await state.get_data()
    with get_db_session() as db:
        result = crud.create_reservation(
            db,
            product_id=data["rsv_product_id"],
            quantity=data["rsv_qty"],
            expires_in_hours=hours,
            customer_name=callback.from_user.full_name,
            created_by=callback.from_user.full_name,
        )
        if "error" in result:
            await callback.message.answer(f"❌ {result['error']}", reply_markup=get_stock_ops_menu())
            await state.clear()
            return
        r = result["reservation"]
        crud.create_system_log(db, user_id=callback.from_user.id,
                               user_name=callback.from_user.full_name,
                               action=f"Rezervatsiya: {r.reservation_code}",
                               module="stock_ops")
        product = db.query(models.Product).filter(models.Product.id == r.product_id).first()
    await state.clear()
    await callback.message.answer(
        f"✅ <b>REZERVATSIYA YARATILDI!</b>\n\n"
        f"📋 Kod: {r.reservation_code}\n"
        f"🏭 Mahsulot: {product.name}\n"
        f"📦 Miqdor: {r.quantity:,.0f} {product.unit}\n"
        f"⏳ Muddati: {r.expires_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"⚠️ Mijoz to'lamasa, muddat tugagach avtomatik bo'shatiladi.",
        reply_markup=get_stock_ops_menu(), parse_mode="HTML"
    )


async def reservations_active(message: types.Message):
    with get_db_session() as db:
        reservations = crud.list_active_reservations(db)
        if not reservations:
            await message.answer("📭 Faol rezervatsiyalar yo'q.", reply_markup=get_stock_ops_menu())
            return
        text = "📋 <b>REZERVATSIYALAR</b>\n\n"
        for r in reservations:
            product = db.query(models.Product).filter(models.Product.id == r.product_id).first()
            status_icon = "🟢" if r.status == "faol" else "⚪"
            text += (
                f"{status_icon} <b>{r.reservation_code}</b>\n"
                f"   🏭 {product.name if product else '?'} x {r.quantity:,.0f}\n"
                f"   ⏳ Tugaydi: {r.expires_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"   📌 Holat: {r.status}\n"
            )
            if r.status == "faol":
                text += f"   👤 {r.customer_name or '-'}\n"
            text += "\n"
        await message.answer(text[:4000], reply_markup=get_stock_ops_menu(), parse_mode="HTML")


# =====================================================
#  KO'CHIRISH
# =====================================================
async def transfer_create_start(message: types.Message, state: FSMContext):
    if not await ensure_access(message, "stock_ops", edit=True):
        return
    await state.clear()
    rows = [
        [types.InlineKeyboardButton(text="🧱 Xom ashyo", callback_data="ttype_raw")],
        [types.InlineKeyboardButton(text="📦 Tayyor mahsulot", callback_data="ttype_product")],
    ]
    await message.answer("🔄 <b>KO'CHIRISH</b>\n\nNimani ko'chirish kerak?",
                         reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows),
                         parse_mode="HTML")
    await StockOpsStates.waiting_tr_item_type.set()


async def tr_pick_type(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    item_type = callback.data.replace("ttype_", "")
    await state.update_data(tr_type=item_type)
    with get_db_session() as db:
        if item_type == "raw":
            items = db.query(models.RawMaterial).order_by(models.RawMaterial.name).all()
            rows = [[types.InlineKeyboardButton(
                text=f"{m.name} ({m.current_stock:,.0f} {m.unit})", callback_data=f"titem_{m.id}"
            )] for m in items]
        else:
            rows = _product_keyboard(db, "titem")
    if not rows:
        await message.answer("❌ Element yo'q.", reply_markup=get_stock_ops_menu())
        return
    await message.answer("Qaysi element ko'chiriladi?",
                         reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows))
    await StockOpsStates.waiting_tr_item.set()


async def tr_pick_item(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    item_id = int(callback.data.replace("titem_", ""))
    await state.update_data(tr_item_id=item_id)
    await callback.message.answer("📦 Miqdorni kiriting:")
    await StockOpsStates.waiting_tr_qty.set()


async def tr_qty(message: types.Message, state: FSMContext):
    qty = parse_float_input(message.text)
    if qty is None:
        await message.answer("❌ Faqat raqam kiriting:")
        return
    if qty <= 0:
        await message.answer("❌ Miqdor 0 dan katta bo'lishi kerak:")
        return
    await state.update_data(tr_qty=qty)
    rows = [[types.InlineKeyboardButton(text=w.title(), callback_data=f"src_{w}")]
            for w in WAREHOUSE_TYPES]
    await message.answer("📍 Qayerdan? (manba ombor)",
                         reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows))
    await StockOpsStates.waiting_tr_source.set()


async def tr_source(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    source = callback.data.replace("src_", "")
    await state.update_data(tr_source=source)
    rows = [[types.InlineKeyboardButton(text=w.title(), callback_data=f"dst_{w}")]
            for w in WAREHOUSE_TYPES if w != source]
    await message.answer("📍 Qayerga? (maqsad ombor)",
                         reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows))
    await StockOpsStates.waiting_tr_target.set()


async def tr_target(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    target = callback.data.replace("dst_", "")
    data = await state.get_data()
    with get_db_session() as db:
        result = crud.create_transfer(
            db, item_type=data["tr_type"], item_id=data["tr_item_id"],
            quantity=data["tr_qty"],
            source_warehouse=data["tr_source"],
            target_warehouse=target,
            notes=f"{data['tr_source']} → {target}",
            user_id=callback.from_user.id,
            user_name=callback.from_user.full_name,
        )
        if "error" in result:
            await callback.message.answer(f"❌ {result['error']}", reply_markup=get_stock_ops_menu())
            await state.clear()
            return
        t = result["transfer"]
        crud.create_system_log(db, user_id=callback.from_user.id,
                               user_name=callback.from_user.full_name,
                               action=f"Ko'chirish: {t.document_number or t.id}",
                               module="stock_ops")
    await state.clear()
    await callback.message.answer(
        f"✅ <b>KO'CHIRISH BAJARILDI!</b>\n\n"
        f"🔄 {data['tr_source']} → {target}\n"
        f"📦 Miqdor: {data['tr_qty']:,.0f}\n"
        f"📝 Izoh: {data['tr_source']} → {target}",
        reply_markup=get_stock_ops_menu(), parse_mode="HTML"
    )


async def transfers_history(message: types.Message):
    with get_db_session() as db:
        transfers = crud.list_transfers(db)
        if not transfers:
            await message.answer("📭 Ko'chirishlar tarixi bo'sh.", reply_markup=get_stock_ops_menu())
            return
        text = "🔄 <b>KO'CHIRISHLAR TARIXI</b>\n\n"
        for t in transfers:
            text += (
                f"• {t.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"  {t.source_warehouse} → {t.target_warehouse} | {t.quantity:,.0f}\n"
                f"  👤 {t.user_name or '-'} | {t.notes or ''}\n\n"
            )
        await message.answer(text[:4000], reply_markup=get_stock_ops_menu(), parse_mode="HTML")


# =====================================================
#  INVENTARIZATSIYA
# =====================================================
async def inventory_start(message: types.Message, state: FSMContext):
    if not await ensure_access(message, "stock_ops", edit=True):
        return
    await state.clear()
    rows = [
        [types.InlineKeyboardButton(text="🧱 Xom ashyo", callback_data="invtype_raw")],
        [types.InlineKeyboardButton(text="📦 Tayyor mahsulot", callback_data="invtype_product")],
    ]
    await message.answer("📋 <b>INVENTARIZATSIYA</b>\n\nNimani sanab chiqamiz?",
                         reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows),
                         parse_mode="HTML")
    await StockOpsStates.waiting_inv_type.set()


async def inv_pick_type(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    item_type = callback.data.replace("invtype_", "")
    await state.update_data(inv_type=item_type)
    with get_db_session() as db:
        if item_type == "raw":
            items = db.query(models.RawMaterial).order_by(models.RawMaterial.name).all()
            rows = [[types.InlineKeyboardButton(
                text=f"{m.name} (tizimda: {m.current_stock:,.0f} {m.unit})", callback_data=f"invi_{m.id}"
            )] for m in items]
        else:
            rows = _product_keyboard(db, "invi")
    if not rows:
        await message.answer("❌ Element yo'q.", reply_markup=get_stock_ops_menu())
        return
    await message.answer("Qaysi element?",
                         reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows))
    await StockOpsStates.waiting_inv_item.set()


async def inv_pick_item(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    item_id = int(callback.data.replace("invi_", ""))
    await state.update_data(inv_item_id=item_id)
    await callback.message.answer("🔢 Sanab chiqilgan haqiqiy miqdorni kiriting:")
    await StockOpsStates.waiting_inv_qty.set()


async def inv_qty(message: types.Message, state: FSMContext):
    qty = parse_float_input(message.text)
    if qty is None:
        await message.answer("❌ Faqat raqam kiriting:")
        return
    if qty < 0:
        await message.answer("❌ Haqiqiy miqdor manfiy bo'lishi mumkin emas:")
        return
    data = await state.get_data()
    with get_db_session() as db:
        try:
            check = crud.create_inventory_check(
                db, warehouse="asosiy", item_type=data["inv_type"],
                item_id=data["inv_item_id"], actual_quantity=qty,
                created_by=message.from_user.full_name,
            )
            name = "?"
            if data["inv_type"] == "raw":
                item = db.query(models.RawMaterial).filter(models.RawMaterial.id == data["inv_item_id"]).first()
            else:
                item = db.query(models.Product).filter(models.Product.id == data["inv_item_id"]).first()
            name = item.name if item else "?"
            crud.create_system_log(db, user_id=message.from_user.id,
                                   user_name=message.from_user.full_name,
                                   action=f"Inventarizatsiya: {check.check_number}",
                                   module="stock_ops")
        except ValueError as e:
            await message.answer(f"❌ {e}", reply_markup=get_stock_ops_menu())
            await state.clear()
            return
    await state.clear()
    diff_text = (f"➕ Ortiqcha: {check.difference:+,.0f}" if check.difference > 0
                 else f"➖ Yetishmovchilik: {check.difference:,.0f}")
    await message.answer(
        f"📋 <b>INVENTARIZATSIYA NATIJASI</b>\n\n"
        f"🏷️ {name}\n"
        f"📊 Tizimda: {check.system_quantity:,.0f}\n"
        f"🔢 Haqiqiy: {check.actual_quantity:,.0f}\n"
        f"⚖️ Farq: {check.difference:+,.0f}\n"
        f"{'📄 Yetishmovchilik dalolatnomasi tayyorlandi!' if check.act_created and check.difference < 0 else ''}",
        reply_markup=get_stock_ops_menu(), parse_mode="HTML"
    )


# =====================================================
#  KONVERTATSIYA
# =====================================================
async def conversion_start(message: types.Message, state: FSMContext):
    if not await ensure_access(message, "stock_ops"):
        return
    await state.clear()
    with get_db_session() as db:
        rows = _product_keyboard(db, "cvp")
    if not rows:
        await message.answer("❌ Mahsulotlar yo'q.", reply_markup=get_stock_ops_menu())
        return
    await message.answer("💱 <b>KONVERTATSIYA</b>\n\nMahsulotni tanlang:",
                         reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows),
                         parse_mode="HTML")
    await StockOpsStates.waiting_cv_product.set()


async def cv_pick_product(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    pid = int(callback.data.replace("cvp_", ""))
    await state.update_data(cv_product_id=pid)
    with get_db_session() as db:
        units = crud.get_product_units(db, pid)
        product = db.query(models.Product).filter(models.Product.id == pid).first()
        # Asosiy birlikni ham qo'shish
        rows = [[types.InlineKeyboardButton(
            text=f"{u.unit} (1 {u.unit} = {u.factor} {u.base_unit})",
            callback_data=f"cvfrom_{u.unit}"
        )] for u in units]
        if not units:
            rows = [[types.InlineKeyboardButton(
                text=product.unit, callback_data=f"cvfrom_{product.unit}"
            )]]
        await callback.message.answer(f"💱 {product.name}\nQaysi birlikdan?",
                                      reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows))
    await StockOpsStates.waiting_cv_from.set()


async def cv_from(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    unit = callback.data.replace("cvfrom_", "")
    await state.update_data(cv_from_unit=unit)
    await callback.message.answer("🔢 Miqdorni kiriting:")
    await StockOpsStates.waiting_cv_qty.set()


async def cv_qty(message: types.Message, state: FSMContext):
    qty = parse_float_input(message.text)
    if qty is None:
        await message.answer("❌ Faqat raqam kiriting:")
        return
    if qty <= 0:
        await message.answer("❌ Miqdor 0 dan katta bo'lishi kerak:")
        return
    await state.update_data(cv_qty=qty)
    data = await state.get_data()
    with get_db_session() as db:
        units = crud.get_product_units(db, data["cv_product_id"])
        product = db.query(models.Product).filter(models.Product.id == data["cv_product_id"]).first()
        rows = [[types.InlineKeyboardButton(
            text=f"{u.unit} (1 {u.unit} = {u.factor} {u.base_unit})",
            callback_data=f"cvto_{u.unit}"
        )] for u in units if u.unit != data["cv_from_unit"]]
        if not rows and product:
            rows = [[types.InlineKeyboardButton(
                text=product.unit, callback_data=f"cvto_{product.unit}"
            )]]
        await message.answer("Qaysi birlikka?", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows))
    await StockOpsStates.waiting_cv_to.set()


async def cv_to(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    to_unit = callback.data.replace("cvto_", "")
    data = await state.get_data()
    if to_unit == data.get("cv_from_unit"):
        await state.clear()
        await callback.message.answer("❌ Boshqa o'lchov birligi yo'q (bir xil birlikka konvertatsiya qilib bo'lmaydi).",
                                      reply_markup=get_stock_ops_menu())
        return
    with get_db_session() as db:
        result = crud.convert_quantity(db, data["cv_product_id"], data["cv_from_unit"],
                                       data["cv_qty"], to_unit)
    await state.clear()
    if not result or "error" in result:
        await callback.message.answer(f"❌ {result.get('error', 'Xatolik') if result else 'Xatolik'}",
                                      reply_markup=get_stock_ops_menu())
        return
    await callback.message.answer(
        f"💱 <b>KONVERTATSIYA NATIJASI</b>\n\n"
        f"🏭 {result['product_name']}\n"
        f"{result['quantity']:,.0f} {result['from']} = "
        f"<b>{result['result']:,.2f} {result['to']}</b>\n"
        f"(asosiy birlikda: {result['base_quantity']:,.2f})",
        reply_markup=get_stock_ops_menu(), parse_mode="HTML"
    )


# =============== REGISTER ===============
def register_handlers_stock_ops(dp: Dispatcher):
    # Asosiy menyu tugmalari (4 ta) -> ops bo'limi ochiladi
    dp.message.register(stock_ops_menu, F.text.in_(
        ["🔒 Rezervatsiya", "🔄 Ko'chirish", "📋 Inventarizatsiya", "💱 Konvertatsiya"]
    ))

    # Rezervatsiya
    dp.message.register(reservation_create_start, F.text == "🔒 Rezervatsiya yaratish")
    dp.message.register(reservations_active, F.text == "📋 Faol rezervatsiyalar")
    dp.message.register(rsv_qty, StockOpsStates.waiting_rsv_qty)
    dp.callback_query.register(rsv_pick_product, F.data.startswith("rsvp_"),
                               StockOpsStates.waiting_rsv_product)
    dp.callback_query.register(rsv_hours, F.data.startswith("hours_"),
                               StockOpsStates.waiting_rsv_hours)

    # Ko'chirish
    dp.message.register(transfer_create_start, F.text == "🔄 Ko'chirish yaratish")
    dp.message.register(transfers_history, F.text == "📋 Ko'chirishlar tarixi")
    dp.message.register(tr_qty, StockOpsStates.waiting_tr_qty)
    dp.callback_query.register(tr_pick_type, F.data.startswith("ttype_"),
                               StockOpsStates.waiting_tr_item_type)
    dp.callback_query.register(tr_pick_item, F.data.startswith("titem_"),
                               StockOpsStates.waiting_tr_item)
    dp.callback_query.register(tr_source, F.data.startswith("src_"),
                               StockOpsStates.waiting_tr_source)
    dp.callback_query.register(tr_target, F.data.startswith("dst_"),
                               StockOpsStates.waiting_tr_target)

    # Inventarizatsiya
    dp.message.register(inventory_start, F.text == "📋 Inventarizatsiya o'tkazish")
    dp.message.register(inv_qty, StockOpsStates.waiting_inv_qty)
    dp.callback_query.register(inv_pick_type, F.data.startswith("invtype_"),
                               StockOpsStates.waiting_inv_type)
    dp.callback_query.register(inv_pick_item, F.data.startswith("invi_"),
                               StockOpsStates.waiting_inv_item)

    # Konvertatsiya
    dp.message.register(conversion_start, F.text == "💱 Konvertatsiya bajarish")
    dp.message.register(cv_qty, StockOpsStates.waiting_cv_qty)
    dp.callback_query.register(cv_pick_product, F.data.startswith("cvp_"),
                               StockOpsStates.waiting_cv_product)
    dp.callback_query.register(cv_from, F.data.startswith("cvfrom_"),
                               StockOpsStates.waiting_cv_from)
    dp.callback_query.register(cv_to, F.data.startswith("cvto_"),
                               StockOpsStates.waiting_cv_to)
