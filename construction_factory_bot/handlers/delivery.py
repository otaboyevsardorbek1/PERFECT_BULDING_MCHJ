"""
Yetkazib berish (Delivery + GPS) moduli — haydovchi roli

TZ:
- Direktor/sotuvchi sotuvga yetkazish topshirig'i yaratadi va haydovchi tayinlaydi
- Haydovchi: "📋 Mening topshiriqlarim" (marshrut), "🛰️ GPS kuzatuv" (Telegram
  orqali jonli joylashuv -> delivery_locations), "✅ Yetkazib berildi"
- Har bir joylashuv nuqtasi saqlanadi: API/Web orqali xaritada ko'rsatish mumkin

Kirish: asosiy menyu -> 🚚 Yetkazib berish
"""

import html
from datetime import datetime

from aiogram import F, Router, Dispatcher, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from database import crud, crud_v5, crud_v54, models
from database.session import get_db_session
from keyboards.main_menu import get_main_menu
from utils.access import ensure_access, get_user_role

delivery_router = Router()

STATUS_LABELS = crud.DELIVERY_STATUS_LABELS


class DeliveryStates(StatesGroup):
    """Yetkazib berish FSM holatlari"""
    create_sale = State()     # topshiriq uchun sotuv tanlash
    create_driver = State()   # haydovchi tanlash
    create_vehicle = State()  # mashina tanlash (ixtiyoriy)
    tracking = State()        # GPS kuzatuv / yakunlash faol
    cancel_pick = State()     # bekor qilish uchun topshiriq tanlash


def _active_vehicles_rows(db, with_skip: bool = True):
    """Faol mashinalar ro'yxatini inline tugmalarga aylantiradi."""
    vehicles = crud_v5.list_vehicles(db, status="faol")
    rows = []
    for v in vehicles:
        label = crud_v54.vehicle_to_label(v)
        if v.driver_name:
            label += f" (🚚 {v.driver_name})"
        rows.append((label, f"dlv_veh_{v.id}"))
    if with_skip and vehicles:
        rows.append(("🚫 Mashinasiz (keyin tayinlanadi)", "dlv_veh_skip"))
    return rows


def _driver_keyboard() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2, keyboard=[
        [KeyboardButton(text="📋 Mening topshiriqlarim"),
         KeyboardButton(text="🛰️ GPS kuzatuv")],
        [KeyboardButton(text="✅ Yetkazib berildi"),
         KeyboardButton(text="⬅️ Orqaga")],
    ])
    return kb


def _manager_keyboard() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2, keyboard=[
        [KeyboardButton(text="➕ Topshiriq yaratish"),
         KeyboardButton(text="📋 Barcha yetkazishlar")],
        [KeyboardButton(text="⬅️ Orqaga")],
    ])
    return kb


def _gps_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(resize_keyboard=True, row_width=1, keyboard=[
        [KeyboardButton(text="📍 Joylashuvni yuborish", request_location=True)],
        [KeyboardButton(text="⏹️ GPS kuzatuvni to'xtatish")],
    ])


def _inline(rows: list) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=cb)] for t, cb in rows
    ])


def _qty(value) -> str:
    try:
        if float(value).is_integer():
            return f"{int(value):,}".replace(",", " ")
        return f"{float(value):,.2f}".rstrip("0").rstrip(".").replace(",", " ")
    except (TypeError, ValueError):
        return str(value)


def _find_employee(db, telegram_id: int):
    return db.query(models.Employee).filter(
        models.Employee.telegram_id == telegram_id
    ).first()


