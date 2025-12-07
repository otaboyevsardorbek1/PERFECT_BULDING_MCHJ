"""
Employees Management - Qurilish Korxonasi Xodimlar Boshqaruvi
"""
from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from datetime import datetime, date, timedelta
import logging
import os

from database.session import get_db_session
from database import crud, models
from keyboards.main_menu import get_main_menu
from keyboards.admin_menu import get_employee_management_menu, get_employee_actions_keyboard
from config import EMPLOYEE_POSITIONS, ADMIN_IDS
from utils.excel_reports import create_employee_excel_report
from utils.charts import create_employee_chart

logger = logging.getLogger(__name__)

# =============== EMPLOYEE STATES ===============
class EmployeeStates(StatesGroup):
    # Add Employee
    waiting_full_name = State()
    waiting_phone_number = State()
    waiting_position = State()
    waiting_department = State()
    waiting_salary = State()
    waiting_hire_date = State()
    waiting_telegram_id = State()
    confirm_add_employee = State()
    
    # Edit Employee
    waiting_employee_select = State()
    waiting_edit_field = State()
    waiting_edit_value = State()
    confirm_edit_employee = State()
    
    # Work Hours
    waiting_employee_for_work = State()
    waiting_work_date = State()
    waiting_start_time = State()
    waiting_end_time = State()
    waiting_overtime = State()
    confirm_work_hours = State()
    
    # Salary Payment
    waiting_employee_for_salary = State()
    waiting_salary_month = State()
    waiting_salary_year = State()
    waiting_bonus = State()
    waiting_deduction = State()
    confirm_salary_payment = State()
    
    # Search Employee
    waiting_search_query = State()

# =============== EMPLOYEE MANAGEMENT MENU ===============
async def employee_management(message: types.Message):
    """Xodimlar boshqaruvi menyusi"""
    
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Sizda bu amalni bajarish huquqi yo'q!")
        return
    
    await message.answer("👥 **Xodimlar Boshqaruvi**", 
                        reply_markup=get_employee_management_menu())

# =============== ADD NEW EMPLOYEE ===============
async def add_employee_start(message: types.Message):
    """Yangi xodim qo'shishni boshlash"""
    
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await message.answer("Yangi xodimning to'liq ismini kiriting:", 
                        reply_markup=ReplyKeyboardRemove())
    await EmployeeStates.waiting_full_name.set()

async def process_full_name(message: types.Message, state: FSMContext):
    """Xodim ismini qabul qilish"""
    
    await state.update_data(full_name=message.text)
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ["📞 Telefon raqam", "⬅️ Orqaga"]
    keyboard.add(*buttons)
    
    await message.answer("Telefon raqamini kiriting (format: +998901234567):", 
                        reply_markup=keyboard)
    await EmployeeStates.waiting_phone_number.set()

async def process_phone_number(message: types.Message, state: FSMContext):
    """Telefon raqamini qabul qilish"""
    
    if not message.text.startswith('+998') or len(message.text) != 13 or not message.text[1:].isdigit():
        await message.answer("❌ Noto'g'ri telefon raqami formati. Qayta kiriting (+998901234567):")
        return
    
    await state.update_data(phone_number=message.text)
    
    # Lavozim tanlash uchun keyboard
    keyboard = InlineKeyboardMarkup(row_width=2)
    positions = list(EMPLOYEE_POSITIONS.items())
    
    for pos_code, pos_name in positions:
        keyboard.insert(InlineKeyboardButton(pos_name, callback_data=f"position_{pos_code}"))
    
    keyboard.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_start"))
    
    await message.answer("Lavozimini tanlang:", reply_markup=keyboard)
    await EmployeeStates.waiting_position.set()

async def process_position(callback_query: types.CallbackQuery, state: FSMContext):
    """Lavozimni qabul qilish"""
    
    if callback_query.data == "back_to_start":
        await callback_query.answer()
        await add_employee_start(callback_query.message)
        return
    
    position_code = callback_query.data.replace("position_", "")
    position_name = EMPLOYEE_POSITIONS.get(position_code, "Noma'lum")
    
    await state.update_data(position=position_name, position_code=position_code)
    await callback_query.answer(f"Tanlangan: {position_name}")
    
    # Bo'lim tanlash
    departments = {
        "production": "Ishlab chiqarish",
        "warehouse": "Ombor",
        "sales": "Sotuv",
        "accounting": "Buxgalteriya",
        "management": "Rahbariyat",
        "logistics": "Logistika",
        "quality": "Sifat nazorati"
    }
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    for dept_code, dept_name in departments.items():
        keyboard.insert(InlineKeyboardButton(dept_name, callback_data=f"dept_{dept_code}"))
    
    keyboard.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_position"))
    
    await callback_query.message.answer("Bo'limini tanlang:", reply_markup=keyboard)
    await EmployeeStates.waiting_department.set()

async def process_department(callback_query: types.CallbackQuery, state: FSMContext):
    """Bo'limni qabul qilish"""
    
    if callback_query.data == "back_to_position":
        await callback_query.answer()
        await process_phone_number(callback_query.message, state)
        return
    
    dept_code = callback_query.data.replace("dept_", "")
    departments = {
        "production": "Ishlab chiqarish",
        "warehouse": "Ombor",
        "sales": "Sotuv",
        "accounting": "Buxgalteriya",
        "management": "Rahbariyat",
        "logistics": "Logistika",
        "quality": "Sifat nazorati"
    }
    dept_name = departments.get(dept_code, "Noma'lum")
    
    await state.update_data(department=dept_name)
    await callback_query.answer(f"Tanlangan: {dept_name}")
    
    await callback_query.message.answer("Oylik maoshini kiriting (so'mda):")
    await EmployeeStates.waiting_salary.set()

