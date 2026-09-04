"""
Operatsion modullar (v4) — TZ bo'yicha yangi darajaga ko'tarish

- ⛽ Yoqilg'i nazorati: haydovchi quyishni qayd etadi, 100 km ga me'yor hisoblanadi
- 🧾 Avans hisoboti: xodim xarajatini qayd etadi, direktor tasdiqlaydi
- 📦 Yig'ish varaqasi: omborchi buyurtma bo'yicha ro'yxatni yig'adi
- 🚨 Shubhali harakatlar: xavfsizlik ogohlantirishlari (direktor ko'radi)
- 🏆 Sotuvchilar reytingi: eng yaxshi sotuvchilar taxtasi

Foydalanish: /operatsiyalar (yoki admin panelidan) → pastdagi tugmalar
"""

from datetime import datetime

from aiogram import F, Router, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import crud
from database.session import get_db_session
from keyboards.main_menu import get_main_menu
from utils.access import ensure_access, get_user_role

ops_router = Router()


class FuelStates(StatesGroup):
    liters = State()
    odometer = State()
    price = State()


class ExpenseStates(StatesGroup):
    category = State()
    amount = State()
    description = State()


# ==================== ASOSIY MENYU ====================

@ops_router.message(Command("operatsiyalar"))
@ops_router.message(F.text == "⚙️ Operatsiyalar")
async def operations_menu(message: types.Message):
    """Operatsion modullar menyusi"""
    with get_db_session() as db:
        role = get_user_role(db, message.from_user.id)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⛽ Yoqilg'i qayd etish", callback_data="ops_fuel_add")],
        [types.InlineKeyboardButton(text="📊 Yoqilg'i samaradorligi", callback_data="ops_fuel_stats")],
        [types.InlineKeyboardButton(text="🧾 Avans hisoboti yuborish", callback_data="ops_expense_add")],
        [types.InlineKeyboardButton(text="📑 Avanslar nazorati", callback_data="ops_expense_list")],
        [types.InlineKeyboardButton(text="📦 Yig'ish varaqalari", callback_data="ops_picking_list")],
        [types.InlineKeyboardButton(text="🚨 Shubhali harakatlar", callback_data="ops_security_list")],
        [types.InlineKeyboardButton(text="🏆 Sotuvchilar reytingi", callback_data="ops_ratings")],
        [types.InlineKeyboardButton(text="❌ Yopish", callback_data="ops_close")],
    ])
    role_note = "" if role in ("direktor", "admin") else "\n\nℹ️ Sizga faqat o'z huquqingiz bo'lgan bo'limlar ko'rinadi."
    await message.answer(
        "⚙️ <b>Operatsion modullar</b>\n\n"
        "TZ bo'yicha qo'shilgan samaradorlik vositalari:"
        "\n• <b>Yoqilg'i nazorati</b> — har bir quyish qayd etiladi, 100 km ga me'yor bilan solishtiriladi"
        "\n• <b>Avans hisoboti</b> — xarajat tasdiqlash oqimi"
        "\n• <b>Yig'ish varaqasi</b> — ombor yig'ish ro'yxati"
        "\n• <b>Xavfsizlik</b> — shubhali harakatlar detektori"
        "\n• <b>Reyting</b> — sotuvchilar taxtasi" + role_note,
        reply_markup=kb, parse_mode="HTML",
    )


@ops_router.callback_query(F.data == "ops_close")
async def ops_close(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer("⚙️ Operatsiyalar yopildi.", reply_markup=get_main_menu(callback.from_user.id))


@ops_router.callback_query(F.data.startswith("ops_"))
async def ops_callback_gateway(callback: types.CallbackQuery, state: FSMContext):
    """Ruxsatni tekshirib, tegishli amalga yo'naltiradi"""
    data = callback.data
    module_map = {
        "ops_fuel_add": ("fuel", False),
        "ops_fuel_stats": ("fuel", False),
        "ops_expense_add": ("expenses", False),
        "ops_expense_list": ("expenses", False),
        "ops_picking_list": ("picking", False),
        "ops_security_list": ("security", False),
        "ops_ratings": ("ratings", False),
    }
    if data not in module_map:
        await callback.answer()
        return
    module, _ = module_map[data]
    if not await ensure_access(callback, module, edit=False):
        return

    if data == "ops_fuel_add":
        await fuel_add_start(callback, state)
    elif data == "ops_fuel_stats":
        await fuel_stats(callback)
    elif data == "ops_expense_add":
        await expense_add_start(callback, state)
    elif data == "ops_expense_list":
        await expense_list(callback)
    elif data == "ops_picking_list":
        await picking_list(callback)
    elif data == "ops_security_list":
        await security_list(callback)
    elif data == "ops_ratings":
        await ratings_show(callback)


# ==================== YOQILG'I ====================

async def fuel_add_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    with get_db_session() as db:
        role = get_user_role(db, callback.from_user.id)
    if role == "haydovchi":
        driver_name = (callback.from_user.full_name or "").strip()
    else:
        driver_name = None
    await state.set_state(FuelStates.liters)
    await state.update_data(driver_name=driver_name)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[
        types.InlineKeyboardButton(text="❌ Bekor", callback_data="ops_cancel"),
    ]])
    await callback.message.answer(
        "⛽ <b>Yoqilg'i quyish qaydi</b>\n\n"
        "Quyilgan <b>litr</b>ni kiriting (masalan: 45):",
        reply_markup=kb, parse_mode="HTML",
    )


