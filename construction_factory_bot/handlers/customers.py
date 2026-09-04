"""
Mijozlar (CRM) moduli — v3
Mijoz kartasi, nasiya limiti, qarz to'lovi, sodiqlik ballari
"""
from datetime import datetime

from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.session import get_db_session
from database import models, crud
from keyboards.main_menu import get_crm_menu, get_main_menu
from utils.access import ensure_access, get_user_role, role_label
from utils.helpers import validate_phone, normalize_phone, parse_float_input
from config import role_can_edit


class CustomerStates(StatesGroup):
    waiting_name = State()
    waiting_phone = State()
    waiting_company = State()
    waiting_credit_limit = State()
    waiting_search = State()
    waiting_debt_customer = State()
    waiting_debt_amount = State()
    waiting_debt_method = State()


# =============== ENTRY ===============
async def crm_menu(message: types.Message):
    if not await ensure_access(message, "crm"):
        return
    with get_db_session() as db:
        role = role_label(db, message.from_user.id)
    await message.answer(
        f"👥 <b>MIJOZLAR (CRM)</b>\n\n"
        f"Rolingiz: {role}\n"
        f"Mijozlar bazasi, nasiya va qarz boshqaruvi.",
        reply_markup=get_crm_menu(), parse_mode="HTML"
    )


# =============== YANGI MIJOZ ===============
async def add_customer_start(message: types.Message, state: FSMContext):
    if not await ensure_access(message, "crm", edit=True):
        return
    await state.clear()
    await message.answer("👤 Mijozning to'liq ismini kiriting:")
    await CustomerStates.waiting_name.set()


async def process_customer_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(
        "📞 Telefon raqamini kiriting (masalan +998901234567).\n"
        "Agar bo'lmasa — 0 deb yozing:"
    )
    await CustomerStates.waiting_phone.set()


async def process_customer_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    if phone != "0" and not validate_phone(phone):
        await message.answer("❌ Telefon formati noto'g'ri. To'g'ri format: +998901234567")
        return
    phone = normalize_phone(phone) if phone != "0" else None

    with get_db_session() as db:
        if phone and crud.get_customer_by_phone(db, phone):
            await message.answer("❌ Bu telefon raqamli mijoz allaqachon mavjud. Qidiruvdan foydalaning.")
            await state.clear()
            return

    await state.update_data(phone=phone)
    await message.answer(
        "🏢 Kompaniya/tashkilot nomi (agar pudratchi firma bo'lsa).\n"
        "Bo'lmasa — 0 deb yozing:"
    )
    await CustomerStates.waiting_company.set()


async def process_customer_company(message: types.Message, state: FSMContext):
    company = message.text.strip()
    await state.update_data(company=None if company == "0" else company)
    await message.answer(
        "💰 Nasiya (kredit) limitini kiriting (so'mda).\n"
        "Nasiya sotuvini yoqmaslik uchun 0 kiriting.\n"
        "Masalan: 5000000"
    )
    await CustomerStates.waiting_credit_limit.set()


async def process_credit_limit(message: types.Message, state: FSMContext):
    limit = parse_float_input(message.text)
    if limit is None:
        await message.answer("❌ Faqat raqam kiriting. Masalan: 5000000")
        return
    if limit < 0:
        await message.answer("❌ Kredit limiti manfiy bo'lishi mumkin emas:")
        return
    data = await state.get_data()
    with get_db_session() as db:
        customer = crud.create_customer(db, {
            "name": data["name"],
            "phone": data.get("phone"),
            "company": data.get("company"),
            "credit_limit": limit,
        })
        crud.create_system_log(db, user_id=message.from_user.id,
                               user_name=message.from_user.full_name,
                               action=f"Yangi mijoz qo'shildi: {customer.name}",
                               module="crm")
        cid = customer.id
    await state.clear()
    await message.answer(
        f"✅ <b>Mijoz qo'shildi!</b>\n\n"
        f"👤 {customer.name}\n"
        f"📞 {customer.phone or '-'}\n"
        f"🏢 {customer.company or '-'}\n"
        f"💰 Kredit limiti: {limit:,.0f} so'm",
        reply_markup=get_crm_menu(), parse_mode="HTML"
    )