async def process_salary(message: types.Message, state: FSMContext):
    """Maoshni qabul qilish"""
    
    try:
        salary = float(message.text)
        if salary <= 0:
            await message.answer("❌ Maosh 0 dan katta bo'lishi kerak. Qayta kiriting:")
            return
        
        await state.update_data(salary=salary)
        
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        buttons = ["Bugun", "⬅️ Orqaga"]
        keyboard.add(*buttons)
        
        await message.answer("Ishga kirgan sanasini kiriting (YYYY-MM-DD formatida yoki 'Bugun'):", 
                            reply_markup=keyboard)
        await EmployeeStates.waiting_hire_date.set()
        
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Faqat raqam kiriting:")

async def process_hire_date(message: types.Message, state: FSMContext):
    """Ishga kirgan sanani qabul qilish"""
    
    if message.text == "Bugun":
        hire_date = datetime.utcnow().date()
    else:
        try:
            hire_date = datetime.strptime(message.text, "%Y-%m-%d").date()
        except ValueError:
            await message.answer("❌ Noto'g'ri sana formati. YYYY-MM-DD formatida kiriting:")
            return
    
    await state.update_data(hire_date=hire_date)
    
    await message.answer("Telegram ID sini kiriting (agar mavjud bo'lsa, yoki '0' kiriting):", 
                        reply_markup=ReplyKeyboardRemove())
    await EmployeeStates.waiting_telegram_id.set()

async def process_telegram_id(message: types.Message, state: FSMContext):
    """Telegram ID ni qabul qilish"""
    
    try:
        telegram_id = int(message.text)
        await state.update_data(telegram_id=telegram_id if telegram_id != 0 else None)
        
        # Barcha ma'lumotlarni ko'rsatish
        data = await state.get_data()
        
        summary = f"""
📋 **YANGI XODIM MA'LUMOTLARI:**

👤 **To'liq ism:** {data['full_name']}
📞 **Telefon:** {data['phone_number']}
📋 **Lavozim:** {data['position']}
🏢 **Bo'lim:** {data['department']}
💰 **Maosh:** {data['salary']:,.0f} so'm
📅 **Ishga kirgan sana:** {data['hire_date']}
🆔 **Telegram ID:** {data.get('telegram_id', 'Mavjud emas')}

Ma'lumotlar to'g'rimi?
"""
        
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("✅ Ha, qo'shish", callback_data="confirm_add_yes"),
            InlineKeyboardButton("❌ Yo'q, qayta kirish", callback_data="confirm_add_no")
        )
        
        await message.answer(summary, reply_markup=keyboard, parse_mode="Markdown")
        await EmployeeStates.confirm_add_employee.set()
        
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Faqat raqam kiriting:")

async def confirm_add_employee(callback_query: types.CallbackQuery, state: FSMContext):
    """Xodim qo'shishni tasdiqlash"""
    
    await callback_query.answer()
    
    if callback_query.data == "confirm_add_yes":
        data = await state.get_data()
        
        with get_db_session() as db:
            # Xodimni yaratish
            employee_data = {
                'full_name': data['full_name'],
                'phone_number': data['phone_number'],
                'position': data['position'],
                'department': data['department'],
                'hire_date': data['hire_date'],
                'salary': data['salary'],
                'telegram_id': data.get('telegram_id'),
                'status': models.EmployeeStatus.ACTIVE,
                'is_admin': False
            }
            
            employee = crud.create_employee(db, employee_data)
            
            # Tizim logiga yozish
            crud.create_system_log(
                db,
                user_id=callback_query.from_user.id,
                user_name=callback_query.from_user.full_name,
                action=f"Yangi xodim qo'shildi: {data['full_name']}",
                module="employees"
            )
        
        await callback_query.message.answer(
            f"✅ **{data['full_name']}** muvaffaqiyatli qo'shildi!\n\n"
            f"👤 ID: {employee.id}\n"
            f"📞 Telefon: {data['phone_number']}\n"
            f"📋 Lavozim: {data['position']}\n"
            f"💰 Maosh: {data['salary']:,.0f} so'm\n\n"
            f"🎉 Tabriklaymiz! Yangi xodim tizimga qo'shildi.",
            parse_mode="Markdown",
            reply_markup=get_employee_management_menu()
        )
    
    else:
        await callback_query.message.answer(
            "❌ Xodim qo'shish bekor qilindi.",
            reply_markup=get_employee_management_menu()
        )
    
    await state.finish()

