"""
Yetkazib beruvchilar moduli — v3
Ta'minot: yetkazib beruvchi ro'yxati, sifat nazorati bilan qabul qilish akti,
avtomatik qayta buyurtma tavsiyalari
"""
from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from sqlalchemy.exc import IntegrityError

from database.session import get_db_session
from database import models, crud
from keyboards.main_menu import get_supplier_menu
from utils.access import ensure_access
from utils.helpers import validate_phone, normalize_phone, parse_float_input


class SupplierStates(StatesGroup):
    waiting_name = State()
    waiting_phone = State()
    waiting_contact = State()
    waiting_address = State()
    waiting_receipt_supplier = State()
    waiting_receipt_material = State()
    waiting_receipt_ordered = State()
    waiting_receipt_received = State()
    waiting_receipt_quality = State()
    waiting_receipt_price = State()


# =============== ENTRY ===============
async def supplier_menu(message: types.Message):
    if not await ensure_access(message, "supplier"):
        return
    await message.answer(
        "🚚 <b>YETKAZIB BERUVCHILAR</b>\n\n"
        "Ta'minot boshqaruvi: yetkazib beruvchilar, qabul qilish aktlari (sifat nazorati), "
        "avtomatik buyurtma tavsiyalari.",
        reply_markup=get_supplier_menu(), parse_mode="HTML"
    )


# =============== YANGI YETKAZIB BERUVCHI ===============
async def add_supplier_start(message: types.Message, state: FSMContext):
    if not await ensure_access(message, "supplier", edit=True):
        return
    await state.clear()
    await message.answer("🚚 Yetkazib beruvchi nomini kiriting (masalan: O'zbekiston Sement):")
    await SupplierStates.waiting_name.set()


async def process_supplier_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("❌ Yetkazib beruvchi nomi bo'sh bo'lishi mumkin emas:")
        return
    # Dublikatni erta tekshirish — keyingi 3 ta savolni so'ramaydi
    with get_db_session() as db:
        exists = db.query(models.Supplier).filter(models.Supplier.name == name).first()
    if exists:
        await message.answer("❌ Bu nomdagi yetkazib beruvchi allaqachon mavjud!\n📋 Yetkazib beruvchilar ro'yxatidan tekshiring.")
        await state.clear()
        return
    await state.update_data(name=name)
    await message.answer("📞 Telefon raqamini kiriting (0 bo'lmasa):")
    await SupplierStates.waiting_phone.set()


async def process_supplier_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    if phone != "0" and not validate_phone(phone):
        await message.answer("❌ Noto'g'ri format. Masalan: +998901234567")
        return
    await state.update_data(phone=None if phone == "0" else normalize_phone(phone))
    await message.answer("👤 Aloqa shaxsi (0 bo'lmasa):")
    await SupplierStates.waiting_contact.set()


async def process_supplier_contact(message: types.Message, state: FSMContext):
    contact = message.text.strip()
    await state.update_data(contact_person=None if contact == "0" else contact)
    await message.answer("📍 Manzil (0 bo'lmasa):")
    await SupplierStates.waiting_address.set()


async def process_supplier_address(message: types.Message, state: FSMContext):
    address = message.text.strip()
    data = await state.get_data()
    with get_db_session() as db:
        existing = db.query(models.Supplier).filter(models.Supplier.name == data["name"]).first()
        if existing:
            await message.answer("❌ Bu nomdagi yetkazib beruvchi allaqachon mavjud!")
            await state.clear()
            return
        try:
            supplier = crud.create_supplier(db, {
                "name": data["name"],
                "phone": data.get("phone"),
                "contact_person": data.get("contact_person"),
                "address": None if address == "0" else address,
            })
        except IntegrityError:
            db.rollback()
            await message.answer("❌ Bu nomdagi yetkazib beruvchi allaqachon mavjud!",
                                 reply_markup=get_supplier_menu())
            await state.clear()
            return
        crud.create_system_log(db, user_id=message.from_user.id,
                               user_name=message.from_user.full_name,
                               action=f"Yangi yetkazib beruvchi: {supplier.name}",
                               module="supplier")
    await state.clear()
    await message.answer(
        f"✅ <b>Yetkazib beruvchi qo'shildi!</b>\n\n"
        f"🚚 {supplier.name}\n"
        f"📞 {supplier.phone or '-'}\n"
        f"👤 {supplier.contact_person or '-'}\n"
        f"📍 {supplier.address or '-'}",
        reply_markup=get_supplier_menu(), parse_mode="HTML"
    )