def _delivery_text(d: models.Delivery, db=None) -> str:
    """Topshiriq matni. db berilsa o'sha sessiya ishlatiladi (mashina nomi uchun)."""
    status = STATUS_LABELS.get(d.status, d.status)
    loc = ""
    if d.current_lat is not None and d.current_lng is not None:
        loc = f"📍 {d.current_lat:.6f}, {d.current_lng:.6f}"
    loc_line = ("   " + loc + "\n") if loc else ""
    veh_line = ""
    if d.vehicle_id:
        v = db.query(models.Vehicle).filter(models.Vehicle.id == d.vehicle_id).first() if db else None
        if v:
            veh_line = f"   🚛 Mashina: {html.escape(crud_v54.vehicle_to_label(v))}\n"
    return (
        f"📄 <b>{d.delivery_number}</b> — {status}\n"
        f"   🏭 {html.escape(d.product_name or '')} x {_qty(d.quantity)} {d.unit or ''}\n"
        f"   👤 {html.escape(d.customer_name or '-')} | 📞 {html.escape(d.customer_phone or '-')}\n"
        f"   🏠 {html.escape(d.customer_address or '-')}\n"
        f"   🚚 Haydovchi: {html.escape(d.driver_name or '-')}\n"
        f"{veh_line}"
        f"{loc_line}"
    )


# ==================== KIRISH ====================

@delivery_router.message(F.text == "🚚 Yetkazib berish", StateFilter(None))
async def delivery_menu(message: Message, state: FSMContext):
    """Yetkazib berish menyusi — rolga qarab haydovchi/menejer ko'rinishi"""
    if not await ensure_access(message, "delivery", edit=True):
        return
    await state.clear()

    with get_db_session() as db:
        role = get_user_role(db, message.from_user.id)

    if role == "haydovchi":
        text = (
            "🚚 <b>YETKAZIB BERISH</b>\n\n"
            "• 📋 Mening topshiriqlarim — yo'nalish va mijoz ma'lumotlari\n"
            "• 🛰️ GPS kuzatuv — joylashuvni yuborib, yetkazishni kuzatish\n"
            "• ✅ Yetkazib berildi — topshiriqni yakunlash"
        )
        await message.answer(text, reply_markup=_driver_keyboard(), parse_mode="HTML")
    else:
        text = (
            "🚚 <b>YETKAZIB BERISH</b>\n\n"
            "• ➕ Topshiriq yaratish — sotuvga haydovchi tayinlash\n"
            "• 📋 Barcha yetkazishlar — holati va GPS kuzatuvi"
        )
        await message.answer(text, reply_markup=_manager_keyboard(), parse_mode="HTML")


# ==================== HAYDOVCHI: TOPSHIRIQLAR ====================

@delivery_router.message(F.text == "📋 Mening topshiriqlarim", StateFilter(None))
async def driver_my_deliveries(message: Message):
    """Haydovchiga biriktirilgan faol topshiriqlar (marshrut ro'yxati)"""
    if not await ensure_access(message, "delivery"):
        return
    with get_db_session() as db:
        emp = _find_employee(db, message.from_user.id)
        if not emp:
            await message.answer("❌ Profil topilmadi. Administratorga murojaat qiling.",
                                 reply_markup=_driver_keyboard())
            return
        items = db.query(models.Delivery).filter(
            models.Delivery.driver_id == emp.id,
            models.Delivery.status.in_(["tayinlangan", "yo'lda"]),
        ).order_by(models.Delivery.created_at.asc()).all()
        if not items:
            await message.answer("📭 Sizga biriktirilgan faol topshiriqlar yo'q.",
                                 reply_markup=_driver_keyboard())
            return
        text = "📋 <b>Mening topshiriqlarim:</b>\n\n"
        text += "\n".join(_delivery_text(d, db) for d in items)
        await message.answer(text[:4000], reply_markup=_driver_keyboard(), parse_mode="HTML")


# ==================== HAYDOVCHI: GPS KUZATUV ====================