# =============== VIEW EMPLOYEES ===============
async def view_employees(message: types.Message):
    """Xodimlar ro'yxatini ko'rsatish"""
    
    with get_db_session() as db:
        employees = db.query(models.Employee).order_by(
            models.Employee.department, models.Employee.position
        ).all()
    
    if not employees:
        await message.answer("❌ Hozircha xodimlar mavjud emas.")
        return
    
    # Xodimlarni bo'limlarga ajratish
    departments = {}
    for emp in employees:
        if emp.department not in departments:
            departments[emp.department] = []
        departments[emp.department].append(emp)
    
    employees_text = "👥 **XODIMLAR RO'YXATI**\n\n"
    
    for dept, dept_employees in departments.items():
        employees_text += f"🏢 **{dept}** ({len(dept_employees)} kishi)\n"
        
        for emp in dept_employees:
            status_icon = "🟢" if emp.status == models.EmployeeStatus.ACTIVE else \
                         "🟡" if emp.status == models.EmployeeStatus.ON_LEAVE else \
                         "🔴" if emp.status == models.EmployeeStatus.FIRED else "⚪"
            
            employees_text += (
                f"{status_icon} **{emp.full_name}**\n"
                f"   📋 {emp.position} | 📞 {emp.phone_number}\n"
                f"   💰 {emp.salary:,.0f} so'm | 📅 {emp.hire_date.strftime('%Y-%m-%d')}\n\n"
            )
    
    # Qo'shimcha ma'lumotlar
    total_count = len(employees)
    active_count = len([e for e in employees if e.status == models.EmployeeStatus.ACTIVE])
    
    employees_text += (
        f"📊 **STATISTIKA:**\n"
        f"• Jami xodimlar: {total_count} ta\n"
        f"• Faol xodimlar: {active_count} ta\n"
        f"• Faol emas: {total_count - active_count} ta"
    )
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📊 Statistika", callback_data="emp_stats"),
        InlineKeyboardButton("📋 Excel hisobot", callback_data="emp_excel"),
        InlineKeyboardButton("📈 Grafik", callback_data="emp_chart"),
        InlineKeyboardButton("🔍 Qidirish", callback_data="emp_search")
    )
    
    await message.answer(employees_text, parse_mode="Markdown", reply_markup=keyboard)

# =============== EMPLOYEE DETAILS ===============
async def employee_details(callback_query: types.CallbackQuery, employee_id: int = None):
    """Xodimning batafsil ma'lumotlari"""
    
    await callback_query.answer()
    
    with get_db_session() as db:
        if employee_id:
            employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
        else:
            # Agar employee_id berilmagan bo'lsa, foydalanuvchini o'zi haqida ma'lumot ko'rsatish
            employee = db.query(models.Employee).filter(
                models.Employee.telegram_id == callback_query.from_user.id
            ).first()
        
        if not employee:
            await callback_query.message.answer("❌ Xodim topilmadi.")
            return
        
        # Xodim ma'lumotlari
        status_text = {
            models.EmployeeStatus.ACTIVE: "🟢 Faol",
            models.EmployeeStatus.ON_LEAVE: "🟡 Ta'tilda",
            models.EmployeeStatus.FIRED: "🔴 Ishdan bo'shatilgan",
            models.EmployeeStatus.VACATION: "🟣 Dam olish"
        }.get(employee.status, "⚪ Noma'lum")
        
        details_text = f"""
📋 **XODIM MA'LUMOTLARI**

👤 **To'liq ism:** {employee.full_name}
📞 **Telefon:** {employee.phone_number}
📋 **Lavozim:** {employee.position}
🏢 **Bo'lim:** {employee.department}
📊 **Holat:** {status_text}
💰 **Maosh:** {employee.salary:,.0f} so'm
⏰ **Soatlik stavka:** {employee.hourly_rate:,.0f} so'm
📅 **Ishga kirgan:** {employee.hire_date.strftime('%Y-%m-%d')}
🆔 **Telegram ID:** {employee.telegram_id or 'Mavjud emas'}
🏦 **Bank hisobi:** {employee.bank_account or 'Mavjud emas'}
👑 **Admin:** {'✅ Ha' if employee.is_admin else '❌ Yoq'}

📝 **Qo'shimcha ma'lumotlar:**
{employee.notes or 'Mavjud emas'}
"""
        
        # Oxirgi ish vaqtlari
        work_hours = crud.get_employee_work_hours(
            db, employee.id, 
            start_date=date.today() - timedelta(days=7),
            end_date=date.today()
        )
        
        if work_hours:
            total_hours = sum([wh.hours_worked for wh in work_hours])
            overtime_hours = sum([wh.overtime_hours for wh in work_hours])
            
            details_text += f"\n⏱️ **Oxirgi 7 kunlik ish vaqti:**\n"
            details_text += f"• Jami ish soati: {total_hours:.1f} soat\n"
            details_text += f"• Qo'shimcha ish: {overtime_hours:.1f} soat\n"
        
        # Oxirgi maosh to'lovlari
        salary_payments = crud.get_employee_salary_payments(db, employee.id)
        
        if salary_payments:
            last_payment = salary_payments[0]
            details_text += f"\n💰 **Oxirgi maosh to'lovi:**\n"
            details_text += f"• Oy: {last_payment.month}/{last_payment.year}\n"
            details_text += f"• Miqdor: {last_payment.total_amount:,.0f} so'm\n"
            details_text += f"• Holat: {last_payment.status}\n"
        
        # Admin uchun qo'shimcha tugmalar
        keyboard = InlineKeyboardMarkup(row_width=2)
        
        if callback_query.from_user.id in ADMIN_IDS:
            keyboard.add(
                InlineKeyboardButton("✏️ Tahrirlash", callback_data=f"emp_edit_{employee.id}"),
                InlineKeyboardButton("⏱️ Ish vaqti", callback_data=f"emp_work_{employee.id}"),
                InlineKeyboardButton("💰 Maosh to'lash", callback_data=f"emp_salary_{employee.id}"),
                InlineKeyboardButton("📊 Statistika", callback_data=f"emp_stats_{employee.id}")
            )
        
        keyboard.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="emp_back"))
        
        await callback_query.message.answer(details_text, parse_mode="Markdown", reply_markup=keyboard)