# =============== QIDIRISH ===============
async def customer_search_start(message: types.Message, state: FSMContext):
    await message.answer("🔍 Ism, telefon yoki kompaniya bo'yicha qidiring:")
    await CustomerStates.waiting_search.set()


async def process_customer_search(message: types.Message, state: FSMContext):
    query = message.text.strip()
    if not query or query == "🔍 Mijoz qidirish":
        await message.answer("❌ Qidiruv so'zini kiriting")
        return
    with get_db_session() as db:
        results = crud.search_customers(db, query)
        if not results:
            await message.answer("❌ Hech narsa topilmadi.")
            await state.clear()
            return
        rows = [[types.InlineKeyboardButton(
            text=f"{c.name} — qarz: {c.total_debt:,.0f} so'm",
            callback_data=f"crm_view_{c.id}"
        )] for c in results]
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=rows)
        await message.answer(f"🔍 Topildi: {len(results)} ta", reply_markup=keyboard)
    await state.clear()


# =============== BARCHA MIJOZLAR ===============
async def all_customers(message: types.Message):
    with get_db_session() as db:
        customers = crud.list_customers(db, limit=30)
        if not customers:
            await message.answer("📭 Hozircha mijozlar yo'q. ➕ Yangi mijoz qo'shing.",
                                 reply_markup=get_crm_menu())
            return
        text = f"👥 <b>MIJOZLAR ({len(customers)})</b>\n\n"
        for i, c in enumerate(customers, 1):
            debt_icon = "🟢" if c.total_debt <= 0 else "🔴"
            text += (
                f"{i}. {debt_icon} <b>{c.name}</b>\n"
                f"   📞 {c.phone or '-'} | 💰 Qarz: {c.total_debt:,.0f} so'm\n"
                f"   🏢 {c.company or '-'} | 🎖️ {c.loyalty_points or 0} ball\n\n"
            )
        await message.answer(text[:4000], parse_mode="HTML")


# =============== MIJOZ KARTASI ===============
async def customer_card(callback: types.CallbackQuery):
    await callback.answer()
    cid = int(callback.data.replace("crm_view_", ""))
    with get_db_session() as db:
        customer = crud.get_customer(db, cid)
        if not customer:
            await callback.message.answer("❌ Mijoz topilmadi.")
            return
        sales = db.query(models.Sale).filter(models.Sale.customer_id == cid).order_by(
            models.Sale.sale_date.desc()
        ).limit(5).all()
        payments = db.query(models.Payment).filter(models.Payment.customer_id == cid).order_by(
            models.Payment.created_at.desc()
        ).limit(5).all()

        free_limit = (customer.credit_limit or 0) - (customer.total_debt or 0)
        from database.crud import calculate_customer_tier, get_customer_tier_label
        tier = calculate_customer_tier(db, customer)
        card = (
            f"👤 <b>{customer.name}</b>\n\n"
            f"📞 Telefon: {customer.phone or '-'}\n"
            f"🏢 Kompaniya: {customer.company or '-'}\n"
            f"📍 Manzil: {customer.address or '-'}\n"
            f"🔖 Holat: {customer.status}\n"
            f"{get_customer_tier_label(tier)}\n\n"
            f"💰 Kredit limiti: {customer.credit_limit or 0:,.0f} so'm\n"
            f"🔴 Joriy qarz: {customer.total_debt or 0:,.0f} so'm\n"
            f"🟢 Bo'sh limit: {max(free_limit, 0):,.0f} so'm\n"
            f"📈 Jami xarid: {customer.total_purchases or 0:,.0f} so'm\n"
            f"🎖️ Loyallik ballari: {customer.loyalty_points or 0}\n\n"
            f"📋 <b>Oxirgi xaridlar:</b>\n"
        )
        if not sales:
            card += "   Yo'q\n"
        for s in sales:
            card += f"   • {s.invoice_number}: {s.total_amount:,.0f} so'm ({s.payment_method})\n"
        card += "\n💳 <b>Oxirgi to'lovlar:</b>\n"
        if not payments:
            card += "   Yo'q\n"
        for p in payments:
            card += f"   • {p.amount:,.0f} so'm ({p.method}, {p.payment_type})\n"

        rows = []
        if (customer.total_debt or 0) > 0:
            rows.append([types.InlineKeyboardButton(
                text="🧾 Qarz to'lash", callback_data=f"crm_pay_{customer.id}"
            )])
        rows.append([types.InlineKeyboardButton(
            text="📝 Nasiya tarixi", callback_data=f"crm_credit_{customer.id}"
        )])
        await callback.message.answer(card, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows),
                                      parse_mode="HTML")


