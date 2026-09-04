"""
Qaytarish akti moduli (v3) — TZ "F. QAYTARISH MODULI"

Mijoz tovarni qaytarsa:
  1. Sabab: sifat (brak) / noto'g'ri mahsulot / mijoz istagi
  2. Tizim ruxsatni tekshiradi (7 kun ichida + qoldiq yetarli)
  3. Qaytarish akti yaratiladi
  4. Pul qaytarish turi: naqd/karta, almashtirish yoki bonus ball
  5. Mahsulot omborga qaytadi (sifatsiz bo'lsa - brak ombori)
  6. Sotuv tarixiga "qaytarilgan" yoziladi
  7. Mijozga SMS: "Qaytarish amalga oshirildi"

Kirish: 💰 Sotuvlar -> ↩️ Qaytarish akti / 🧾 Qaytarishlar tarixi
"""

import asyncio
import html
from datetime import datetime

from aiogram import F, Router, Dispatcher, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import crud, models
from database.session import get_db_session
from keyboards.main_menu import get_main_menu
from utils.access import ensure_access
from utils.helpers import format_currency, parse_float_input

returns_router = Router()


class ReturnStates(StatesGroup):
    """Qaytarish akti FSM holatlari"""
    sale_selected = State()      # sotuv tanlandi (keyingi qadam: miqdor yoki sabab)
    quantity = State()           # qaytariladigan miqdor kiritilmoqda
    reason = State()             # sabab tanlash
    refund_type = State()        # qaytarish turi (pul/almashtirish/bonus)
    exchange_product = State()   # almashtiriladigan mahsulot
    exchange_quantity = State()  # almashtiriladigan miqdor
    pay_method = State()         # farq uchun to'lov/kassa usuli


def _qty_text(value: float) -> str:
    """Miqdorni chiroyli ko'rsatish (butun bo'lsa vergulsiz)"""
    try:
        if float(value).is_integer():
            return f"{int(value):,}".replace(",", " ")
        return f"{float(value):,.2f}".rstrip("0").rstrip(".").replace(",", " ")
    except (TypeError, ValueError):
        return str(value)