# =============== ADD WORK HOURS ===============
async def add_work_hours_start(callback_query: types.CallbackQuery, state: FSMContext):
    """Ish vaqti kiritishni boshlash"""
    
    employee_id = int(callback_query.data.replace("emp_work_", ""))
    
    with get_db_session() as db:
        employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
        
        if not employee:
            await callback_query.answer("❌ Xodim topilmadi")
            return
        
        await state.update_data(employee_id=employee_id, employee_name=employee.full_name)
    
    await callback_query.answer()
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ["Bugun", "Kecha", "⬅️ Orqaga"]
    keyboard.add(*buttons)
    
    await callback_query.message.answer(
        f"📅 **{employee.full_name}** uchun ish vaqtini kiritish\n\n"
        f"Ish kunini tanlang yoki sanani kiriting (YYYY-MM-DD):",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    
    await EmployeeStates.waiting_work_date.set()

async def process_work_date(message: types.Message, state: FSMContext):
    """Ish kunini qabul qilish"""
    
    if message.text == "Bugun":
        work_date = datetime.utcnow().date()
    elif message.text == "Kecha":
        work_date = (datetime.utcnow() - timedelta(days=1)).date()
    else:
        try:
            work_date = datetime.strptime(message.text, "%Y-%m-%d").date()
        except ValueError:
            await message.answer("❌ Noto'g'ri sana formati. YYYY-MM-DD formatida kiriting yoki 'Bugun'/'Kecha' tanlang:")
            return
    
    await state.update_data(work_date=work_date)
    
    await message.answer(
        f"Ish boshlagan vaqtini kiriting (HH:MM formatida, masalan 09:00):",
        reply_markup=ReplyKeyboardRemove()
    )
    
    await EmployeeStates.waiting_start_time.set()

async def process_start_time(message: types.Message, state: FSMContext):
    """Ish boshlash vaqtini qabul qilish"""
    
    try:
        start_time = datetime.strptime(message.text, "%H:%M").time()
        await state.update_data(start_time=start_time)
        
        await message.answer("Ish tugash vaqtini kiriting (HH:MM formatida, masalan 18:00):")
        await EmployeeStates.waiting_end_time.set()
        
    except ValueError:
        await message.answer("❌ Noto'g'ri vaqt formati. HH:MM formatida kiriting:")

async def process_end_time(message: types.Message, state: FSMContext):
    """Ish tugash vaqtini qabul qilish"""
    
    try:
        end_time = datetime.strptime(message.text, "%H:%M").time()
        
        data = await state.get_data()
        start_time = data['start_time']
        
        # Ish soatlarini hisoblash
        start_datetime = datetime.combine(data['work_date'], start_time)
        end_datetime = datetime.combine(data['work_date'], end_time)
        
        if end_datetime <= start_datetime:
            end_datetime += timedelta(days=1)
        
        hours_worked = (end_datetime - start_datetime).total_seconds() / 3600
        
        # Normal ish soati 8 soat deb hisoblaymiz
        normal_hours = min(hours_worked, 8)
        overtime_hours = max(hours_worked - 8, 0)
        
        await state.update_data(
            end_time=end_time,
            hours_worked=hours_worked,
            normal_hours=normal_hours,
            overtime_hours=overtime_hours
        )
        
        summary = f"""
📋 **ISH VAQTI MA'LUMOTLARI:**

👤 Xodim: {data['employee_name']}
📅 Sana: {data['work_date']}
⏰ Boshlash: {start_time.strftime('%H:%M')}
⏰ Tugash: {end_time.strftime('%H:%M')}
⏱️ Jami ish soati: {hours_worked:.1f} soat
📊 Normal ish: {normal_hours:.1f} soat
🚀 Qo'shimcha ish: {overtime_hours:.1f} soat

Qo'shimcha ish soatini kiriting (agar kerak bo'lsa):
"""
        
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add("0", "1", "2", "3", "4", "5", "⬅️ Orqaga")
        
        await message.answer(summary, reply_markup=keyboard, parse_mode="Markdown")
        await EmployeeStates.waiting_overtime.set()
        
    except ValueError:
        await message.answer("❌ Noto'g'ri vaqt formati. HH:MM formatida kiriting:")

async def process_overtime(message: types.Message, state: FSMContext):
    """Qo'shimcha ish soatini qabul qilish"""
    
    try:
        additional_overtime = float(message.text)
        
        data = await state.get_data()
        total_overtime = data['overtime_hours'] + additional_overtime
        
        await state.update_data(total_overtime=total_overtime)
        
        summary = f"""
✅ **YAKUNIY MA'LUMOTLAR:**

👤 Xodim: {data['employee_name']}
📅 Sana: {data['work_date']}
⏰ Ish vaqti: {data['start_time'].strftime('%H:%M')} - {data['end_time'].strftime('%H:%M')}
⏱️ Jami ish: {data['hours_worked']:.1f} soat
🚀 Qo'shimcha ish: {total_overtime:.1f} soat

Ma'lumotlarni saqlaysizmi?
"""
        
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("✅ Ha, saqlash", callback_data="save_work_hours"),
            InlineKeyboardButton("❌ Yo'q, bekor qilish", callback_data="cancel_work_hours")
        )
        
        await message.answer(summary, reply_markup=keyboard, parse_mode="Markdown")
        await EmployeeStates.confirm_work_hours.set()
        
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Faqat raqam kiriting:")