# =============== NASIYA TARIXI ===============
async def customer_credit_history(callback: types.CallbackQuery):
    await callback.answer()
    cid = int(callback.data.replace("crm_credit_", ""))
    with get_db_session() as db:
        credit_sales = db.query(models.Sale).filter(
            models.Sale.customer_id == cid,
            models.Sale.is_credit == True,
        ).order_by(models.Sale.sale_date.desc()).limit(10).all()
        if not credit_sales:
            await callback.message.answer("📭 Nasiya sotuvlari yo'q.")
            return
        text = "📝 <b>NASIYA SOTUVLARI</b>\n\n"
        for s in credit_sales:
            remaining = (s.total_amount or 0) - (s.paid_amount or 0)
            text += (
                f"🧾 {s.invoice_number}\n"
                f"   Summa: {s.total_amount:,.0f} so'm | To'langan: {s.paid_amount:,.0f}\n"
                f"   Qoldiq: {remaining:,.0f} so'm | Holat: {s.credit_status}\n"
                f"   Muddati: {s.due_date.strftime('%d.%m.%Y') if s.due_date else '-'}\n\n"
            )
        await callback.message.answer(text[:4000], parse_mode="HTML")


# =============== QARZ TO'LOVI ===============
async def debt_payment_start(message: types.Message, state: FSMContext):
    # Ruxsat: qarz to'lovi — crm YOKI finance bo'limini tahrirlay oladigan rol uchun ochiq.
    # (Ikkita ensure_access ketma-ket chaqirilsa, ruxsatsiz foydalanuvchiga 2 xil xato xabari ketadi)
    with get_db_session() as db:
        role = get_user_role(db, message.from_user.id)
        allowed = role_can_edit(role, "finance") or role_can_edit(role, "crm")
        role_text = role_label(db, message.from_user.id)
    if not allowed:
        await message.answer(
            f"❌ Ruxsat yo'q!\nSizning rolingiz: {role_text}\n"
            f"Qarz to'lovi (finance/crm) sizga ochiq emas."
        )
        return
    with get_db_session() as db:
        debtors = db.query(models.Customer).filter(models.Customer.total_debt > 0).order_by(
            models.Customer.total_debt.desc()
        ).all()
        if not debtors:
            await message.answer("🎉 Barcha mijozlar qarzini to'lagan!",
                                 reply_markup=get_crm_menu())
            await state.clear()
            return
        rows = [[types.InlineKeyboardButton(
            text=f"{c.name} — {c.total_debt:,.0f} so'm",
            callback_data=f"debt_sel_{c.id}"
        )] for c in debtors]
        await message.answer("🧾 <b>QARZ TO'LOVI</b>\n\nQarzi bor mijozni tanlang:",
                             reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows),
                             parse_mode="HTML")


