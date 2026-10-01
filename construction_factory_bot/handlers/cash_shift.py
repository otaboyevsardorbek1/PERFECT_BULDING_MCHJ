"""
Kassir smenasi moduli (v3) — "smena yopish + naqd farq"

- 🟢 Smena boshlash: kassir boshlang'ich naqd miqdorni kiritadi
- 📊 Joriy holat: shu paytgacha kutilgan naqd (sotuv/avans/qaytarish guruhlari)
- 🔴 Smena yopish: kassir sanagan haqiqiy naqd kiritiladi,
  tizim farqni hisoblaydi (actual - expected) va smenani yopadi
- 📋 Smenalar tarixi

Naqd kassa: Payment.method == 'cash' bo'lgan barcha to'lovlar
(kirim +, qaytarish -) smena boshlangan vaqtdan boshlab hisobga olinadi.
"""

from datetime import datetime

from aiogram import F, Router, Dispatcher, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import crud, models
from database.session import get_db_session
from keyboards.main_menu import get_main_menu
from utils.access import ensure_access, get_user_role
from utils.helpers import parse_float_input

shift_router = Router()


class ShiftStates(StatesGroup):
    """Smena FSM holatlari"""
    opening_amount = State()   # boshlang'ich naqd kiritish
    closing_actual = State()   # haqiqiy sanalgan naqd kiritish
    closing_confirm = State()  # yakuniy tasdiqlash


def _shift_menu_keyboard() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        types.KeyboardButton("🟢 Smena boshlash"),
        types.KeyboardButton("📊 Joriy holat"),
        types.KeyboardButton("🔴 Smena yopish"),
        types.KeyboardButton("📋 Smenalar tarixi"),
        types.KeyboardButton("⬅️ Orqaga"),
    ]
    kb.add(*buttons)
    return kb


def _inline(rows: list) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=t, callback_data=cb)] for t, cb in rows
    ])


def _money(value) -> str:
    try:
        return f"{float(value):,.0f}".replace(",", " ").replace(".0", "")
    except (TypeError, ValueError):
        return "0"


def _employee(db, telegram_id: int):
    return db.query(models.Employee).filter(
        models.Employee.telegram_id == telegram_id
    ).first()


def _summary_text(db, shift: models.CashShift) -> str:
    """Smena bo'yicha naqd hisob matni"""
    s = crud.cash_shift_summary(db, shift)
    text = (
        f"🧾 Smena: <b>{shift.shift_number}</b>\n"
        f"👤 Kassir: {shift.cashier_name or '-'}\n"
        f"🕐 Boshlangan: {shift.opened_at.strftime('%d.%m.%Y %H:%M') if shift.opened_at else '-'}\n\n"
        f"💰 Boshlang'ich naqd: <b>{_money(shift.opening_balance)} so'm</b>\n"
    )
    for g in s["groups"]:
        sign = "➖" if (g["total"] or 0) < 0 else "➕"
        text += f"{sign} {g['label']} ({g['count']} ta): {_money(g['total'])} so'm\n"
    text += (
        f"\n📊 <b>Kutilgan naqd: {_money(s['expected_cash'])} so'm</b>\n"
        f"📄 Jami harakatlar: {s['payment_count']} ta"
    )
    return text


# ==================== KIRISH ====================

@shift_router.message(F.text == "💵 Smena (kassa)", StateFilter(None))
async def shift_menu(message: types.Message, state: FSMContext):
    """Smena bo'limi — kassir uchun menyu"""
    if not await ensure_access(message, "cash_shift"):
        return
    await state.clear()
    with get_db_session() as db:
        shift = crud.get_open_cash_shift(db)
        role = get_user_role(db, message.from_user.id)
    shift_status = (
        "🟢 Smena ochiq: " + shift.shift_number if shift else "🔴 Ochiq smena yo'q"
    )
    text = (
        "💵 <b>KASSA SMENASI</b>\n\n"
        "• 🟢 Smena boshlash — boshlang'ich naqd bilan ishni boshlash\n"
        "• 📊 Joriy holat — kutilgan naqd va harakatlar\n"
        "• 🔴 Smena yopish — sanalgan naqdni kiritib farqni hisoblash\n"
        f"\nHolat: {shift_status}"
    )
    # Kassir emas (direktor) ko'rishi uchun rol faqat info
    await message.answer(text, reply_markup=_shift_menu_keyboard(), parse_mode="HTML")


# ==================== SMENA BOSHLASH ====================