# =============== YETKAZIB BERUVCHILAR RO'YXATI ===============
async def list_suppliers(message: types.Message):
    with get_db_session() as db:
        suppliers = crud.list_suppliers(db)
        if not suppliers:
            await message.answer("📭 Hozircha yetkazib beruvchilar yo'q.",
                                 reply_markup=get_supplier_menu())
            return
        text = f"🚚 <b>YETKAZIB BERUVCHILAR ({len(suppliers)})</b>\n\n"
        for i, s in enumerate(suppliers, 1):
            star = "⭐" * max(1, round(s.rating or 5))
            text += (
                f"{i}. <b>{s.name}</b> {star}\n"
                f"   📞 {s.phone or '-'} | 👤 {s.contact_person or '-'}\n"
                f"   📦 O'z vaqtida: {s.on_time_count} | Kechikkan: {s.late_count}\n"
                f"   💰 Qarz: {s.total_debt:,.0f} so'm\n\n"
            )
        await message.answer(text[:4000], parse_mode="HTML")


# =============== QABUL QILISH AKTI ===============
async def receipt_start(message: types.Message, state: FSMContext):
    if not await ensure_access(message, "supplier", edit=True):
        return
    await state.clear()
    with get_db_session() as db:
        suppliers = crud.list_suppliers(db)
        if not suppliers:
            await message.answer("❌ Avval yetkazib beruvchi qo'shing!", reply_markup=get_supplier_menu())
            return
        rows = [[types.InlineKeyboardButton(text=s.name, callback_data=f"receipt_sup_{s.id}")]
                for s in suppliers]
        await message.answer("📦 <b>QABUL QILISH AKTI</b>\n\nYetkazib beruvchini tanlang:",
                             reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows),
                             parse_mode="HTML")
        await SupplierStates.waiting_receipt_supplier.set()


async def receipt_pick_supplier(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    sid = int(callback.data.replace("receipt_sup_", ""))
    await state.update_data(supplier_id=sid)
    with get_db_session() as db:
        materials = db.query(models.RawMaterial).filter(
            models.RawMaterial.supplier_id == sid
        ).all()
        if not materials:
            # Barcha xom ashyolarni taklif qilish
            materials = db.query(models.RawMaterial).order_by(models.RawMaterial.name).all()
        rows = [[types.InlineKeyboardButton(
            text=f"{m.name} (qoldiq: {m.current_stock:,.0f} {m.unit})",
            callback_data=f"receipt_mat_{m.id}"
        )] for m in materials]
        if not rows:
            await callback.message.answer(
                "❌ Xom ashyolar yo'q. Avval 📦 Ombor bo'limida xom ashyo qo'shing.",
                reply_markup=get_supplier_menu()
            )
            await state.clear()
            return
        await callback.message.answer("Qaysi xom ashyo kelmoqda?",
                                      reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows))
    await SupplierStates.waiting_receipt_material.set()


async def receipt_pick_material(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    mid = int(callback.data.replace("receipt_mat_", ""))
    await state.update_data(material_id=mid)
    await callback.message.answer("🔢 Buyurtma qilingan miqdorni kiriting:")
    await SupplierStates.waiting_receipt_ordered.set()


async def receipt_ordered(message: types.Message, state: FSMContext):
    qty = parse_float_input(message.text)
    if qty is None:
        await message.answer("❌ Faqat raqam kiriting:")
        return
    if qty <= 0:
        await message.answer("❌ Miqdor 0 dan katta bo'lishi kerak:")
        return
    await state.update_data(ordered=qty)
    await message.answer("⚖️ Tarozida/tekshiruvda chiqqan miqdorni kiriting:")
    await SupplierStates.waiting_receipt_received.set()


async def receipt_received(message: types.Message, state: FSMContext):
    qty = parse_float_input(message.text)
    if qty is None:
        await message.answer("❌ Faqat raqam kiriting:")
        return
    if qty < 0:
        await message.answer("❌ Qabul qilingan miqdor manfiy bo'lishi mumkin emas:")
        return
    await state.update_data(received=qty)
    rows = [
        [types.InlineKeyboardButton(text="✅ Sifatli — qabul", callback_data="q_accept")],
        [types.InlineKeyboardButton(text="⚠️ Qisman — qisman qabul", callback_data="q_partial")],
        [types.InlineKeyboardButton(text="❌ Sifatsiz — rad etish", callback_data="q_reject")],
    ]
    await message.answer("🔍 Sifat nazorati natijasi:",
                         reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows))
    await SupplierStates.waiting_receipt_quality.set()