@ops_router.message(FuelStates.liters)
async def fuel_get_liters(message: types.Message, state: FSMContext):
    try:
        liters = float(message.text.strip().replace(",", "."))
        if liters <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Litrni to'g'ri kiriting (masalan: 45)")
        return
    await state.update_data(liters=liters)
    await state.set_state(FuelStates.odometer)
    await message.answer("📟 Spidometr ko'rsatkichi (km):\n(maydon, bilmasangiz 0 yozing)")


@ops_router.message(FuelStates.odometer)
async def fuel_get_odometer(message: types.Message, state: FSMContext):
    raw = message.text.strip().replace(" ", "").replace(",", ".")
    try:
        odometer = float(raw) if raw not in ("", "0") else None
    except ValueError:
        odometer = None
    await state.update_data(odometer=odometer)
    await state.set_state(FuelStates.price)
    await message.answer("💰 1 litr narxi (so'm):\n(a - o'tkazib yuborish)")


@ops_router.message(FuelStates.price)
async def fuel_get_price(message: types.Message, state: FSMContext):
    raw = message.text.strip().replace(" ", "").replace(",", ".")
    try:
        price = float(raw) if raw.lower() not in ("a", "0") else None
    except ValueError:
        price = None
    data = await state.get_data()
    with get_db_session() as db:
        entry = crud.create_fuel_log(db, {
            "driver_id": None,
            "driver_name": data.get("driver_name"),
            "odometer_km": data.get("odometer"),
            "liters": data.get("liters"),
            "price_per_liter": price,
            "created_by": message.from_user.full_name or message.from_user.username or "",
        })
        total = entry.total_cost
    await state.clear()
    await message.answer(
        f"✅ <b>Yoqilg'i qaydi saqlandi</b>\n\n"
        f"⛽ Litr: <b>{data['liters']:g}</b>\n"
        f"💵 Jami xarajat: <b>{total:,.0f} so'm</b>" if total else
        f"✅ <b>Yoqilg'i qaydi saqlandi</b>\n\n⛽ Litr: <b>{data['liters']:g}</b>",
        parse_mode="HTML",
    )


async def fuel_stats(callback: types.CallbackQuery):
    await callback.answer()
    with get_db_session() as db:
        stats = crud.get_fuel_efficiency(db, days=30)
        logs = crud.list_fuel_logs(db, limit=5)
    lines = [
        "📊 <b>Yoqilg'i samaradorligi (30 kun)</b>", "",
        f"Quyishlar soni: <b>{stats['logs_count']}</b>",
        f"Jami yoqilg'i: <b>{stats['total_liters']:,.1f} L</b>",
        f"Jami xarajat: <b>{stats['total_cost']:,.0f} so'm</b>",
    ]
    if stats["avg_liters_per_100km"] is not None:
        lines += [
            f"O'rtacha sarf: <b>{stats['avg_liters_per_100km']:,.2f} L/100 km</b>"
            f" (me'yor: {stats['norm_liters_per_100km']:g})",
        ]
        if stats["over_norm"]:
            lines.append(f"⚠️ <b>Me'yordan {stats['over_norm_pct']}% oshgan!</b>")
        else:
            lines.append("✅ Me'yor doirasida")
    else:
        lines.append("ℹ️ Samaradorlikni hisoblash uchun spidometr ko'rsatkichlari kerak")
    if logs:
        lines += ["", "🕐 <b>So'nggi qaydlar:</b>"]
        for l in logs:
            lines.append(
                f"• {l.created_at.strftime('%d.%m %H:%M') if l.created_at else '—'} — "
                f"{l.driver_name or 'Haydovchi'}: {l.liters:g} L / {l.total_cost:,.0f} so'm"
            )
    await callback.message.answer("\n".join(lines), parse_mode="HTML")


# ==================== AVANS HISOBOti ====================