@delivery_router.message(F.text == "🛰️ GPS kuzatuv", StateFilter(None))
async def driver_gps_start(message: Message, state: FSMContext):
    """GPS kuzatuv uchun faol topshiriqni tanlash"""
    if not await ensure_access(message, "delivery"):
        return
    with get_db_session() as db:
        emp = _find_employee(db, message.from_user.id)
        if not emp:
            await message.answer("❌ Profil topilmadi.", reply_markup=_driver_keyboard())
            return
        items = db.query(models.Delivery).filter(
            models.Delivery.driver_id == emp.id,
            models.Delivery.status.in_(["tayinlangan", "yo'lda"]),
        ).order_by(models.Delivery.created_at.asc()).all()
        if not items:
            await message.answer("📭 Kuzatuv uchun faol topshiriq yo'q.",
                                 reply_markup=_driver_keyboard())
            return
        rows = []
        for d in items:
            label = f"{d.delivery_number} — {d.customer_name} ({STATUS_LABELS.get(d.status, d.status)})"
            rows.append((label, f"dlv_gps_{d.id}"))
        rows.append(("❌ Bekor qilish", "dlv_cancel"))
        await message.answer("🛰️ <b>GPS KUZATUV</b>\n\nQaysi topshiriq kuzatiladi?",
                             reply_markup=_inline(rows), parse_mode="HTML")
        await DeliveryStates.tracking.set()


@delivery_router.callback_query(F.data.startswith("dlv_gps_"), DeliveryStates.tracking)
async def driver_gps_pick(callback: CallbackQuery, state: FSMContext):
    """Topshiriq tanlandi -> (mashina yo'q bo'lsa tanlatiladi) -> GPS boshlanadi"""
    await callback.answer()
    delivery_id = int(callback.data.replace("dlv_gps_", ""))
    with get_db_session() as db:
        d = crud.get_delivery(db, delivery_id)
        if not d or d.status in ("yetkazildi", "bekor"):
            await callback.message.answer("❌ Bu topshiriq yakunlangan.", reply_markup=_driver_keyboard())
            await state.clear()
            return
        if not d.vehicle_id:
            rows = _active_vehicles_rows(db, with_skip=False)
            if rows:
                # Haydovchi mashinani o'zi tanlaydi (TZ: haydovchi vehicle_id tanlasin)
                veh_rows = [
                    (f"🚛 {label}", f"dlv_gpsveh_{delivery_id}_{vid}")
                    for label, cb in rows
                    for vid in [int(cb.replace("dlv_veh_", ""))]
                ]
                await state.update_data(delivery_id=delivery_id)
                await callback.message.answer(
                    "🛰️ <b>GPS KUZATUV</b>\n\n"
                    f"📄 {d.delivery_number} — {html.escape(d.customer_name or '')}\n"
                    "🚛 Bu topshiriqga mashina tayinlanmagan. Qaysi mashinada ketasiz?",
                    reply_markup=_inline(veh_rows), parse_mode="HTML",
                )
                return
        crud.start_delivery(db, delivery_id)
        d = crud.get_delivery(db, delivery_id)
        await state.update_data(delivery_id=delivery_id)
        await callback.message.answer(
            "🛰️ <b>GPS KUZATUV BOSHLANDI</b>\n\n"
            f"📄 {d.delivery_number} — {html.escape(d.customer_name or '')}\n\n"
            "📍 Pastdagi tugma orqali <b>joylashuvni yuboring</b>.\n"
            "Har bir nuqta tizimda saqlanadi va kuzatuv sifatida ko'rsatiladi.",
            reply_markup=_gps_keyboard(), parse_mode="HTML",
        )


@delivery_router.callback_query(F.data.startswith("dlv_gpsveh_"), DeliveryStates.tracking)
async def driver_gps_pick_vehicle(callback: CallbackQuery, state: FSMContext):
    """Haydovchi mashinani tanladi -> topshiriqqa bog'lanadi -> GPS boshlanadi"""
    await callback.answer()
    parts = callback.data.replace("dlv_gpsveh_", "").split("_")
    delivery_id = int(parts[0])
    vehicle_id = int(parts[1])
    with get_db_session() as db:
        try:
            d = crud_v54.set_delivery_vehicle(db, delivery_id, vehicle_id)
        except ValueError as e:
            await callback.message.answer(f"❌ {str(e)}", reply_markup=_driver_keyboard())
            await state.clear()
            return
        crud.start_delivery(db, delivery_id)
        d = crud.get_delivery(db, delivery_id)
        await state.update_data(delivery_id=delivery_id)
        v = db.query(models.Vehicle).filter(models.Vehicle.id == d.vehicle_id).first() if d.vehicle_id else None
        veh_line = f"🚛 Mashina: {html.escape(crud_v54.vehicle_to_label(v))}\n" if v else ""
        await callback.message.answer(
            "🛰️ <b>GPS KUZATUV BOSHLANDI</b>\n\n"
            f"📄 {d.delivery_number} — {html.escape(d.customer_name or '')}\n"
            f"{veh_line}\n"
            "📍 Pastdagi tugma orqali <b>joylashuvni yuboring</b>.",
            reply_markup=_gps_keyboard(), parse_mode="HTML",
        )