async def save_work_hours(callback_query: types.CallbackQuery, state: FSMContext):
    """Ish vaqtini saqlash"""
    
    await callback_query.answer()
    
    if callback_query.data == "save_work_hours":
        data = await state.get_data()
        
        with get_db_session() as db:
            # Ish vaqtini yaratish
            work_date = data['work_date']
            start_datetime = datetime.combine(work_date, data['start_time'])
            end_datetime = datetime.combine(work_date, data['end_time'])
            
            if end_datetime <= start_datetime:
                end_datetime += timedelta(days=1)
            
            work_data = {
                'employee_id': data['employee_id'],
                'date': work_date,
                'start_time': start_datetime,
                'end_time': end_datetime,
                'hours_worked': data['hours_worked'],
                'overtime_hours': data['total_overtime'],
                'shift_type': 'day',  # Kunlik smena
                'notes': f"Bot orqali kiritildi. Xodim: {data['employee_name']}"
            }
            
            crud.add_work_hours(db, work_data)
            
            # Tizim logiga yozish
            crud.create_system_log(
                db,
                user_id=callback_query.from_user.id,
                user_name=callback_query.from_user.full_name,
                action=f"Ish vaqti kiritildi: {data['employee_name']} - {work_date}",
                module="employees"
            )
        
        await callback_query.message.answer(
            f"✅ **Ish vaqti muvaffaqiyatli saqlandi!**\n\n"
            f"👤 Xodim: {data['employee_name']}\n"
            f"📅 Sana: {data['work_date']}\n"
            f"⏰ Ish vaqti: {data['start_time'].strftime('%H:%M')} - {data['end_time'].strftime('%H:%M')}\n"
            f"⏱️ Jami ish: {data['hours_worked']:.1f} soat\n"
            f"🚀 Qo'shimcha ish: {data['total_overtime']:.1f} soat\n\n"
            f"📝 Ma'lumotlar tizimga kiritildi.",
            parse_mode="Markdown",
            reply_markup=get_employee_management_menu()
        )
    
    else:
        await callback_query.message.answer(
            "❌ Ish vaqti kiritish bekor qilindi.",
            reply_markup=get_employee_management_menu()
        )
    
    await state.finish()

# =============== SALARY PAYMENT ===============
async def salary_payment_start(callback_query: types.CallbackQuery, state: FSMContext):
    """Maosh to'lashni boshlash"""
    
    employee_id = int(callback_query.data.replace("emp_salary_", ""))
    
    with get_db_session() as db:
        employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
        
        if not employee:
            await callback_query.answer("❌ Xodim topilmadi")
            return
        
        await state.update_data(employee_id=employee_id, employee_name=employee.full_name)
    
    await callback_query.answer()
    
    # Oy tanlash
    current_month = datetime.now().month
    months = {
        1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel",
        5: "May", 6: "Iyun", 7: "Iyul", 8: "Avgust",
        9: "Sentabr", 10: "Oktabr", 11: "Noyabr", 12: "Dekabr"
    }
    
    keyboard = InlineKeyboardMarkup(row_width=3)
    for month_num, month_name in months.items():
        keyboard.insert(InlineKeyboardButton(month_name, callback_data=f"month_{month_num}"))
    
    keyboard.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_employee"))
    
    await callback_query.message.answer(
        f"💰 **{employee.full_name}** uchun maosh to'lash\n\n"
        f"Oyini tanlang:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    
    await EmployeeStates.waiting_salary_month.set()

async def process_salary_month(callback_query: types.CallbackQuery, state: FSMContext):
    """Oy ni qabul qilish"""
    
    if callback_query.data == "back_to_employee":
        await callback_query.answer()
        data = await state.get_data()
        await employee_details(callback_query, data['employee_id'])
        await state.finish()
        return
    
    month = int(callback_query.data.replace("month_", ""))
    await state.update_data(month=month)
    
    await callback_query.answer(f"Tanlangan oy: {month}")
    
    # Yil tanlash
    current_year = datetime.now().year
    
    keyboard = InlineKeyboardMarkup(row_width=3)
    for year in range(current_year - 2, current_year + 1):
        keyboard.insert(InlineKeyboardButton(str(year), callback_data=f"year_{year}"))
    
    keyboard.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_month"))
    
    await callback_query.message.answer("Yilini tanlang:", reply_markup=keyboard)
    await EmployeeStates.waiting_salary_year.set()

async def process_salary_year(callback_query: types.CallbackQuery, state: FSMContext):
    """Yilni qabul qilish"""
    
    if callback_query.data == "back_to_month":
        await callback_query.answer()
        await salary_payment_start(callback_query, state)
        return
    
    year = int(callback_query.data.replace("year_", ""))
    await state.update_data(year=year)
    
    await callback_query.answer(f"Tanlangan yil: {year}")
    
    data = await state.get_data()
    
    with get_db_session() as db:
        employee = db.query(models.Employee).filter(models.Employee.id == data['employee_id']).first()
        
        # Oldingi maosh to'lovlarini tekshirish
        existing_payment = db.query(models.SalaryPayment).filter(
            models.SalaryPayment.employee_id == data['employee_id'],
            models.SalaryPayment.month == data['month'],
            models.SalaryPayment.year == data['year']
        ).first()
        
        if existing_payment:
            await callback_query.message.answer(
                f"⚠️ **Diqqat!**\n\n"
                f"{data['month']}/{data['year']} oyi uchun maosh allaqachon to'langan:\n"
                f"💳 Miqdor: {existing_payment.total_amount:,.0f} so'm\n"
                f"📅 To'lov sanasi: {existing_payment.payment_date.strftime('%Y-%m-%d') if existing_payment.payment_date else 'Noma\'lum'}\n"
                f"📊 Holat: {existing_payment.status}\n\n"
                f"Yana maosh to'lamoqchimisiz?",
                parse_mode="Markdown"
            )
    
    await callback_query.message.answer(
        f"Bonus miqdorini kiriting (so'mda, agar bo'lsa):",
        reply_markup=ReplyKeyboardRemove()
    )
    
    await EmployeeStates.waiting_bonus.set()

async def process_bonus(message: types.Message, state: FSMContext):
    """Bonusni qabul qilish"""
    
    try:
        bonus = float(message.text) if message.text else 0
        await state.update_data(bonus=bonus)
        
        await message.answer("Chegirma miqdorini kiriting (so'mda, agar bo'lsa):")
        await EmployeeStates.waiting_deduction.set()
        
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Faqat raqam kiriting:")

async def process_deduction(message: types.Message, state: FSMContext):
    """Chegirmani qabul qilish"""
    
    try:
        deduction = float(message.text) if message.text else 0
        
        data = await state.get_data()
        
        with get_db_session() as db:
            employee = db.query(models.Employee).filter(models.Employee.id == data['employee_id']).first()
            
            # Asosiy maosh
            base_salary = employee.salary
            
            # Qo'shimcha ish uchun to'lov (agar ma'lumot bo'lsa)
            overtime_pay = 0
            
            # Jami miqdor
            total_amount = base_salary + data['bonus'] + overtime_pay - deduction
            
            await state.update_data(
                deduction=deduction,
                base_salary=base_salary,
                total_amount=total_amount
            )
        
        summary = f"""
💰 **MAOSH TO'LOV MA'LUMOTLARI:**

👤 Xodim: {data['employee_name']}
📅 Oy: {data['month']}/{data['year']}
🏦 Asosiy maosh: {base_salary:,.0f} so'm
🎁 Bonus: {data['bonus']:,.0f} so'm
📉 Chegirma: {deduction:,.0f} so'm
💰 Jami to'lov: {total_amount:,.0f} so'm

Ma'lumotlar to'g'rimi?
"""
        
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("✅ Ha, to'lash", callback_data="confirm_salary_yes"),
            InlineKeyboardButton("❌ Yo'q, bekor qilish", callback_data="confirm_salary_no")
        )
        
        await message.answer(summary, reply_markup=keyboard, parse_mode="Markdown")
        await EmployeeStates.confirm_salary_payment.set()
        
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Faqat raqam kiriting:")