async def receipt_quality(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    qmap = {"q_accept": "qabul_qilingan", "q_partial": "qisman", "q_reject": "rad_etilgan"}
    await state.update_data(quality=qmap[callback.data])
    await callback.message.answer("💰 1 birlik narxini kiriting (so'm):")
    await SupplierStates.waiting_receipt_price.set()


async def receipt_price(message: types.Message, state: FSMContext):
    price = parse_float_input(message.text)
    if price is None:
        await message.answer("❌ Faqat raqam kiriting:")
        return
    if price < 0:
        await message.answer("❌ Narx manfiy bo'lishi mumkin emas:")
        return
    data = await state.get_data()
    with get_db_session() as db:
        try:
            delivery = crud.create_supplier_delivery(
                db,
                supplier_id=data["supplier_id"],
                raw_material_id=data["material_id"],
                quantity_ordered=data["ordered"],
                quantity_received=data["received"],
                quality_status=data["quality"],
                price_per_unit=price,
                created_by=message.from_user.full_name,
            )
            material = db.query(models.RawMaterial).filter(
                models.RawMaterial.id == data["material_id"]
            ).first()
            supplier = db.query(models.Supplier).filter(
                models.Supplier.id == data["supplier_id"]
            ).first()
            crud.create_system_log(db, user_id=message.from_user.id,
                                   user_name=message.from_user.full_name,
                                   action=f"Qabul akti: {delivery.act_number}",
                                   module="supplier")
        except ValueError as e:
            await message.answer(f"❌ {e}")
            await state.clear()
            return
    qtext = {"qabul_qilingan": "✅ Qabul", "qisman": "⚠️ Qisman", "rad_etilgan": "❌ Rad etilgan"}
    await state.clear()
    await message.answer(
        f"📦 <b>QABUL QILISH AKTI: {delivery.act_number}</b>\n\n"
        f"🚚 Yetkazib beruvchi: {supplier.name}\n"
        f"🧱 Xom ashyo: {material.name}\n"
        f"📦 Buyurtma: {data['ordered']:,.0f} {material.unit}\n"
        f"⚖️ Qabul qilingan: {delivery.quantity_received:,.0f} {material.unit}\n"
        f"🔍 Sifat: {qtext.get(data['quality'])}\n"
        f"💰 Narx: {price:,.0f} so'm/{material.unit}\n"
        f"⚠️ Kamomad qarzi: {delivery.deficiency_amount:,.0f} so'm\n\n"
        f"Joriy zaxira: {material.current_stock:,.0f} {material.unit}",
        reply_markup=get_supplier_menu(), parse_mode="HTML"
    )


# =============== QAYTA BUYURTMA TAVSIYALARI ===============
async def reorder_suggestions(message: types.Message):
    with get_db_session() as db:
        suggestions = crud.get_supplier_reorder_suggestions(db)
        if not suggestions:
            await message.answer("✅ Barcha xom ashyo zaxirasi yetarli!",
                                 reply_markup=get_supplier_menu())
            return
        text = "🛒 <b>AVTOMATIK QAYTA BUYURTMA TAVSIYALARI</b>\n\n"
        for s in suggestions:
            text += (
                f"🧱 {s['raw_material_name']}\n"
                f"   Qoldiq: {s['current_stock']:,.0f} {s['unit']} (min: {s['min_stock']:,.0f})\n"
                f"   Buyurtma: {s['suggested_order']:,.0f} {s['unit']}\n"
                f"   🚚 {s['supplier_name']}\n\n"
            )
        text += "\n💡 Buyurtma berish uchun: 📦 Qabul qilish akti"
        await message.answer(text[:4000], reply_markup=get_supplier_menu(), parse_mode="HTML")


# =============== REGISTER ===============
def register_handlers_suppliers(dp: Dispatcher):
    dp.message.register(supplier_menu, F.text == "🚚 Yetkazib beruvchilar")
    dp.message.register(add_supplier_start, F.text == "➕ Yangi yetkazib beruvchi")
    dp.message.register(list_suppliers, F.text == "📋 Yetkazib beruvchilar")
    dp.message.register(receipt_start, F.text == "📦 Qabul qilish akti")
    dp.message.register(reorder_suggestions, F.text == "🛒 Qayta buyurtma tavsiyalari")

    dp.message.register(process_supplier_name, SupplierStates.waiting_name)
    dp.message.register(process_supplier_phone, SupplierStates.waiting_phone)
    dp.message.register(process_supplier_contact, SupplierStates.waiting_contact)
    dp.message.register(process_supplier_address, SupplierStates.waiting_address)
    dp.message.register(receipt_ordered, SupplierStates.waiting_receipt_ordered)
    dp.message.register(receipt_received, SupplierStates.waiting_receipt_received)
    dp.message.register(receipt_price, SupplierStates.waiting_receipt_price)

    dp.callback_query.register(receipt_pick_supplier, F.data.startswith("receipt_sup_"),
                               SupplierStates.waiting_receipt_supplier)
    dp.callback_query.register(receipt_pick_material, F.data.startswith("receipt_mat_"),
                               SupplierStates.waiting_receipt_material)
    dp.callback_query.register(receipt_quality, F.data.startswith("q_"),
                               SupplierStates.waiting_receipt_quality)