def _sales_menu_keyboard() -> types.ReplyKeyboardMarkup:
    """Sotuvlar bo'limiga qaytish uchun tugmalar"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        types.KeyboardButton("💰 Sotuvlar"),
        types.KeyboardButton("⬅️ Orqaga"),
    ]
    keyboard.add(*buttons)
    return keyboard


def _inline_buttons(rows: list) -> types.InlineKeyboardMarkup:
    """Qatorlar: [(text, callback_data), ...]"""
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=t, callback_data=cb)] for t, cb in rows
    ])


# ==================== KIRISH: YANGI QAYTARISH ====================

@returns_router.message(F.text == "↩️ Qaytarish akti", StateFilter(None))
async def return_act_start(message: types.Message, state: FSMContext):
    """Qaytarishga yaroqli so'nggi sotuvlarni ko'rsatadi"""
    if not await ensure_access(message, "sales", edit=True):
        return

    await state.clear()
    with get_db_session() as db:
        sales = db.query(models.Sale).order_by(
            models.Sale.sale_date.desc()
        ).limit(20).all()

        rows = []
        for s in sales:
            remaining = (s.quantity or 0) - (s.returned_qty or 0)
            if remaining <= 0:
                continue
            elig = crud.check_return_eligibility(db, s.id, None)
            product = db.query(models.Product).filter(
                models.Product.id == s.product_id
            ).first()
            name = product.name if product else "Noma'lum"
            label = f"{s.invoice_number} — {name} x {_qty_text(remaining)}"
            if not elig["allowed"]:
                label += " ⛔"
            rows.append((label, f"ret_sale_{s.id}"))

        if not rows:
            await message.answer(
                "↩️ <b>Qaytarish akti</b>\n\n"
                "📭 Qaytarishga yaroqli sotuvlar yo'q.\n"
                "Qaytarish sharti: sotuvdan keyin 7 kun ichida va qoldiq bo'lishi kerak.",
                reply_markup=get_main_menu(), parse_mode="HTML",
            )
            return

        rows.append(("❌ Bekor qilish", "ret_cancel"))
        await message.answer(
            "↩️ <b>Qaytarish akti</b>\n\n"
            "Qaysi sotuv qaytarilmoqda? Sotuvni tanlang:\n"
            "(⛔ — qaytarish muddati o'tgan)",
            reply_markup=_inline_buttons(rows), parse_mode="HTML",
        )
        await ReturnStates.sale_selected.set()


@returns_router.callback_query(F.data.startswith("ret_sale_"), ReturnStates.sale_selected)
async def return_pick_sale(callback: types.CallbackQuery, state: FSMContext):
    """Sotuv tanlandi -> qaytariladigan miqdorni so'raydi"""
    await callback.answer()
    sale_id = int(callback.data.replace("ret_sale_", ""))

    with get_db_session() as db:
        elig = crud.check_return_eligibility(db, sale_id, None)
        sale = db.query(models.Sale).filter(models.Sale.id == sale_id).first()
        product = db.query(models.Product).filter(
            models.Product.id == sale.product_id
        ).first() if sale else None

        if not elig["allowed"] or not sale:
            await callback.message.answer(
                f"⛔ Qaytarish mumkin emas: {elig['reason']}",
                reply_markup=get_main_menu(),
            )
            await state.clear()
            return

        remaining = (sale.quantity or 0) - (sale.returned_qty or 0)
        unit = product.unit if product else ""
        await state.update_data(sale_id=sale_id, remaining=remaining)
        await callback.message.answer(
            "↩️ <b>Qaytarish akti</b>\n\n"
            f"🧾 Sotuv: <b>{html.escape(sale.invoice_number or '')}</b>\n"
            f"🏭 Mahsulot: <b>{html.escape(product.name) if product else "Noma'lum"}</b>\n"
            f"📦 Qoldiq: <b>{_qty_text(remaining)} {unit}</b>\n\n"
            "Qaytariladigan miqdorni kiriting:",
            reply_markup=_inline_buttons([("❌ Bekor qilish", "ret_cancel")]),
            parse_mode="HTML",
        )
        await ReturnStates.quantity.set()


@returns_router.message(ReturnStates.quantity)
async def return_input_quantity(message: types.Message, state: FSMContext):
    """Qaytariladigan miqdor qabul qilinadi"""
    qty = parse_float_input(message.text)
    data = await state.get_data()
    sale_id = data.get("sale_id")

    if qty is None or qty <= 0:
        await message.answer("❌ Miqdor noto'g'ri. Iltimos, musbat son kiriting:")
        return

    with get_db_session() as db:
        elig = crud.check_return_eligibility(db, sale_id, qty)
        sale = db.query(models.Sale).filter(models.Sale.id == sale_id).first()
        product = db.query(models.Product).filter(
            models.Product.id == sale.product_id
        ).first() if sale else None

        if not elig["allowed"]:
            await message.answer(f"⛔ {elig['reason']}")
            await state.clear()
            return

        remaining = data.get("remaining") or 0
        unit = product.unit if product else ""
        await state.update_data(quantity=qty)
        await message.answer(
            "↩️ <b>Qaytarish sababi?</b>\n\n"
            f"Miqdor: <b>{_qty_text(qty)} {unit}</b>",
            reply_markup=_inline_buttons([
                ("🔴 Sifat muammosi (brak)", "ret_reason_brak"),
                ("❌ Noto'g'ri mahsulot", "ret_reason_notogri"),
                ("🙋 Mijoz istagi", "ret_reason_mijoz_istagi"),
                ("❌ Bekor qilish", "ret_cancel"),
            ]),
            parse_mode="HTML",
        )
        await ReturnStates.reason.set()