async def confirm_salary_payment(callback_query: types.CallbackQuery, state: FSMContext):
    """Maosh to'lovini tasdiqlash"""
    
    await callback_query.answer()
    
    if callback_query.data == "confirm_salary_yes":
        data = await state.get_data()
        
        with get_db_session() as db:
            # Maosh to'lovini yaratish
            salary_data = {
                'employee_id': data['employee_id'],
                'month': data['month'],
                'year': data['year'],
                'base_salary': data['base_salary'],
                'bonus': data['bonus'],
                'deduction': data['deduction'],
                'total_amount': data['total_amount'],
                'payment_date': datetime.utcnow(),
                'payment_method': 'bank',  # Default
                'status': 'paid'
            }
            
            crud.create_salary_payment(db, salary_data)
            
            # Tizim logiga yozish
            crud.create_system_log(
                db,
                user_id=callback_query.from_user.id,
                user_name=callback_query.from_user.full_name,
                action=f"Maosh to'lovi: {data['employee_name']} - {data['month']}/{data['year']} - {data['total_amount']:,.0f} so'm",
                module="employees"
            )
        
        await callback_query.message.answer(
            f"✅ **Maosh muvaffaqiyatli to'landi!**\n\n"
            f"👤 Xodim: {data['employee_name']}\n"
            f"📅 Oy: {data['month']}/{data['year']}\n"
            f"💰 Jami to'lov: {data['total_amount']:,.0f} so'm\n"
            f"📝 To'lov sanasi: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"🎉 Maosh to'lovi tizimga kiritildi.",
            parse_mode="Markdown",
            reply_markup=get_employee_management_menu()
        )
    
    else:
        await callback_query.message.answer(
            "❌ Maosh to'lash bekor qilindi.",
            reply_markup=get_employee_management_menu()
        )
    
    await state.finish()