async def debt_select_customer(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    cid = int(callback.data.replace("debt_sel_", ""))
    with get_db_session() as db:
        c = crud.get_customer(db, cid)
        if not c:
            await callback.message.answer("❌ Mijoz topilmadi.")
            await state.clear()
            return
        await state.update_data(debt_customer_id=cid)
        await callback.message.answer(
            f"🧾 {c.name} qarzi: <b>{c.total_debt:,.0f} so'm</b>\n\n"
            f"Qancha to'lanadi (so'm)?", parse_mode="HTML"
        )
    await CustomerStates.waiting_debt_amount.set()


async def process_debt_amount(message: types.Message, state: FSMContext):
    amount = parse_float_input(message.text)
    if amount is None:
        await message.answer("❌ Faqat raqam kiriting:")
        return
    if amount <= 0:
        await message.answer("❌ Miqdor 0 dan katta bo'lishi kerak:")
        return
    data = await state.get_data()
    with get_db_session() as db:
        c = crud.get_customer(db, data["debt_customer_id"])
        if not c:
            await message.answer("❌ Mijoz topilmadi.")
            await state.clear()
            return
        if amount > (c.total_debt or 0):
            await message.answer(f"❌ Qarzdan ortiq summa kiritdingiz. Maksimal: {c.total_debt:,.0f} so'm")
            return
    await state.update_data(debt_amount=amount)
    # To'lov usulini tanlash
    rows = [[types.InlineKeyboardButton(text="💵 Naqd", callback_data="dmethod_cash"),
             types.InlineKeyboardButton(text="💳 Karta", callback_data="dmethod_card")],
            [types.InlineKeyboardButton(text="📱 Payme", callback_data="dmethod_payme"),
             types.InlineKeyboardButton(text="📱 Click", callback_data="dmethod_click")],
            [types.InlineKeyboardButton(text="🏦 O'tkazma", callback_data="dmethod_transfer")]]
    await message.answer("💳 To'lov usulini tanlang:",
                         reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows))
    await CustomerStates.waiting_debt_method.set()


