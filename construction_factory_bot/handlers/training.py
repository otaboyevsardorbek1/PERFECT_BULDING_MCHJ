"""
🎓 Trening simulyatori va v5.3 vositalari (TZ)

- 🎓 Trening simulyatori (TZ: "Eng muhim taklif" — interaktiv o'quv, sertifikat)
- 🚗 Transport vositalari (TZ ERD: vehicles — ko'rish + direktor qo'shish)
- 📅 Xodimlar smenasi kalendari (TZ E-bo'lim)
- 🤔 "Nima bo'lsa?" tahlili (TZ E-bo'lim — narx/chegirma prognozi)
- ⏳ Amal muddati eslatmasi (TZ 3.1/3.2 — yaqinlashgan/o'tgan xom ashyolar)

Foydalanish: asosiy menyudagi tugmalar orqali.
"""

from datetime import datetime

from aiogram import F, Router, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import crud_v5
from database.session import get_db_session
from keyboards.main_menu import get_main_menu
from utils.access import ensure_access, get_user_role

train_router = Router()


class VehicleStates(StatesGroup):
    number = State()
    brand = State()
    capacity = State()
    fuel = State()


# ==================== ASOSIY MENYU ====================

@train_router.message(Command("trening"))
@train_router.message(F.text == "🎓 Trening")
async def training_menu(message: types.Message):
    """Trening simulyatori menyusi (TZ: xodimlar 15 daqiqada o'rganadi)"""
    if not await ensure_access(message, "training", edit=False):
        return
    with get_db_session() as db:
        role = get_user_role(db, message.from_user.id)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📚 Sotuv va kassa", callback_data="train_start_sales")],
        [types.InlineKeyboardButton(text="📦 Ombor va qabul", callback_data="train_start_warehouse")],
        [types.InlineKeyboardButton(text="🚚 Yetkazib berish", callback_data="train_start_delivery")],
        [types.InlineKeyboardButton(text="🔐 Xavfsizlik", callback_data="train_start_security")],
        [types.InlineKeyboardButton(text="❌ Yopish", callback_data="train_close")],
    ])
    await message.answer(
        "🎓 <b>Trening simulyatori</b>\n\n"
        "Tizimni ishlatishni 5 daqiqada o'rganing — savollarga javob bering, "
        "xato qilsangiz to'g'ri javobni ko'rasiz. Yakunda <b>sertifikat</b> olasiz!\n\n"
        f"👤 Sizning rolingiz: <b>{role}</b>",
        reply_markup=kb, parse_mode="HTML",
    )