@delivery_router.message(F.location, DeliveryStates.tracking)
async def driver_gps_location(message: Message, state: FSMContext):
    """Haydovchi joylashuvi qabul qilinadi va saqlanadi"""
    data = await state.get_data()
    delivery_id = data.get("delivery_id")
    loc = message.location

    with get_db_session() as db:
        try:
            point = crud.record_delivery_location(
                db, delivery_id, loc.latitude, loc.longitude,
                accuracy=loc.horizontal_accuracy, source="telegram",
            )
        except ValueError as e:
            await message.answer(str(e), reply_markup=_driver_keyboard())
            await state.clear()
            return
        d = crud.get_delivery(db, delivery_id)
        count = db.query(models.DeliveryLocation).filter(
            models.DeliveryLocation.delivery_id == delivery_id
        ).count()
        text = (
            f"📍 <b>Joylashuv qabul qilindi</b> (nuqta #{count})\n"
            f"📄 {d.delivery_number if d else ''}\n"
            f"🌐 {loc.latitude:.6f}, {loc.longitude:.6f}"
        )
        await message.answer(text, reply_markup=_gps_keyboard(), parse_mode="HTML")


@delivery_router.message(F.text == "⏹️ GPS kuzatuvni to'xtatish", DeliveryStates.tracking)
async def driver_gps_stop(message: Message, state: FSMContext):
    """GPS kuzatuvni to'xtatish (topshiriq 'yo'lda' holatida qoladi)"""
    await state.clear()
    await message.answer(
        "⏹️ GPS kuzatuv to'xtatildi. Topshiriq '🚚 Yo'lda' holatida qoldi.",
        reply_markup=_driver_keyboard(),
    )


# ==================== HAYDOVCHI: YETKAZIB BERILDI ====================

@delivery_router.message(F.text == "✅ Yetkazib berildi", StateFilter(None))
async def driver_complete_pick(message: Message, state: FSMContext):
    """Yakunlash uchun topshiriq tanlash"""
    if not await ensure_access(message, "delivery", edit=True):
        return
    with get_db_session() as db:
        emp = _find_employee(db, message.from_user.id)
        if not emp:
            await message.answer("❌ Profil topilmadi.", reply_markup=_driver_keyboard())
            return
        items = db.query(models.Delivery).filter(
            models.Delivery.driver_id == emp.id,
            models.Delivery.status.in_(["tayinlangan", "yo'lda"]),
        ).order_by(models.Delivery.created_at.asc()).all()
        if not items:
            await message.answer("📭 Yakunlanadigan topshiriq yo'q.",
                                 reply_markup=_driver_keyboard())
            return
        rows = [(
            f"{d.delivery_number} — {d.customer_name}",
            f"dlv_done_{d.id}",
        ) for d in items]
        rows.append(("❌ Bekor qilish", "dlv_cancel"))
        await message.answer("✅ <b>YETKAZIB BERILDI</b>\n\nQaysi topshiriq yakunlanadi?",
                             reply_markup=_inline(rows), parse_mode="HTML")
        await DeliveryStates.tracking.set()