async def process_debt_method(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    method = callback.data.replace("dmethod_", "")
    data = await state.get_data()
    with get_db_session() as db:
        c = crud.get_customer(db, data["debt_customer_id"])
        if not c:
            await state.clear()
            await callback.message.answer("❌ Mijoz topilmadi. To'lov amalga oshirilmadi.",
                                          reply_markup=get_crm_menu())
            return
        result = crud.pay_customer_debt(
            db, data["debt_customer_id"], data["debt_amount"],
            method=method, created_by=callback.from_user.full_name,
        )
        crud.create_system_log(db, user_id=callback.from_user.id,
                               user_name=callback.from_user.full_name,
                               action=f"Qarz to'lovi: {c.name} {data['debt_amount']:,.0f} so'm ({method})",
                               module="crm")
    await state.clear()
    if result:
        await callback.message.answer(
            f"✅ <b>Qarz to'lovi qabul qilindi!</b>\n\n"
            f"👤 Mijoz: {c.name}\n"
            f"💵 Summa: {data['debt_amount']:,.0f} so'm ({method})\n"
            f"🔴 Qolgan qarz: {result['new_debt']:,.0f} so'm",
            reply_markup=get_crm_menu(), parse_mode="HTML"
        )
    else:
        await callback.message.answer("❌ Xatolik yuz berdi.", reply_markup=get_crm_menu())


# =============== MIJOZ KARTASIDAN QARZ TO'LOVI ===============
async def crm_card_pay(callback: types.CallbackQuery, state: FSMContext):
    """Mijoz kartasidagi "Qarz to'lash" tugmasi — to'lov oqimini boshlaydi"""
    await callback.answer()
    with get_db_session() as db:
        role = get_user_role(db, callback.from_user.id)
        allowed = role_can_edit(role, "finance") or role_can_edit(role, "crm")
        role_text = role_label(db, callback.from_user.id)
    if not allowed:
        await callback.message.answer(
            f"❌ Ruxsat yo'q!\nSizning rolingiz: {role_text}\n"
            f"Qarz to'lovi (finance/crm) sizga ochiq emas."
        )
        return
    cid = int(callback.data.replace("crm_pay_", ""))
    with get_db_session() as db:
        c = crud.get_customer(db, cid)
        if not c:
            await callback.message.answer("❌ Mijoz topilmadi.")
            return
        if not (c.total_debt or 0) > 0:
            await callback.message.answer(f"✅ {c.name} mijozining qarzi yo'q.")
            return
        await state.update_data(debt_customer_id=cid)
        await callback.message.answer(
            f"🧾 {c.name} qarzi: <b>{c.total_debt:,.0f} so'm</b>\n\n"
            f"Qancha to'lanadi (so'm)?", parse_mode="HTML"
        )
    await CustomerStates.waiting_debt_amount.set()


# =============== CRM STATISTIKA ===============
async def crm_statistics(message: types.Message):
    with get_db_session() as db:
        total = db.query(models.Customer).count()
        debtors = db.query(models.Customer).filter(models.Customer.total_debt > 0).count()
        total_debt = db.query(models.Customer).with_entities(
            models.Customer.total_debt
        ).all()
        total_debt_sum = sum(c.total_debt or 0 for c in total_debt)
        wholesale = db.query(models.Customer).filter(models.Customer.is_wholesale == True).count()
        top = db.query(models.Customer).order_by(models.Customer.total_purchases.desc()).limit(5).all()

        from database.crud import get_customer_segmentation
        seg = get_customer_segmentation(db)
        text = (
            f"📊 <b>CRM STATISTIKA</b>\n\n"
            f"👥 Jami mijozlar: {total}\n"
            f"🏢 Ulgurji mijozlar: {wholesale}\n"
            f"🔴 Qarzdorlar: {debtors}\n"
            f"💰 Umumiy qarz: {total_debt_sum:,.0f} so'm\n\n"
            f"🏅 <b>MIJOZ TRIAJI (segmentatsiya):</b>\n"
            f"• 🏅 Oltin: {seg['gold']} ta\n"
            f"• 🥈 Kumush: {seg['silver']} ta\n"
            f"• 🥉 Bronza: {seg['bronze']} ta\n\n"
            f"🏆 <b>TOP-5 mijozlar (xarid bo'yicha):</b>\n"
        )
        for i, c in enumerate(top, 1):
            text += f"{i}. {c.name} — {c.total_purchases:,.0f} so'm\n"
        await message.answer(text, parse_mode="HTML")


# =============== REGISTER ===============
def register_handlers_customers(dp: Dispatcher):
    dp.message.register(crm_menu, F.text == "👥 Mijozlar")
    dp.message.register(add_customer_start, F.text == "➕ Yangi mijoz")
    dp.message.register(customer_search_start, F.text == "🔍 Mijoz qidirish")
    dp.message.register(all_customers, F.text == "📋 Barcha mijozlar")
    dp.message.register(debt_payment_start, F.text == "🧾 Qarz to'lovi")
    dp.message.register(crm_statistics, F.text == "📊 CRM statistika")

    dp.message.register(process_customer_name, CustomerStates.waiting_name)
    dp.message.register(process_customer_phone, CustomerStates.waiting_phone)
    dp.message.register(process_customer_company, CustomerStates.waiting_company)
    dp.message.register(process_credit_limit, CustomerStates.waiting_credit_limit)
    dp.message.register(process_customer_search, CustomerStates.waiting_search)
    dp.message.register(process_debt_amount, CustomerStates.waiting_debt_amount)

    dp.callback_query.register(customer_card, F.data.startswith("crm_view_"))
    dp.callback_query.register(customer_credit_history, F.data.startswith("crm_credit_"))
    dp.callback_query.register(crm_card_pay, F.data.startswith("crm_pay_"))
    dp.callback_query.register(debt_select_customer, F.data.startswith("debt_sel_"))
    dp.callback_query.register(process_debt_method, F.data.startswith("dmethod_"))