@train_router.callback_query(F.data == "train_close")
async def train_close(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer("🎓 Trening yopildi.", reply_markup=get_main_menu(callback.from_user.id))


# Savollar: (savol, [variantlar], to'g'ri indeks, izoh)
_TRAIN_QUIZ = {
    "sales": [
        ("Sotuvda tannarxni kim ko'ra oladi?",
         ["Sotuvchi", "Direktor", "Kassir"], 1,
         "TZ: Sotuvchi va kassir tannarxni ko'ra olmaydi (see_cost=False)."),
        ("Sotuvchi 5% dan ortiq chegirma bera oladimi?",
         ["Ha, istalgancha", "Yo'q, direktor tasdig'i kerak", "Faqat 10% gacha"], 1,
         "TZ: 5% dan ortiq chegirma uchun direktor tasdig'i talab qilinadi."),
        ("Nasiya (kredit) sotuvda nima tekshiriladi?",
         ["Mijozning kredit limiti", "Ob-havo", "Mahsulot rangi"], 0,
         "TZ: Mijoz limiti oshsa sotuv bloklanadi yoki direktorga xabar ketadi."),
    ],
    "warehouse": [
        ("Kirimda sifat farqi topilsa nima qilinadi?",
         ["Qaytarish schyot-fakturasi avtomatik yaratiladi", "Hammasi qabul qilinadi", "Hech narsa"], 0,
         "TZ: Farq/sifatsizlikda yetkazib beruvchiga qaytarish hujjati avtomatik tuziladi."),
        ("Har bir operatsiyaga beriladigan kod necha xonali?",
         ["8", "16", "12"], 1,
         "TZ: Tranzaksiya kodi 16 xonali — soliq tekshiruvida hujjat 1 daqiqada topiladi."),
        ("Inventarizatsiyada farq bo'lsa nima yaratiladi?",
         ["Yetishmovchilik dalolatnomasi", "Yangi mahsulot", "Chegirma kuponi"], 0,
         "TZ: Farq bo'lsa 'Yetishmovchilik bayonnomasi' avtomatik yaratiladi."),
    ],
    "delivery": [
        ("Yetkazib berishda mijoz nimani qoldiradi?",
         ["Imzo (PIN/barmoq izi)", "Pul garovi", "Passport nusxasi"], 0,
         "TZ: Yuk hujjatlari — mijoz elektron imzo (PIN yoki barmoq izi) qoldiradi."),
        ("Yoqilg'i me'yordan oshsa kim xabar oladi?",
         ["Direktor", "Mijoz", "Yetkazib beruvchi"], 0,
         "TZ: 1 km ga sarf me'yordan oshsa direktor xabar oladi."),
        ("GPS lokatsiya qancha vaqt oralig'ida yuboriladi?",
         ["Har 30 sekund", "Har 1 soat", "Kuniga bir marta"], 0,
         "TZ: Yetkazib berishda jonli GPS har 30 sekundda yuboriladi."),
    ],
    "security": [
        ("Sessiya tugaganda darajalar qanday bo'ladi?",
         ["Bekor qilinadi", "Saqlanadi", "Oshadi"], 0,
         "TZ: Sessiya tugaganda/logout'da xodimga berilgan darajalar bekor qilinadi."),
        ("2FA (ikki bosqichli tasdiq) kim uchun?",
         ["Barcha xodimlar uchun yoqilishi mumkin", "Faqat mijozlar", "Hech kim"], 0,
         "TZ: Direktor va kassir uchun Google Authenticator 2FA."),
        ("Kechasi (23:00-06:00) katta sotuv qilinsa nima bo'ladi?",
         ["Shubhali harakat sifatida direktor xabar oladi", "Hech narsa", "Sotuv o'chiriladi"], 0,
         "TZ: 'Shubhali harakat detektori' anomaliyani direktor va xavfsizlikka yuboradi."),
    ],
}


@train_router.callback_query(F.data.startswith("train_start_"))
async def train_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    topic = callback.data.replace("train_start_", "")
    questions = _TRAIN_QUIZ.get(topic)
    if not questions:
        await callback.message.answer("❌ Mavzu topilmadi.")
        return
    await state.update_data(train_topic=topic, train_index=0, train_correct=0)
    await show_train_question(callback.message, state, topic, 0)


async def show_train_question(message: types.Message, state: FSMContext, topic: str, index: int):
    questions = _TRAIN_QUIZ[topic]
    if index >= len(questions):
        data = await state.get_data()
        correct = data.get("train_correct", 0)
        total = len(questions)
        mark = "🌟 A'lo!" if correct == total else ("👍 Yaxshi!" if correct >= total * 0.6 else "📖 Qayta o'qish tavsiya etiladi")
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔄 Qaytadan", callback_data="train_retry")],
            [types.InlineKeyboardButton(text="❌ Yopish", callback_data="train_close")],
        ])
        await message.answer(
            f"🎓 <b>SERTIFIKAT</b>\n\n"
            f"🏆 {message.from_user.full_name or 'Xodim'}, siz <b>“{topic}”</b> treningini "
            f"yakunladingiz!\n\n"
            f"✅ To'g'ri javoblar: <b>{correct}/{total}</b> — {mark}\n\n"
            f"Endi tizimda ishlashga tayyorsiz. Ishda omad! 🚀",
            reply_markup=kb, parse_mode="HTML",
        )
        await state.clear()
        return
    question, variants, correct_idx, explain = questions[index]
    buttons = []
    for i, v in enumerate(variants):
        buttons.append([types.InlineKeyboardButton(text=v, callback_data=f"train_ans_{topic}_{index}_{i}")])
    await message.answer(
        f"❓ <b>{(index + 1)}-savol:</b> {question}",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML",
    )


@train_router.callback_query(F.data.startswith("train_ans_"))
async def train_answer(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split("_")
    # train_ans_{topic}_{qindex}_{choice}
    topic = parts[2]
    qindex = int(parts[3])
    choice = int(parts[4])
    questions = _TRAIN_QUIZ[topic]
    question, variants, correct_idx, explain = questions[qindex]
    data = await state.get_data()
    correct = data.get("train_correct", 0)
    if choice == correct_idx:
        correct += 1
        await state.update_data(train_correct=correct)
        text = f"✅ <b>To'g'ri!</b> {variants[choice]}\n💡 {explain}"
    else:
        text = f"❌ <b>Noto'g'ri.</b> To'g'ri javob: <b>{variants[correct_idx]}</b>\n💡 {explain}"
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="➡️ Keyingi savol", callback_data=f"train_next_{topic}_{qindex + 1}")],
    ])
    await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")