@returns_router.callback_query(F.data.startswith("ret_reason_"), ReturnStates.reason)
async def return_pick_reason(callback: types.CallbackQuery, state: FSMContext):
    """Sabab tanlandi -> qaytarish turini so'raydi"""
    await callback.answer()
    reason = callback.data.replace("ret_reason_", "")
    await state.update_data(reason=reason)
    await callback.message.answer(
        "↩️ <b>Qaytarish turi?</b>\n\n"
        "• 💵 Naqd / 💳 Karta — pul qaytariladi\n"
        "• 🔄 Almashtirish — boshqa mahsulot beriladi\n"
        "• 🎁 Bonus ball — kelajakdagi xaridga ball yoziladi",
        reply_markup=_inline_buttons([
            ("💵 Naqd pul qaytarish", "ret_type_cash"),
            ("💳 Kartaga qaytarish", "ret_type_card"),
            ("🔄 Boshqa mahsulotga almashtirish", "ret_type_exchange"),
            ("🎁 Bonus ball berish", "ret_type_bonus"),
            ("❌ Bekor qilish", "ret_cancel"),
        ]),
        parse_mode="HTML",
    )
    await ReturnStates.refund_type.set()


@returns_router.callback_query(F.data.startswith("ret_type_"), ReturnStates.refund_type)
async def return_pick_type(callback: types.CallbackQuery, state: FSMContext):
    """Qaytarish turi tanlandi. Almashtirish bo'lsa mahsulot so'raladi"""
    await callback.answer()
    refund_type = callback.data.replace("ret_type_", "")

    if refund_type == "exchange":
        await state.update_data(refund_type="exchange")
        with get_db_session() as db:
            products = db.query(models.Product).filter(
                models.Product.is_active == True
            ).order_by(models.Product.name).all()
            rows = [
                (f"{p.name} ({format_currency(p.selling_price or 0)} so'm)", f"ret_ex_{p.id}")
                for p in products
            ]
            rows.append(("❌ Bekor qilish", "ret_cancel"))
            await callback.message.answer(
                "🔄 <b>Almashtirish</b>\n\nQaysi mahsulotga almashtiriladi?",
                reply_markup=_inline_buttons(rows), parse_mode="HTML",
            )
            await ReturnStates.exchange_product.set()
        return

    # cash / card / bonus
    await state.update_data(refund_type=refund_type)
    await _show_confirm(callback.message, state)
    await ReturnStates.pay_method.set()  # tasdiqlash faqat inline orqali


@returns_router.callback_query(F.data.startswith("ret_ex_"), ReturnStates.exchange_product)
async def return_pick_exchange_product(callback: types.CallbackQuery, state: FSMContext):
    """Almashtiriladigan mahsulot tanlandi -> miqdor so'raladi"""
    await callback.answer()
    exchange_product_id = int(callback.data.replace("ret_ex_", ""))

    with get_db_session() as db:
        product = db.query(models.Product).filter(
            models.Product.id == exchange_product_id,
            models.Product.is_active == True,
        ).first()
        if not product:
            await callback.message.answer("❌ Mahsulot topilmadi.")
            await state.clear()
            return
        data = await state.get_data()
        qty = data.get("quantity") or 1
        await state.update_data(
            exchange_product_id=product.id,
            exchange_product_name=product.name,
            exchange_unit=product.unit,
        )
        await callback.message.answer(
            "🔄 <b>Almashtirish miqdori</b>\n\n"
            f"🏭 {html.escape(product.name)} ({format_currency(product.selling_price or 0)} so'm)\n"
            f"📦 Qaytarilgan miqdor: {_qty_text(qty)} {product.unit}\n\n"
            "Nechta beriladi? (miqdorni kiriting)",
            reply_markup=_inline_buttons([("❌ Bekor qilish", "ret_cancel")]),
            parse_mode="HTML",
        )
        await ReturnStates.exchange_quantity.set()