@shift_router.message(F.text == "🟢 Smena boshlash", StateFilter(None))
async def shift_open_start(message: types.Message, state: FSMContext):
    """Smena boshlash — boshlang'ich summani so'raydi"""
    if not await ensure_access(message, "cash_shift", edit=True):
        return
    with get_db_session() as db:
        if crud.get_open_cash_shift(db):
            await message.answer(
                "⛔ Ochiq smena mavjud. Avval '🔴 Smena yopish' bo'limida yoping.",
                reply_markup=_shift_menu_keyboard(),
            )
            return
    await message.answer(
        "🟢 <b>SMENA BOSHLASH</b>\n\n"
        "Kassadagi <b>boshlang'ich naqd</b> miqdorini kiriting (so'm):\n"
        "(misol: 500000 yoki 500 000)",
        reply_markup=_inline([("❌ Bekor qilish", "shift_cancel")]),
        parse_mode="HTML",
    )
    await ShiftStates.opening_amount.set()


@shift_router.message(ShiftStates.opening_amount)
async def shift_open_amount(message: types.Message, state: FSMContext):
    """Boshlang'ich summa qabul qilinadi va smena ochiladi"""
    amount = parse_float_input(message.text)
    if amount is None or amount < 0:
        await message.answer("❌ Summa noto'g'ri. Musbat son kiriting:")
        return
    try:
        with get_db_session() as db:
            emp = _employee(db, message.from_user.id)
            shift = crud.create_cash_shift(
                db,
                employee_id=emp.id if emp else None,
                employee_name=emp.full_name if emp else message.from_user.full_name,
                opening_balance=amount,
            )
        await message.answer(
            "🟢 <b>SMENA BOSHLANDI</b>\n\n"
            f"🧾 {shift.shift_number}\n"
            f"💰 Boshlang'ich naqd: <b>{_money(amount)} so'm</b>\n"
            f"🕐 {datetime.now().strftime('%H:%M')}\n\n"
            "Sotuvlarni qabul qilishingiz mumkin. Kun oxirida '🔴 Smena yopish'.",
            reply_markup=_shift_menu_keyboard(), parse_mode="HTML",
        )
    except ValueError as e:
        await message.answer(f"❌ {str(e)}", reply_markup=_shift_menu_keyboard())
    await state.clear()


# ==================== JORIY HOLAT ====================

@shift_router.message(F.text == "📊 Joriy holat", StateFilter(None))
async def shift_status(message: types.Message):
    """Ochiq smena bo'yicha kutilgan naqd"""
    if not await ensure_access(message, "cash_shift"):
        return
    with get_db_session() as db:
        shift = crud.get_open_cash_shift(db)
        if not shift:
            await message.answer(
                "🔴 Ochiq smena yo'q. Smena boshlash uchun '🟢 Smena boshlash'.",
                reply_markup=_shift_menu_keyboard(),
            )
            return
        text = "📊 <b>JORIY SMENA HOLATI</b>\n\n" + _summary_text(db, shift)
        await message.answer(text, reply_markup=_shift_menu_keyboard(), parse_mode="HTML")


# ==================== SMENA YOPISH ====================

@shift_router.message(F.text == "🔴 Smena yopish", StateFilter(None))
async def shift_close_start(message: types.Message, state: FSMContext):
    """Smena yopish — haqiqiy naqdni so'raydi"""
    if not await ensure_access(message, "cash_shift", edit=True):
        return
    with get_db_session() as db:
        shift = crud.get_open_cash_shift(db)
        if not shift:
            await message.answer(
                "🔴 Ochiq smena yo'q. Avval smena boshlang.",
                reply_markup=_shift_menu_keyboard(),
            )
            return
        await state.update_data(shift_id=shift.id)
        text = "🔴 <b>SMENA YOPISH</b>\n\n" + _summary_text(db, shift)
        text += "\n\n💵 Kassadagi <b>haqiqiy sanalgan naqd</b> miqdorini kiriting (so'm):"
        await message.answer(text, reply_markup=_inline([("❌ Bekor qilish", "shift_cancel")]),
                             parse_mode="HTML")
        await ShiftStates.closing_actual.set()


@shift_router.message(ShiftStates.closing_actual)
async def shift_close_actual(message: types.Message, state: FSMContext):
    """Haqiqiy naqd qabul qilinadi — farq ko'rsatilib tasdiqlash so'raladi"""
    actual = parse_float_input(message.text)
    if actual is None or actual < 0:
        await message.answer("❌ Summa noto'g'ri. Musbat son kiriting:")
        return
    data = await state.get_data()
    with get_db_session() as db:
        shift = crud.get_open_cash_shift(db)
        if not shift or shift.id != data.get("shift_id"):
            await message.answer("❌ Smena o'zgargan/yopilgan.", reply_markup=_shift_menu_keyboard())
            await state.clear()
            return
        summary = crud.cash_shift_summary(db, shift)
        expected = summary["expected_cash"]
        diff = actual - expected
    await state.update_data(actual_cash=actual, expected_cash=expected)
    diff_label = "✅ Farq yo'q" if abs(diff) < 0.5 else \
        (f"🟢 Ortiqcha: <b>{_money(diff)} so'm</b>" if diff > 0 else f"🔴 Kamomad: <b>{_money(abs(diff))} so'm</b>")
    await message.answer(
        "🔴 <b>SMENA YOPISH — TASDIQLASH</b>\n\n"
        f"💰 Kutilgan naqd: <b>{_money(expected)} so'm</b>\n"
        f"💵 Haqiqiy naqd: <b>{_money(actual)} so'm</b>\n"
        f"{diff_label}\n\n"
        "Smenani yopasizmi?",
        reply_markup=_inline([
            ("✅ Yopish", "shift_close_yes"),
            ("❌ Bekor qilish", "shift_cancel"),
        ]),
        parse_mode="HTML",
    )
    await ShiftStates.closing_confirm.set()