# =============== EMPLOYEE STATISTICS ===============
async def employee_statistics(message: types.Message):
    """Xodimlar statistikasi"""
    
    with get_db_session() as db:
        # Umumiy statistikalar
        total_employees = db.query(models.Employee).count()
        active_employees = db.query(models.Employee).filter(
            models.Employee.status == models.EmployeeStatus.ACTIVE
        ).count()
        
        # Lavozimlar bo'yicha taqsimot
        positions = {}
        for emp in db.query(models.Employee).all():
            if emp.position not in positions:
                positions[emp.position] = 0
            positions[emp.position] += 1
        
        # Bo'limlar bo'yicha taqsimot
        departments = {}
        for emp in db.query(models.Employee).all():
            if emp.department not in departments:
                departments[emp.department] = 0
            departments[emp.department] += 1
        
        # O'rtacha maosh
        avg_salary = db.query(func.avg(models.Employee.salary)).scalar() or 0
        
        # Oxirgi 30 kundagi ish vaqtlari
        month_ago = datetime.utcnow() - timedelta(days=30)
        work_hours = db.query(models.WorkHours).filter(
            models.WorkHours.date >= month_ago
        ).all()
        
        total_hours = sum([wh.hours_worked for wh in work_hours])
        avg_daily_hours = total_hours / 30 if work_hours else 0
    
    stats_text = f"""
📊 **XODIMLAR STATISTIKASI**

👥 **Umumiy:**
├ Jami xodimlar: {total_employees} ta
├ Faol xodimlar: {active_employees} ta
└ Faol emas: {total_employees - active_employees} ta

💰 **Maosh:**
└ O'rtacha maosh: {avg_salary:,.0f} so'm

🏢 **Lavozimlar bo'yicha:**
"""
    
    for position, count in list(positions.items())[:5]:  # Faqat 5 tasini ko'rsatish
        percentage = (count / total_employees * 100) if total_employees > 0 else 0
        stats_text += f"├ {position}: {count} ta ({percentage:.1f}%)\n"
    
    stats_text += f"\n⏱️ **Ish vaqti (oxirgi 30 kun):**\n"
    stats_text += f"├ Jami ish soati: {total_hours:.1f} soat\n"
    stats_text += f"└ Kuniga o'rtacha: {avg_daily_hours:.1f} soat\n"
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📈 Grafik", callback_data="emp_stats_chart"),
        InlineKeyboardButton("📋 Excel hisobot", callback_data="emp_stats_excel"),
        InlineKeyboardButton("👥 Eng faol xodimlar", callback_data="emp_top_active"),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="emp_back")
    )
    
    await message.answer(stats_text, parse_mode="Markdown", reply_markup=keyboard)

# =============== CALLBACK HANDLERS ===============
async def employee_callback_handler(callback_query: types.CallbackQuery, state: FSMContext):
    """Employee callback handler"""
    
    data = callback_query.data
    
    if data == "emp_back":
        await callback_query.answer()
        await employee_management(callback_query.message)
        return
    
    elif data.startswith("emp_edit_"):
        employee_id = int(data.replace("emp_edit_", ""))
        await edit_employee_start(callback_query, employee_id, state)
    
    elif data.startswith("emp_work_"):
        await add_work_hours_start(callback_query, state)
    
    elif data.startswith("emp_salary_"):
        await salary_payment_start(callback_query, state)
    
    elif data.startswith("emp_stats_"):
        employee_id = int(data.replace("emp_stats_", ""))
        await employee_statistics_details(callback_query, employee_id)
    
    elif data == "emp_stats":
        await employee_statistics(callback_query.message)
    
    elif data == "emp_excel":
        await generate_employee_excel(callback_query.message)
    
    elif data == "emp_chart":
        await generate_employee_chart(callback_query.message)
    
    elif data == "emp_search":
        await search_employee_start(callback_query.message, state)
    
    elif data == "emp_stats_chart":
        await generate_employee_chart(callback_query.message)
    
    elif data == "emp_stats_excel":
        await generate_employee_excel(callback_query.message)
    
    else:
        await callback_query.answer("⚠️ Bu funksiya hozircha ishlamaydi", show_alert=True)

# =============== YORDAMCHI FUNKSIYALAR ===============
async def generate_employee_excel(message: types.Message):
    """Xodimlar Excel hisoboti"""
    
    with get_db_session() as db:
        employees = db.query(models.Employee).all()
        
        employee_data = []
        for emp in employees:
            employee_data.append({
                'ID': emp.id,
                'Toʻliq ism': emp.full_name,
                'Telefon': emp.phone_number,
                'Lavozim': emp.position,
                'Boʻlim': emp.department,
                'Maosh': emp.salary,
                'Holat': emp.status.value,
                'Ishga kirgan': emp.hire_date.strftime('%Y-%m-%d'),
                'Telegram ID': emp.telegram_id or '',
                'Bank hisobi': emp.bank_account or '',
                'Admin': 'Ha' if emp.is_admin else 'Yoq'
            })
    
    # Excel hisobot yaratish
    from utils.excel_reports import create_excel_report
    import pandas as pd
    from datetime import datetime
    
    df = pd.DataFrame(employee_data)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"xodimlar_hisoboti_{timestamp}.xlsx"
    filepath = f"reports/excel/{filename}"
    
    df.to_excel(filepath, index=False)
    
    await message.answer_document(
        document=types.InputFile(filepath),
        caption=f"📋 Xodimlar hisoboti ({len(employees)} ta xodim)"
    )

async def generate_employee_chart(message: types.Message):
    """Xodimlar grafigi"""
    
    with get_db_session() as db:
        employees = db.query(models.Employee).all()
        
        employees_data = []
        for emp in employees:
            employees_data.append({
                'id': emp.id,
                'full_name': emp.full_name,
                'position': emp.position,
                'department': emp.department,
                'salary': emp.salary,
                'status': emp.status.value,
                'hire_date': emp.hire_date
            })
    
    # Grafik yaratish
    from utils.charts import create_employee_chart
    chart_file = create_employee_chart(employees_data, {})
    
    await message.answer_photo(
        photo=types.InputFile(chart_file),
        caption="📈 Xodimlar statistikasi grafigi"
    )

async def search_employee_start(message: types.Message, state: FSMContext):
    """Xodim qidirishni boshlash"""
    
    await message.answer("Qidiruv so'zini kiriting (ism, familiya, lavozim yoki bo'lim):", 
                        reply_markup=ReplyKeyboardRemove())
    await EmployeeStates.waiting_search_query.set()