@returns_router.message(ReturnStates.exchange_quantity)
async def return_input_exchange_quantity(message: types.Message, state: FSMContext):
    """Almashtiriladigan miqdor qabul qilinadi"""
    qty = parse_float_input(message.text)
    data = await state.get_data()

    if qty is None or qty <= 0:
        await message.answer("❌ Miqdor noto'g'ri. Iltimos, musbat son kiriting:")
        return

    await state.update_data(exchange_quantity=qty)

    with get_db_session() as db:
        data = await state.get_data()
        exchange_product = db.query(models.Product).filter(
            models.Product.id == data.get("exchange_product_id")
        ).first()
        if not exchange_product:
            await message.answer("❌ Mahsulot topilmadi.")
            await state.clear()
            return

        returned_qty = float(data.get("quantity") or 0)
        sale = db.query(models.Sale).filter(models.Sale.id == data.get("sale_id")).first()
        x_value = returned_qty * (sale.unit_price if sale else 0)
        y_value = qty * (exchange_product.selling_price or 0)
        diff = y_value - x_value

        await state.update_data(exchange_value=y_value)

        if abs(diff) < 1:
            # Qiymat teng — to'lov/farq yo'q, to'g'ridan-to'g'ri tasdiqlash
            await state.update_data(pay_method=None)
            await _show_confirm(message, state)
            await ReturnStates.pay_method.set()
        else:
            if diff > 0:
                text = (
                    f"💳 Yangi mahsulot qiymati qaytarilgan qiymatdan <b>{format_currency(diff)} so'm</b> "
                    "ortiq. Farq qanday to'lanadi?"
                )
            else:
                text = (
                    f"💵 Yangi mahsulot qiymati qaytarilgan qiymatdan <b>{format_currency(abs(diff))} so'm</b> "
                    "kam. Farq mijozga qanday qaytariladi?"
                )
            await message.answer(
                text,
                reply_markup=_inline_buttons([
                    ("💵 Naqd", "ret_diff_cash"),
                    ("💳 Karta", "ret_diff_card"),
                    ("❌ Bekor qilish", "ret_cancel"),
                ]),
                parse_mode="HTML",
            )
            await ReturnStates.pay_method.set()


@returns_router.callback_query(F.data.startswith("ret_diff_"), ReturnStates.pay_method)
async def return_pick_pay_method(callback: types.CallbackQuery, state: FSMContext):
    """Farq uchun to'lov/kassa usuli tanlandi"""
    await callback.answer()
    method = callback.data.replace("ret_diff_", "")
    await state.update_data(pay_method=method)
    await _show_confirm(callback.message, state)


async def _show_confirm(message: types.Message, state: FSMContext):
    """Yakuniy tasdiqlash ekrani"""
    data = await state.get_data()
    refund_type = data.get("refund_type", "cash")

    with get_db_session() as db:
        sale = db.query(models.Sale).filter(models.Sale.id == data.get("sale_id")).first()
        product = db.query(models.Product).filter(models.Product.id == sale.product_id).first() if sale else None
        qty = float(data.get("quantity") or 0)
        x_value = qty * (sale.unit_price or 0) if sale else 0
        exchange_value = float(data.get("exchange_value") or 0)

        text = (
            "↩️ <b>QAYTARISH AKTI — TASDIQLASH</b>\n\n"
            f"🧾 Sotuv: {html.escape(sale.invoice_number or '') if sale else '-'}\n"
            f"🏭 Qaytariladigan: {html.escape(product.name) if product else "Noma'lum"} x "
            f"{_qty_text(qty)} {product.unit if product else ''}\n"
            f"💵 Qiymati: <b>{format_currency(x_value)} so'm</b>\n"
        )

        reason_label = crud.RETURN_REASON_LABELS.get(data.get("reason", "mijoz_istagi"), "-")
        text += f"📋 Sabab: {reason_label}\n"

        type_label = crud.RETURN_TYPE_LABELS.get(refund_type, refund_type)
        text += f"💳 Turi: <b>{type_label}</b>\n"

        if refund_type == "exchange":
            ex_name = data.get("exchange_product_name", "?")
            ex_qty = float(data.get("exchange_quantity") or 0)
            ex_unit = data.get("exchange_unit", "")
            text += (
                f"🔄 Yangi mahsulot: {html.escape(ex_name)} x {_qty_text(ex_qty)} {ex_unit}\n"
                f"💰 Yangi qiymat: {format_currency(exchange_value)} so'm\n"
            )
            diff = exchange_value - x_value
            if abs(diff) >= 1:
                pay_method = data.get("pay_method") or "cash"
                pay_label = "💵 Naqd" if pay_method == "cash" else "💳 Karta"
                if diff > 0:
                    text += f"➕ Farq (mijoz to'laydi): {format_currency(diff)} so'm ({pay_label})\n"
                else:
                    text += f"➖ Farq (qaytariladi): {format_currency(abs(diff))} so'm ({pay_label})\n"
        elif refund_type == "bonus":
            data_qty = float(data.get("quantity") or 0)
            bonus = crud.calc_loyalty_points(x_value)
            text += f"🎁 Bonus ball: <b>{bonus}</b> ball\n"
        elif refund_type in ("cash", "card"):
            text += f"💵 Qaytariladigan pul: <b>{format_currency(x_value)} so'm</b>\n"

        text += "\nTasdiqlaysizmi?"
        await message.answer(
            text,
            reply_markup=_inline_buttons([
                ("✅ Tasdiqlash", "ret_confirm"),
                ("❌ Bekor qilish", "ret_cancel"),
            ]),
            parse_mode="HTML",
        )