@delivery_router.callback_query(F.data.startswith("dlv_done_"), DeliveryStates.tracking)
async def driver_complete(callback: CallbackQuery, state: FSMContext):
    """Topshiriqni yakunlash"""
    await callback.answer()
    delivery_id = int(callback.data.replace("dlv_done_", ""))
    with get_db_session() as db:
        try:
            d = crud.complete_delivery(db, delivery_id)
            sale = db.query(models.Sale).filter(models.Sale.id == d.sale_id).first()
            text = (
                "✅ <b>YETKAZIB BERILDI</b>\n\n"
                f"📄 {d.delivery_number}\n"
                f"👤 Mijoz: {html.escape(d.customer_name or '-')}\n"
                f"🏭 {html.escape(d.product_name or '')} x {_qty(d.quantity)} {d.unit or ''}\n"
                f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                "Sotuv tarixida 'yetkazib_berildi' deb belgilandi."
            )
            await callback.message.answer(text, reply_markup=_driver_keyboard(), parse_mode="HTML")
        except ValueError as e:
            await callback.message.answer(f"❌ {str(e)}", reply_markup=_driver_keyboard())
    await state.clear()


# ==================== MENEJER: TOPSHIRIQ YARATISH ====================

@delivery_router.message(F.text == "➕ Topshiriq yaratish", StateFilter(None))
async def manager_create_pick_sale(message: Message, state: FSMContext):
    """Yangi topshiriq: sotuvni tanlash"""
    if not await ensure_access(message, "delivery", edit=True):
        return
    with get_db_session() as db:
        sales = crud.list_deliverable_sales(db, limit=15)
        if not sales:
            await message.answer(
                "📭 Topshiriq yaratish mumkin bo'lgan sotuvlar yo'q.\n"
                "(yetkazilmagan qoldiq bo'lishi kerak)",
                reply_markup=_manager_keyboard(),
            )
            return
        rows = []
        for s in sales:
            product = db.query(models.Product).filter(models.Product.id == s.product_id).first()
            name = product.name if product else "Noma'lum"
            remaining = crud.get_sale_delivery_remaining(db, s)
            label = f"{s.invoice_number} — {name} x {_qty(remaining)} ({s.customer_name})"
            rows.append((label, f"dlv_sale_{s.id}"))
        rows.append(("❌ Bekor qilish", "dlv_cancel"))
        await message.answer(
            "➕ <b>TOPSHIRIQ YARATISH</b>\n\nQaysi sotuv yetkaziladi?",
            reply_markup=_inline(rows), parse_mode="HTML",
        )
        await DeliveryStates.create_sale.set()


@delivery_router.callback_query(F.data.startswith("dlv_sale_"), DeliveryStates.create_sale)
async def manager_create_pick_driver(callback: CallbackQuery, state: FSMContext):
    """Sotuv tanlandi -> haydovchini tanlash"""
    await callback.answer()
    sale_id = int(callback.data.replace("dlv_sale_", ""))
    with get_db_session() as db:
        sale = db.query(models.Sale).filter(models.Sale.id == sale_id).first()
        if not sale:
            await callback.message.answer("❌ Sotuv topilmadi.", reply_markup=_manager_keyboard())
            await state.clear()
            return
        remaining = crud.get_sale_delivery_remaining(db, sale)
        await state.update_data(sale_id=sale_id, remaining=remaining)

        drivers = db.query(models.Employee).filter(
            models.Employee.role == "haydovchi",
            models.Employee.status == models.EmployeeStatus.ACTIVE,
        ).order_by(models.Employee.full_name).all()
        if not drivers:
            await callback.message.answer(
                "❌ Haydovchi xodim topilmadi. Avval xodimlar bo'limida haydovchi qo'shing.",
                reply_markup=_manager_keyboard(),
            )
            await state.clear()
            return
        rows = [(f"🚚 {d.full_name} ({d.phone_number})", f"dlv_drv_{d.id}") for d in drivers]
        rows.append(("❌ Bekor qilish", "dlv_cancel"))
        await callback.message.answer(
            f"➕ <b>TOPSHIRIQ YARATISH</b>\n\n"
            f"🧾 Sotuv: {sale.invoice_number} | Qoldiq: {_qty(remaining)}\n"
            "Haydovchini tanlang:",
            reply_markup=_inline(rows), parse_mode="HTML",
        )
        await DeliveryStates.create_driver.set()