async def expense_add_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ExpenseStates.category)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⛽ Yoqilg'i", callback_data="exp_cat_yoqilgi"),
         types.InlineKeyboardButton(text="🚗 Yo'l haqi", callback_data="exp_cat_yol_hagi")],
        [types.InlineKeyboardButton(text="🍽 Ovqat", callback_data="exp_cat_ovqat"),
         types.InlineKeyboardButton(text="📦 Boshqa", callback_data="exp_cat_boshqa")],
        [types.InlineKeyboardButton(text="❌ Bekor", callback_data="ops_cancel")],
    ])
    await callback.message.answer(
        "🧾 <b>Avans hisoboti</b>\n\nXarajat turini tanlang:",
        reply_markup=kb, parse_mode="HTML",
    )


@ops_router.callback_query(F.data.startswith("exp_cat_"))
async def expense_category_cb(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    category = callback.data.replace("exp_cat_", "")
    await state.update_data(category=category)
    await state.set_state(ExpenseStates.amount)
    await callback.message.answer("💵 Xarajat summasini kiriting (so'm):")


@ops_router.message(ExpenseStates.amount)
async def expense_get_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(" ", "").replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Summani to'g'ri kiriting")
        return
    await state.update_data(amount=amount)
    await state.set_state(ExpenseStates.description)
    await message.answer("📝 Qisqa izoh (masalan: 'Toshkentga yo'l'):")


@ops_router.message(ExpenseStates.description)
async def expense_get_description(message: types.Message, state: FSMContext):
    data = await state.get_data()
    with get_db_session() as db:
        report = crud.create_expense_report(db, {
            "employee_name": message.from_user.full_name or message.from_user.username or "",
            "category": data.get("category", "boshqa"),
            "amount": data.get("amount"),
            "description": (message.text or "").strip() or None,
            "created_by": message.from_user.full_name or message.from_user.username or "",
        })
    await state.clear()
    await message.answer(
        f"✅ <b>Avans hisoboti yuborildi</b>\n\n"
        f"📄 Raqam: <b>{report.report_number}</b>\n"
        f"🏷 Tur: <b>{report.category}</b>\n"
        f"💵 Summa: <b>{report.amount:,.0f} so'm</b>\n\n"
        f"⏳ Direktor tasdiqlashini kuting.",
        parse_mode="HTML",
    )


async def expense_list(callback: types.CallbackQuery):
    await callback.answer()
    with get_db_session() as db:
        pending = crud.list_expense_reports(db, status="kutilmoqda", limit=15)
        totals = crud.get_expense_totals(db, days=30)
    lines = ["📑 <b>Avans hisobotlari</b>", "",
             f"✅ Tasdiqlangan (30 kun): <b>{totals['approved_total']:,.0f} so'm</b>"]
    if pending:
        kb_rows = []
        for r in pending:
            lines.append(
                f"\n<b>{r.report_number}</b> — {r.employee_name or '—'}\n"
                f"💵 {r.amount:,.0f} so'm · {r.category}"
            )
            kb_rows.append([types.InlineKeyboardButton(
                text=f"✅ {r.report_number} tasdiqlash", callback_data=f"exp_review_{r.id}_tasdiqlangan")])
            kb_rows.append([types.InlineKeyboardButton(
                text=f"❌ {r.report_number} rad etish", callback_data=f"exp_review_{r.id}_rad_etilgan")])
        kb = types.InlineKeyboardMarkup(inline_keyboard=kb_rows)
    else:
        lines.append("\n🎉 Kutilayotgan hisobotlar yo'q.")
        kb = None
    await callback.message.answer("\n".join(lines), reply_markup=kb, parse_mode="HTML")


@ops_router.callback_query(F.data.startswith("exp_review_"))
async def expense_review_cb(callback: types.CallbackQuery):
    """Faqat direktor/buxgalter xarajatni tasdiqlay oladi"""
    if not await ensure_access(callback, "expenses", edit=True):
        return
    parts = callback.data.split("_")
    report_id = int(parts[2])
    status = parts[3]
    with get_db_session() as db:
        crud.review_expense_report(
            db, report_id, status,
            reviewed_by=callback.from_user.full_name or callback.from_user.username,
        )
    await callback.answer("✅ Holat yangilandi")
    await callback.message.delete()
    await expense_list(callback)


# ==================== YIG'ISH VARAQASI ====================

async def picking_list(callback: types.CallbackQuery):
    await callback.answer()
    with get_db_session() as db:
        pending = crud.list_picking_lists(db, limit=20)
    if not pending:
        await callback.message.answer("📦 Yig'ish varaqalari yo'q.", parse_mode="HTML")
        return
    lines = ["📦 <b>Yig'ish varaqalari</b>", ""]
    kb_rows = []
    for p in pending:
        status_icon = {"yangi": "🆕", "tayyor": "✅", "yuborilgan": "🚚"}.get(p.status, "🆕")
        lines.append(
            f"{status_icon} <b>{p.picking_number}</b> — {p.product_name}\n"
            f"   Miqdor: {p.quantity:g} {p.unit or ''} · Sektor: {p.sector or '—'} · Holat: {p.status}"
        )
        if p.status == "yangi":
            kb_rows.append([types.InlineKeyboardButton(
                text=f"✅ {p.picking_number} tayyor", callback_data=f"pkg_{p.id}_tayyor")])
    kb = types.InlineKeyboardMarkup(inline_keyboard=kb_rows) if kb_rows else None
    await callback.message.answer("\n".join(lines), reply_markup=kb, parse_mode="HTML")


@ops_router.callback_query(F.data.startswith("pkg_"))
async def picking_update_cb(callback: types.CallbackQuery):
    if not await ensure_access(callback, "picking", edit=True):
        return
    parts = callback.data.split("_")
    picking_id = int(parts[1])
    status = parts[2]
    with get_db_session() as db:
        crud.update_picking_status(
            db, picking_id, status,
            picked_by=callback.from_user.full_name or callback.from_user.username,
        )
    await callback.answer("✅ Yig'ish tayyor deb belgilandi")
    await callback.message.delete()
    await picking_list(callback)


# ==================== SHUBHALI HARAKATLAR ====================

async def security_list(callback: types.CallbackQuery):
    await callback.answer()
    with get_db_session() as db:
        acts = crud.list_suspicious_activities(db, limit=15)
    severity_icon = {"high": "🔴", "medium": "🟠", "low": "🟡"}.get
    if not acts:
        await callback.message.answer("🚨 Shubhali harakatlar yo'q — hammasi tinch. ✅")
        return
    lines = ["🚨 <b>Shubhali harakatlar</b>", ""]
    kb_rows = []
    for a in acts:
        icon = severity_icon(a.severity, "🟡")
        lines.append(
            f"{icon} <b>{a.activity_type}</b> ({a.severity})\n"
            f"   {a.description or ''} · {a.user_name or '—'}\n"
            f"   🕐 {a.created_at.strftime('%d.%m %H:%M') if a.created_at else ''} · Holat: {a.status}"
        )
        if a.status in ("yangi", "ko'rib_chiqilgan"):
            kb_rows.append([types.InlineKeyboardButton(
                text=f"✅ #{a.id} hal qilindi", callback_data=f"sec_{a.id}_hal_qilingan")])
    kb = types.InlineKeyboardMarkup(inline_keyboard=kb_rows) if kb_rows else None
    await callback.message.answer("\n".join(lines), reply_markup=kb, parse_mode="HTML")


@ops_router.callback_query(F.data.startswith("sec_"))
async def security_update_cb(callback: types.CallbackQuery):
    if not await ensure_access(callback, "security", edit=True):
        return
    parts = callback.data.split("_")
    act_id = int(parts[1])
    status = parts[2]
    with get_db_session() as db:
        crud.update_suspicious_status(db, act_id, status)
    await callback.answer("✅ Holat yangilandi")
    await callback.message.delete()
    await security_list(callback)


# ==================== SOTUVCHILAR REYTINGI ====================

async def ratings_show(callback: types.CallbackQuery):
    await callback.answer()
    with get_db_session() as db:
        ratings = crud.get_seller_ratings(db, days=30, limit=10)
    if not ratings:
        await callback.message.answer("🏆 Hozircha savdo qaydlari yo'q.")
        return
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = ["🏆 <b>Sotuvchilar reytingi (30 kun)</b>", ""]
    for r in ratings:
        medal = medals.get(r["rank"], f"{r['rank']}.")
        lines.append(
            f"{medal} <b>{r['seller']}</b>\n"
            f"   💵 {r['total_sales']:,.0f} so'm · {r['sales_count']} ta savdo · "
            f"o'rtacha {r['avg_check']:,.0f} so'm"
        )
    await callback.message.answer("\n".join(lines), parse_mode="HTML")


# ==================== BEKOR ====================

@ops_router.callback_query(F.data == "ops_cancel")
async def ops_cancel(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("❌ Amal bekor qilindi.", reply_markup=get_main_menu(callback.from_user.id))


# ==================== REGISTER ====================

def register_handlers_operations(dp: Dispatcher):
    """Operatsion modul handlerlarini Dispatcher'ga qo'shish"""
    dp.include_router(ops_router)