"""
Rollar (Ruxsatlar matritsasi) moduli — v3
Faqat direktor roliga ruxsat. Xodimlar rolini o'zgartirish.
"""
from aiogram import types, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMIN_IDS, ROLES
from database.session import get_db_session
from database import models, crud
from utils.access import role_label


class RoleStates(StatesGroup):
    waiting_employee = State()
    waiting_role = State()


async def roles_menu(message: types.Message):
    """Rollar matritsasi menyusi (faqat direktor)"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Faqat direktor (asosiy admin) rollarni boshqara oladi!")
        return

    with get_db_session() as db:
        employees = db.query(models.Employee).order_by(models.Employee.full_name).all()
        if not employees:
            await message.answer("📭 Xodimlar yo'q. Avval xodim qo'shing.")
            return
        rows = [[InlineKeyboardButton(
            text=f"{e.full_name} — {role_label(db, e.telegram_id) if e.telegram_id else 'rol: ishchi'}",
            callback_data=f"role_emp_{e.id}"
        )] for e in employees]
        rows.append([InlineKeyboardButton(text="📖 Rol matritsasi", callback_data="role_matrix")])
        await message.answer(
            "🔐 <b>ROLLAR BOSHQARUVI</b>\n\n"
            "Xodimni tanlang yoki rol matritsasini ko'ring:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML"
        )
    await RoleStates.waiting_employee.set()


async def role_pick_employee(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    emp_id = int(callback.data.replace("role_emp_", ""))
    await state.update_data(emp_id=emp_id)

    with get_db_session() as db:
        employee = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
        if not employee:
            await callback.message.answer("❌ Xodim topilmadi.")
            await state.clear()
            return
        rows = [[InlineKeyboardButton(
            text=ROLES[role]["label"],
            callback_data=f"role_set_{role}"
        )] for role in ROLES.keys()]
        current_role = role_label(db, employee.telegram_id) if employee.telegram_id else "—"
        await callback.message.answer(
            f"👤 <b>{employee.full_name}</b>\n"
            f"Joriy rol: {current_role}\n\n"
            f"Yangi rolini tanlang:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML"
        )
    await RoleStates.waiting_role.set()


async def role_set(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    role = callback.data.replace("role_set_", "")
    data = await state.get_data()

    with get_db_session() as db:
        employee = db.query(models.Employee).filter(models.Employee.id == data["emp_id"]).first()
        if not employee:
            await callback.message.answer("❌ Xodim topilmadi.")
            await state.clear()
            return
        employee.role = role
        db.commit()
        crud.create_system_log(db, user_id=callback.from_user.id,
                               user_name=callback.from_user.full_name,
                               action=f"Rol o'zgartirildi: {employee.full_name} -> {ROLES[role]['label']}",
                               module="roles")
        cost_text = ("👁️ Tannarxni ko‘ra oladi" if ROLES[role]['see_cost']
                     else "🚫 Tannarxni ko‘ra olmaydi")
        text = (
            f"✅ <b>Rol yangilandi!</b>\n\n"
            f"👤 Xodim: {employee.full_name}\n"
            f"🔐 Yangi rol: {ROLES[role]['label']}\n\n"
            f"📋 Ko'ra oladi: {', '.join(ROLES[role]['can_view'])}\n"
            f"✏️ O'zgartira oladi: {', '.join(ROLES[role]['can_edit']) or 'hech narsa'}\n"
            f"💰 Chegirma limiti: {ROLES[role]['discount_limit']}%\n"
            f"{cost_text}"
        )
        await callback.message.answer(text, parse_mode="HTML")
    await state.clear()


async def role_matrix(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    text = "📖 <b>ROL MATRITSASI</b>\n\n"
    for role, info in ROLES.items():
        cost_line = ("✅ Tannarxni ko‘radi" if info['see_cost']
                     else "🚫 Tannarxni ko‘rmaydi")
        text += (
            f"{info['label']}\n"
            f"   📋 Ko'rish: {', '.join(info['can_view'])}\n"
            f"   ✏️ Tahrir: {', '.join(info['can_edit']) or '—'}\n"
            f"   💰 Chegirma limiti: {info['discount_limit']}%\n"
            f"   {cost_line}\n\n"
        )
    await callback.message.answer(text[:4000], parse_mode="HTML")
    await state.clear()


def register_handlers_roles(dp: Dispatcher):
    dp.message.register(roles_menu, F.text == "🔐 Rollar boshqaruvi")
    dp.message.register(roles_menu, Command("rollar"))
    dp.callback_query.register(role_pick_employee, F.data.startswith("role_emp_"),
                               RoleStates.waiting_employee)
    dp.callback_query.register(role_set, F.data.startswith("role_set_"), RoleStates.waiting_role)
    dp.callback_query.register(role_matrix, F.data == "role_matrix")