@returns_router.callback_query(F.data == "ret_confirm", ReturnStates.pay_method)
async def return_confirm(callback: types.CallbackQuery, state: FSMContext):
    """Qaytarish aktini yakunlash"""
    await callback.answer()
    data = await state.get_data()

    try:
        with get_db_session() as db:
            refund_method = None
            refund_type = data.get("refund_type", "cash")
            if refund_type in ("cash", "card"):
                refund_method = refund_type
            elif refund_type == "exchange":
                refund_method = data.get("pay_method")

            act = crud.create_return_act(
                db,
                sale_id=data.get("sale_id"),
                quantity=float(data.get("quantity") or 0),
                reason=data.get("reason", "mijoz_istagi"),
                refund_type=refund_type,
                exchange_product_id=data.get("exchange_product_id"),
                exchange_quantity=float(data.get("exchange_quantity")) if data.get("exchange_quantity") else None,
                refund_method=refund_method,
                user_id=callback.from_user.id,
                user_name=callback.from_user.full_name,
            )
            sale = db.query(models.Sale).filter(models.Sale.id == act.sale_id).first()
            product = db.query(models.Product).filter(models.Product.id == act.product_id).first()

            parts = [
                f"📄 <b>QAYTARISH AKTI</b>\n",
                f"🧾 Akt: {act.act_number}\n",
                f"📅 Sana: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n",
                f"🏭 Mahsulot: {html.escape(act.product_name or '')} x {_qty_text(act.quantity)} {act.unit or ''}\n",
                f"💵 Qiymati: {format_currency(act.total_amount)} so'm\n",
                f"📋 Sabab: {crud.RETURN_REASON_LABELS.get(act.reason, act.reason)}\n",
            ]

            if act.refund_amount > 0:
                is_cash = (act.refund_type == "cash") or (refund_method == "cash")
                method_label = "💵 Naqd" if is_cash else "💳 Karta"
                parts.append(f"💳 Qaytarilgan pul: <b>{format_currency(act.refund_amount)} so'm</b> ({method_label})\n")
            elif act.bonus_points > 0:
                parts.append(f"🎁 Bonus ball: <b>{act.bonus_points:g}</b>\n")
            elif act.debt_reduction > 0:
                parts.append(f"📝 Qarzdan chiqarildi: <b>{format_currency(act.debt_reduction)} so'm</b>\n")
            if act.exchange_product_name:
                parts.append(
                    f"🔄 Almashtirildi: {html.escape(act.exchange_product_name)} x "
                    f"{_qty_text(act.exchange_quantity or 0)}\n"
                )
                if act.extra_amount > 0:
                    parts.append(f"➕ Qo'shimcha to'lov: <b>{format_currency(act.extra_amount)} so'm</b>\n")
            if act.warehouse == "brak":
                parts.append("🏚️ Tovar: brak omboriga qaytarildi\n")
            else:
                parts.append("📦 Tovar omborga qaytarildi\n")
            if act.customer_name:
                parts.append(f"👤 Mijoz: {html.escape(act.customer_name)}\n")

            await callback.message.answer("".join(parts), parse_mode="HTML")

            sms_phone = act.customer_phone or (sale.customer_phone if sale else None)
            if sms_phone:
                asyncio.create_task(_notify_customer(sms_phone, act))
    except ValueError as e:
        await callback.message.answer(f"⛔ {str(e)}", reply_markup=get_main_menu())
    except Exception as e:
        await callback.message.answer(
            f"❌ Xatolik yuz berdi: {str(e)}",
            reply_markup=get_main_menu(),
        )

    await state.clear()