@delivery_router.callback_query(F.data.startswith("dlv_drv_"), DeliveryStates.create_driver)
async def manager_create_pick_vehicle(callback: CallbackQuery, state: FSMContext):
    """Haydovchi tanlandi -> mashina tanlash (ixtiyoriy) -> topshiriq yaratiladi"""
    await callback.answer()
    driver_id = int(callback.data.replace("dlv_drv_", ""))
    await state.update_data(driver_id=driver_id)
    data = await state.get_data()
    sale_id = data.get("sale_id")
    with get_db_session() as db:
        sale = db.query(models.Sale).filter(models.Sale.id == sale_id).first()
        rows = _active_vehicles_rows(db, with_skip=True)
    if not rows:
        # Faol mashina yo'q — to'g'ridan-to'g'ri topshiriq yaratamiz
        await _manager_create_final(callback, state, driver_id=driver_id, vehicle_id=None)
        return
    await callback.message.answer(
        f"➕ <b>TOPSHIRIQ YARATISH</b>\n\n"
        f"🧾 Sotuv: {sale.invoice_number if sale else '—'}\n"
        "🚛 Transport vositasini tanlang:",
        reply_markup=_inline(rows), parse_mode="HTML",
    )
    await DeliveryStates.create_vehicle.set()


@delivery_router.callback_query(F.data.startswith("dlv_veh_"), DeliveryStates.create_vehicle)
async def manager_create_confirm(callback: CallbackQuery, state: FSMContext):
    """Mashina tanlandi -> topshiriq yaratiladi"""
    await callback.answer()
    data = await state.get_data()
    if callback.data == "dlv_veh_skip":
        vehicle_id = None
    else:
        vehicle_id = int(callback.data.replace("dlv_veh_", ""))
    await _manager_create_final(callback, state, driver_id=data.get("driver_id"),
                                vehicle_id=vehicle_id)


async def _manager_create_final(callback: CallbackQuery, state: FSMContext,
                                driver_id: int, vehicle_id):
    """Topshiriqni yakuniy yaratish (mashina bilan yoki mashinasiz)"""
    data = await state.get_data()
    try:
        with get_db_session() as db:
            d = crud_v54.create_delivery_with_vehicle(
                db,
                sale_id=data.get("sale_id"),
                driver_id=driver_id,
                quantity=data.get("remaining"),
                created_by=callback.from_user.full_name,
                vehicle_id=vehicle_id,
            )
            text = (
                "✅ <b>TOPSHIRIQ YARATILDI</b>\n\n"
                f"{_delivery_text(d, db)}\n"
                f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            await callback.message.answer(text, reply_markup=_manager_keyboard(), parse_mode="HTML")
    except ValueError as e:
        await callback.message.answer(f"❌ {str(e)}", reply_markup=_manager_keyboard())
    await state.clear()


# ==================== MENEJER: BARCHA YETKAZISHLAR ====================

@delivery_router.message(F.text == "📋 Barcha yetkazishlar", StateFilter(None))
async def manager_all_deliveries(message: Message):
    """Barcha yetkazishlar (so'nggi 10)"""
    if not await ensure_access(message, "delivery"):
        return
    with get_db_session() as db:
        items = crud.list_deliveries(db, limit=10)
        if not items:
            await message.answer("📭 Hozircha yetkazishlar yo'q.", reply_markup=_manager_keyboard())
            return
        text = "🚚 <b>YETKAZISHLAR (so'nggi 10):</b>\n\n"
        text += "\n".join(_delivery_text(d, db) for d in items)
        await message.answer(text[:4000], reply_markup=_manager_keyboard(), parse_mode="HTML")


# ==================== BEKOR QILISH (umumiy) ====================

@delivery_router.callback_query(F.data == "dlv_cancel", StateFilter("*"))
async def delivery_cancel_cb(callback: CallbackQuery, state: FSMContext):
    """Inline bekor qilish"""
    await callback.answer()
    await state.clear()
    await callback.message.answer("❌ Amal bekor qilindi.", reply_markup=get_main_menu())


# ==================== REGISTER ====================

def register_handlers_delivery(dp: Dispatcher):
    """Yetkazib berish handlerlarini Dispatcher'ga qo'shish"""
    dp.include_router(delivery_router)