@shift_router.callback_query(F.data == "shift_close_yes", ShiftStates.closing_confirm)
async def shift_close_confirm(callback: types.CallbackQuery, state: FSMContext):
    """Smenani yakuniy yopish — farq saqlanadi"""
    await callback.answer()
    data = await state.get_data()
    try:
        with get_db_session() as db:
            shift = crud.close_cash_shift(db, data.get("shift_id"),
                                          actual_cash=data.get("actual_cash"))
            diff = shift.difference
            diff_line = "✅ Farq yo'q" if abs(diff) < 0.5 else \
                (f"🟢 Ortiqcha {_money(diff)} so'm" if diff > 0 else f"🔴 Kamomad {_money(abs(diff))} so'm")
        text = (
            "🔴 <b>SMENA YOPILDI</b>\n\n"
            f"🧾 {shift.shift_number}\n"
            f"👤 Kassir: {shift.cashier_name or '-'}\n"
            f"💰 Boshlang'ich: {_money(shift.opening_balance)} so'm\n"
            f"📊 Kutilgan: {_money(shift.expected_cash)} so'm\n"
            f"💵 Haqiqiy: {_money(shift.actual_cash)} so'm\n"
            f"⚖️ Farq: {diff_line}\n"
            f"🕐 Yopilgan: {datetime.now().strftime('%H:%M')}\n\n"
            "⚠️ Farq mavjud bo'lsa — moliya/buxgalter bilan kelishib oling."
        )
        await callback.message.answer(text, reply_markup=_shift_menu_keyboard(), parse_mode="HTML")
    except ValueError as e:
        await callback.message.answer(f"❌ {str(e)}", reply_markup=_shift_menu_keyboard())
    await state.clear()


# ==================== TARIX ====================

@shift_router.message(F.text == "📋 Smenalar tarixi", StateFilter(None))
async def shift_history(message: types.Message):
    """So'nggi smenalar ro'yxati"""
    if not await ensure_access(message, "cash_shift"):
        return
    with get_db_session() as db:
        shifts = crud.list_cash_shifts(db, limit=10)
        if not shifts:
            await message.answer("📭 Smenalar hali yo'q.", reply_markup=_shift_menu_keyboard())
            return
        text = "📋 <b>SMENALAR (so'nggi 10):</b>\n\n"
        for s in shifts:
            diff_part = ""
            if s.difference is not None:
                if abs(s.difference) < 0.5:
                    diff_part = " | ✅ farq yo'q"
                elif s.difference > 0:
                    diff_part = f" | 🟢 +{_money(s.difference)}"
                else:
                    diff_part = f" | 🔴 -{_money(abs(s.difference))}"
            closed = f" yopildi {s.closed_at.strftime('%d.%m %H:%M')}" if s.closed_at else ""
            text += (
                f"{crud.CASH_SHIFT_STATUS_LABELS.get(s.status, s.status)} <b>{s.shift_number}</b>"
                f"{diff_part}\n"
                f"   👤 {s.cashier_name or '-'} | 💵 {_money(s.opening_balance)} so'm"
                f" | 🕐 {s.opened_at.strftime('%d.%m %H:%M') if s.opened_at else ''}{closed}\n\n"
            )
        await message.answer(text[:4000], reply_markup=_shift_menu_keyboard(), parse_mode="HTML")


# ==================== BEKOR ====================

@shift_router.callback_query(F.data == "shift_cancel")
async def shift_cancel_cb(callback: types.CallbackQuery, state: FSMContext):
    """Inline bekor qilish"""
    await callback.answer()
    await state.clear()
    await callback.message.answer("❌ Amal bekor qilindi.", reply_markup=_shift_menu_keyboard())


# ==================== REGISTER ====================

def register_handlers_cash_shift(dp: Dispatcher):
    """Smena handlerlarini Dispatcher'ga qo'shish"""
    dp.include_router(shift_router)