@returns_router.callback_query(F.data == "ret_cancel")
async def return_cancel(callback: types.CallbackQuery, state: FSMContext):
    """Qaytarishni bekor qilish"""
    await callback.answer()
    await state.clear()
    await callback.message.answer("❌ Qaytarish bekor qilindi.", reply_markup=get_main_menu())


async def _notify_customer(phone: str, act: models.ReturnAct):
    """Mijozga SMS: 'Qaytarish amalga oshirildi' (TZ 8-qadam)"""
    try:
        from utils.sms_service import sms_service
        parts = [
            f"Assalomu alaykum! Qaytarish amalga oshirildi.\n",
            f"Akt: {act.act_number}. {act.product_name or ''} x {_qty_text(act.quantity)} {act.unit or ''}",
        ]
        if act.refund_amount > 0:
            parts.append(f"Qaytarilgan pul: {format_currency(act.refund_amount)} so'm.")
        elif act.bonus_points > 0:
            parts.append(f"Bonus ball: {act.bonus_points:g}.")
        elif act.exchange_product_name:
            parts.append(f"Almashtirildi: {act.exchange_product_name}.")
        await sms_service.send_sms(phone, "\n".join(parts))
    except Exception:
        pass


# ==================== QAYTARISHLAR TARIXI ====================

@returns_router.message(F.text == "🧾 Qaytarishlar tarixi", StateFilter(None))
async def return_history(message: types.Message):
    """So'nggi qaytarish aktlari ro'yxati"""
    if not await ensure_access(message, "sales"):
        return

    with get_db_session() as db:
        acts = crud.list_return_acts(db, limit=10)
        if not acts:
            await message.answer("📭 Qaytarish aktlari yo'q.", reply_markup=get_main_menu())
            return

        text = "🧾 <b>QAYTARISH AKTLARI (so'nggi 10):</b>\n\n"
        for a in acts:
            type_label = crud.RETURN_TYPE_LABELS.get(a.refund_type, a.refund_type)
            amount_part = ""
            if a.refund_amount > 0:
                amount_part = f" | 💵 {format_currency(a.refund_amount)} so'm"
            elif a.bonus_points > 0:
                amount_part = f" | 🎁 {a.bonus_points:g} ball"
            elif a.debt_reduction > 0:
                amount_part = f" | 📝 qarz {format_currency(a.debt_reduction)} so'm"
            elif a.exchange_product_name:
                amount_part = f" | 🔄 {a.exchange_product_name}"
            text += (
                f"📄 <b>{a.act_number}</b>{amount_part}\n"
                f"   🏭 {html.escape(a.product_name or '')} x {_qty_text(a.quantity)} {a.unit or ''}\n"
                f"   📅 {a.created_at.strftime('%d.%m.%Y %H:%M') if a.created_at else ''} | "
                f"👤 {html.escape(a.customer_name or '-')}\n\n"
            )
        await message.answer(text[:4000], reply_markup=_sales_menu_keyboard(), parse_mode="HTML")


# ==================== REGISTER ====================

def register_handlers_returns(dp: Dispatcher):
    """Qaytarish handlerlarini Dispatcher'ga qo'shish"""
    dp.include_router(returns_router)