@train_router.callback_query(F.data.startswith("train_next_"))
async def train_next(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split("_")
    topic = parts[2]
    nxt = int(parts[3])
    await show_train_question(callback.message, state, topic, nxt)


@train_router.callback_query(F.data == "train_retry")
async def train_retry(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(train_index=0, train_correct=0)
    await show_train_question(callback.message, state, "sales", 0)


# ==================== 🚗 TRANSPORT VOSITALARI (TZ ERD) ====================

@train_router.message(Command("transport"))
@train_router.message(F.text == "🚗 Transport")
async def vehicles_menu(message: types.Message):
    if not await ensure_access(message, "vehicles", edit=False):
        return
    with get_db_session() as db:
        role = get_user_role(db, message.from_user.id)
        vehicles = crud_v5.list_vehicles(db)
    if not vehicles:
        text = "🚗 <b>Transport vositalari</b>\n\nHozircha mashina ro'yxatga olinmagan."
        kb = None
    else:
        lines = ["🚗 <b>Transport vositalari</b>\n"]
        for v in vehicles:
            status_icon = "🟢" if v.status == "faol" else ("🟠" if v.status == "ta'mirda" else "⚫")
            norm = f", norma {v.fuel_norm_per_km} l/km" if v.fuel_norm_per_km else ""
            lines.append(
                f"{status_icon} <b>{v.number}</b> — {v.brand or '-'}\n"
                f"   🚚 Haydovchi: {v.driver_name or '-'} | ⚖️ {v.capacity:,.0f} kg | "
                f"⛽ {v.fuel_type}{norm}"
            )
        text = "\n\n".join(lines)
        kb = None
    add_btn = []
    if role in ("direktor", "admin") or role == "direktor":
        add_btn.append([types.InlineKeyboardButton(text="➕ Yangi mashina qo'shish", callback_data="veh_add")])
    kb = types.InlineKeyboardMarkup(inline_keyboard=add_btn) if add_btn else None
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@train_router.callback_query(F.data == "veh_add")
async def veh_add_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    if not await ensure_access(callback, "vehicles", edit=True):
        return
    await state.set_state(VehicleStates.number)
    await callback.message.answer("🚗 Yangi mashina: <b>davlat raqamini</b> kiriting (masalan: 01 A 123 BB):", parse_mode="HTML")


@train_router.message(VehicleStates.number)
async def veh_number(message: types.Message, state: FSMContext):
    number = (message.text or "").strip()
    if not number:
        await message.answer("❌ Raqam bo'sh bo'lishi mumkin emas. Qayta kiriting:")
        return
    await state.update_data(veh_number=number)
    await state.set_state(VehicleStates.brand)
    await message.answer("📝 <b>Marka/model</b>ni kiriting (masalan: MAN TGS, yoki '-'):", parse_mode="HTML")


@train_router.message(VehicleStates.brand)
async def veh_brand(message: types.Message, state: FSMContext):
    brand = (message.text or "").strip()
    if brand == "-":
        brand = ""
    await state.update_data(veh_brand=brand)
    await state.set_state(VehicleStates.capacity)
    await message.answer("⚖️ <b>Yuk ko'tarish qobiliyati</b> (kg, masalan: 20000):", parse_mode="HTML")


@train_router.message(VehicleStates.capacity)
async def veh_capacity(message: types.Message, state: FSMContext):
    try:
        capacity = float((message.text or "").replace(" ", "").replace(",", "."))
    except ValueError:
        await message.answer("❌ Son kiriting (masalan: 20000):")
        return
    await state.update_data(veh_capacity=capacity)
    await state.set_state(VehicleStates.fuel)
    kb = types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text="⛽ Dizel"), types.KeyboardButton(text="⛽ Benzin")],
        [types.KeyboardButton(text="⛽ Gaz"), types.KeyboardButton(text="⚡ Elektr")],
    ], resize_keyboard=True)
    await message.answer("⛽ <b>Yoqilg'i turi</b>ni tanlang:", reply_markup=kb, parse_mode="HTML")


@train_router.message(VehicleStates.fuel)
async def veh_fuel(message: types.Message, state: FSMContext):
    fuel_map = {"⛽ Dizel": "dizel", "⛽ Benzin": "benzin", "⛽ Gaz": "gaz", "⚡ Elektr": "elektr"}
    fuel = fuel_map.get((message.text or "").strip(), (message.text or "").strip().lower())
    data = await state.get_data()
    with get_db_session() as db:
        try:
            v = crud_v5.create_vehicle(db, {
                "number": data.get("veh_number"),
                "brand": data.get("veh_brand") or None,
                "capacity": data.get("veh_capacity", 0),
                "fuel_type": fuel,
            })
            ok = True
            err = None
        except Exception as e:
            ok = False
            err = str(e)
    await state.clear()
    await message.answer("✅ Transport qo'shildi!", reply_markup=get_main_menu(message.from_user.id))
    if ok:
        await message.answer(
            f"🚗 <b>{v.number}</b> — {v.brand or '-'}\n"
            f"⚖️ {v.capacity:,.0f} kg | ⛽ {v.fuel_type}\n\n"
            f"<i>TZ ERD: vehicles jadvaliga qo'shildi.</i>",
            parse_mode="HTML",
        )
    else:
        await message.answer(f"❌ Xatolik: {err}")