async def process_search_query(message: types.Message, state: FSMContext):
    """Qidiruv so'zini qabul qilish"""
    
    search_query = message.text.lower()
    
    with get_db_session() as db:
        employees = db.query(models.Employee).filter(
            or_(
                models.Employee.full_name.ilike(f"%{search_query}%"),
                models.Employee.position.ilike(f"%{search_query}%"),
                models.Employee.department.ilike(f"%{search_query}%"),
                models.Employee.phone_number.ilike(f"%{search_query}%")
            )
        ).all()
    
    if not employees:
        await message.answer(f"❌ '{search_query}' bo'yicha xodim topilmadi.", 
                           reply_markup=get_employee_management_menu())
        await state.finish()
        return
    
    search_results = f"🔍 **QIDIRUV NATIJALARI** ('{search_query}')\n\n"
    
    for idx, emp in enumerate(employees[:10], 1):  # Faqat 10 tasini ko'rsatish
        status_icon = "🟢" if emp.status == models.EmployeeStatus.ACTIVE else "🔴"
        
        search_results += (
            f"{idx}. {status_icon} **{emp.full_name}**\n"
            f"   📋 {emp.position} | 🏢 {emp.department}\n"
            f"   📞 {emp.phone_number} | 💰 {emp.salary:,.0f} so'm\n\n"
        )
    
    if len(employees) > 10:
        search_results += f"... va yana {len(employees) - 10} ta natija\n"
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📋 Batafsil ko'rish", callback_data="view_search_results"),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="emp_back")
    )
    
    await state.update_data(search_results=employees)
    await message.answer(search_results, parse_mode="Markdown", reply_markup=keyboard)
    await state.finish()

# =============== REGISTER HANDLERS ===============
def register_handlers_employees(dp: Dispatcher):
    """Employee handlers ni ro'yxatdan o'tkazish"""
    
    # Employee management menu
    dp.register_message_handler(employee_management, 
                               lambda msg: msg.text == "👥 Xodimlar boshqaruvi", 
                               state="*")
    
    # Add employee
    dp.register_message_handler(add_employee_start, 
                               lambda msg: msg.text == "➕ Yangi xodim", 
                               state="*")
    
    # View employees
    dp.register_message_handler(view_employees, 
                               lambda msg: msg.text == "📋 Xodimlar ro'yxati", 
                               state="*")
    
    # My profile
    dp.register_message_handler(lambda msg: employee_details(msg), 
                               lambda msg: msg.text == "👤 Mening profilim", 
                               state="*")
    
    # Work hours
    dp.register_message_handler(lambda msg: add_work_hours_start(msg, None), 
                               lambda msg: msg.text == "⏱️ Ish vaqti kiritish", 
                               state="*")
    
    # Salary payment
    dp.register_message_handler(lambda msg: salary_payment_start(msg, None), 
                               lambda msg: msg.text == "💰 Maosh to'lash", 
                               state="*")
    
    # Statistics
    dp.register_message_handler(employee_statistics, 
                               lambda msg: msg.text == "📊 Xodimlar statistika", 
                               state="*")
    
    # State handlers
    dp.register_message_handler(process_full_name, state=EmployeeStates.waiting_full_name)
    dp.register_message_handler(process_phone_number, state=EmployeeStates.waiting_phone_number)
    dp.register_message_handler(process_salary, state=EmployeeStates.waiting_salary)
    dp.register_message_handler(process_hire_date, state=EmployeeStates.waiting_hire_date)
    dp.register_message_handler(process_telegram_id, state=EmployeeStates.waiting_telegram_id)
    dp.register_message_handler(process_work_date, state=EmployeeStates.waiting_work_date)
    dp.register_message_handler(process_start_time, state=EmployeeStates.waiting_start_time)
    dp.register_message_handler(process_end_time, state=EmployeeStates.waiting_end_time)
    dp.register_message_handler(process_overtime, state=EmployeeStates.waiting_overtime)
    dp.register_message_handler(process_bonus, state=EmployeeStates.waiting_bonus)
    dp.register_message_handler(process_deduction, state=EmployeeStates.waiting_deduction)
    dp.register_message_handler(process_search_query, state=EmployeeStates.waiting_search_query)
    
    # Callback handlers
    dp.register_callback_query_handler(employee_callback_handler,
                                      lambda c: c.data.startswith('emp_') or 
                                               c.data.startswith('position_') or
                                               c.data.startswith('dept_') or
                                               c.data.startswith('month_') or
                                               c.data.startswith('year_'),
                                      state="*")
    
    dp.register_callback_query_handler(process_position, 
                                      lambda c: c.data.startswith('position_'), 
                                      state=EmployeeStates.waiting_position)
    
    dp.register_callback_query_handler(process_department, 
                                      lambda c: c.data.startswith('dept_'), 
                                      state=EmployeeStates.waiting_department)
    
    dp.register_callback_query_handler(confirm_add_employee, 
                                      lambda c: c.data.startswith('confirm_add_'), 
                                      state=EmployeeStates.confirm_add_employee)
    
    dp.register_callback_query_handler(save_work_hours, 
                                      lambda c: c.data in ['save_work_hours', 'cancel_work_hours'], 
                                      state=EmployeeStates.confirm_work_hours)
    
    dp.register_callback_query_handler(process_salary_month, 
                                      lambda c: c.data.startswith('month_') or c.data == 'back_to_employee', 
                                      state=EmployeeStates.waiting_salary_month)
    
    dp.register_callback_query_handler(process_salary_year, 
                                      lambda c: c.data.startswith('year_') or c.data == 'back_to_month', 
                                      state=EmployeeStates.waiting_salary_year)
    
    dp.register_callback_query_handler(confirm_salary_payment, 
                                      lambda c: c.data.startswith('confirm_salary_'), 
                                      state=EmployeeStates.confirm_salary_payment)