# ==================== 📅 SMENA KALENDARI (TZ E-bo'lim) ====================

@train_router.message(Command("smena_kalendari"))
@train_router.message(F.text == "📅 Smena kalendari")
async def schedule_menu(message: types.Message):
    if not await ensure_access(message, "schedule", edit=False):
        return
    with get_db_session() as db:
        data = crud_v5.get_work_schedule(db)
    lines = [f"📅 <b>Xodimlar smenasi — {data['month']}</b>\n"]
    for emp in data["employees"]:
        status_icon = "🟢" if emp["status"] == "faol" else "🟡"
        lines.append(
            f"{status_icon} <b>{emp['full_name']}</b> ({emp['role']})\n"
            f"   🗓 {emp['work_days']} kun | ⏱ {emp['total_hours']} soat | "
            f"🔁 qo'shimcha {emp['overtime_hours']} soat"
        )
    if not data["employees"]:
        lines.append("Xodimlar ro'yxati bo'sh.")
    await message.answer("\n".join(lines), parse_mode="HTML")


# ==================== 🤔 "NIMA BO'LSA?" TAHLILI (TZ E-bo'lim) ====================

@train_router.message(Command("nima_bolsa"))
@train_router.message(F.text == "🤔 Nima bo'lsa?")
async def what_if_menu(message: types.Message):
    if not await ensure_access(message, "analytics", edit=False):
        return
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📉 Narx 5% pasaysa", callback_data="wifi_price_down_5")],
        [types.InlineKeyboardButton(text="📉 Narx 10% pasaysa", callback_data="wifi_price_down_10")],
        [types.InlineKeyboardButton(text="📈 Narx 5% oshsa", callback_data="wifi_price_up_5")],
        [types.InlineKeyboardButton(text="🎁 Chegirma 10% berilsa", callback_data="wifi_discount_10")],
        [types.InlineKeyboardButton(text="❌ Yopish", callback_data="train_close")],
    ])
    await message.answer(
        "🤔 <b>\"Nima bo'lsa?\" tahlili</b>\n\n"
        "Stsenariyni tanlang — tizim o'tgan 90 kunlik sotuvlar asosida "
        "prognoz beradi (konservativ talab elastikligi):",
        reply_markup=kb, parse_mode="HTML",
    )


@train_router.callback_query(F.data.startswith("wifi_"))
async def what_if_run(callback: types.CallbackQuery):
    await callback.answer()
    parts = callback.data.split("_")
    scenario = parts[1]
    percent = float(parts[2])
    with get_db_session() as db:
        result = crud_v5.what_if_analysis(db, scenario=scenario, percent=percent)
    delta_icon = "📈" if result["delta"] >= 0 else "📉"
    await callback.message.answer(
        f"🤔 <b>{result['scenario_label']}</b>\n\n"
        f"📊 O'tgan {result['period_days']} kun:\n"
        f"   • Savdo: <b>{result['base_revenue']:,.0f} so'm</b>\n"
        f"   • Soni: {result['base_quantity']:,.0f} | Buyurtmalar: {result['base_order_count']}\n"
        f"   • O'rtacha chek: {result['avg_check']:,.0f} so'm\n\n"
        f"{delta_icon} Bashorat: <b>{result['projected_revenue']:,.0f} so'm</b>\n"
        f"   ({result['delta']:+,.0f} so'm, {result['delta_percent']:+.1f}%)\n\n"
        f"<i>ℹ️ {result['note']}</i>",
        parse_mode="HTML",
    )


# ==================== ⏳ AMAL MUDDATI ESLATMASI (TZ 3.1/3.2) ====================

@train_router.message(Command("amal_muddati"))
@train_router.message(F.text == "⏳ Amal muddati")
async def expiring_menu(message: types.Message):
    if not await ensure_access(message, "warehouse", edit=False):
        return
    with get_db_session() as db:
        items = crud_v5.get_expiring_materials(db, days=30)
    if not items:
        await message.answer("✅ Amal qilish muddati 30 kun ichida tugaydigan xom ashyo yo'q.")
        return
    lines = ["⏳ <b>Amal qilish muddati yaqinlashgan xom ashyolar</b>\n"]
    for it in items:
        icon = "🔴" if it["status"] == "muddati_o'tgan" else "🟡"
        days_txt = "o'tgan" if it["days_left"] < 0 else f"{it['days_left']} kun qoldi"
        lines.append(
            f"{icon} <b>{it['name']}</b> ({it['batch_number'] or 'partiyasiz'})\n"
            f"   📅 {it['expiry_date'][:10]} — {days_txt} | Qoldiq: {it['current_stock']:,.0f}"
        )
    await message.answer("\n\n".join(lines), parse_mode="HTML")


def register_handlers_training(dp: Dispatcher):
    dp.include_router(train_router)