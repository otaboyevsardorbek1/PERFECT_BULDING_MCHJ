"""
PDF Hisobotlar Handler - PDF hisobot yaratish va yuborish
"""

from aiogram import types, Dispatcher, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InputFile

from database.session import get_db_session
from database import crud, models
from keyboards.main_menu import get_main_menu
from utils.pdf_reports import pdf_generator
from datetime import datetime, date, timedelta
import logging

logger = logging.getLogger(__name__)


class PDFReportStates(StatesGroup):
    waiting_report_type = State()
    waiting_period = State()


async def pdf_reports_menu(message: types.Message):
    """PDF hisobotlar menyusi"""
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        "📄 Ombor PDF",
        "📄 Moliya PDF",
        "📄 Ishlab chiqarish PDF",
        "📄 Xodimlar PDF",
        "⬅️ Orqaga"
    ]
    keyboard.add(*buttons)
    
    await message.answer(
        "📄 <b>PDF HISOBOTLAR</b>\n\n"
        "Qaysi turdagi hisobotni yaratmoqchisiz?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def handle_pdf_report_selection(message: types.Message, state: FSMContext):
    """PDF hisobot turini tanlash"""
    
    report_map = {
        "📄 Ombor PDF": "warehouse",
        "📄 Moliya PDF": "financial",
        "📄 Ishlab chiqarish PDF": "production",
        "📄 Xodimlar PDF": "employee"
    }
    
    report_type = report_map.get(message.text)
    
    if report_type:
        await state.update_data(report_type=report_type)
        
        # Davr tanlash tugmalari
        keyboard = types.InlineKeyboardMarkup(row_width=3)
        keyboard.add(
            types.InlineKeyboardButton("Kunlik", callback_data="pdf_daily"),
            types.InlineKeyboardButton("Haftalik", callback_data="pdf_weekly"),
            types.InlineKeyboardButton("Oylik", callback_data="pdf_monthly")
        )
        keyboard.add(
            types.InlineKeyboardButton("Choraklik", callback_data="pdf_quarterly"),
            types.InlineKeyboardButton("Yillik", callback_data="pdf_yearly")
        )
        
        await message.answer(
            "📅 Hisobot davrini tanlang:",
            reply_markup=keyboard
        )
        await PDFReportStates.waiting_period.set()
        
    elif message.text == "⬅️ Orqaga":
        await message.answer("Asosiy menyu:", reply_markup=get_main_menu())
        await state.clear()
    else:
        await message.answer("Noto'g'ri tanlov. Tugmalardan foydalaning.")


async def handle_pdf_period_selection(callback_query: types.CallbackQuery, state: FSMContext):
    """PDF hisobot davrini tanlash"""
    await callback_query.answer()
    
    period = callback_query.data.replace("pdf_", "")
    
    data = await state.get_data()
    report_type = data.get('report_type')
    
    await callback_query.message.answer("⏳ PDF hisobot tayyorlanmoqda...")
    
    try:
        with get_db_session() as db:
            # Davrni aniqlash
            end_date = date.today()
            
            if period == "daily":
                start_date = end_date
                period_text = "kunlik"
            elif period == "weekly":
                start_date = end_date - timedelta(days=7)
                period_text = "haftalik"
            elif period == "monthly":
                start_date = end_date.replace(day=1)
                period_text = "oylik"
            elif period == "quarterly":
                quarter = (end_date.month - 1) // 3 + 1
                start_month = (quarter - 1) * 3 + 1
                start_date = end_date.replace(month=start_month, day=1)
                period_text = "choraklik"
            elif period == "yearly":
                start_date = end_date.replace(month=1, day=1)
                period_text = "yillik"
            else:
                start_date = end_date - timedelta(days=30)
                period_text = "30 kunlik"
            
            # PDF yaratish
            if report_type == "warehouse":
                await generate_warehouse_pdf(callback_query.message, db)
            elif report_type == "financial":
                await generate_financial_pdf(callback_query.message, db, start_date, end_date, period_text)
            elif report_type == "production":
                await generate_production_pdf(callback_query.message, db, start_date, end_date)
            elif report_type == "employee":
                await generate_employee_pdf(callback_query.message, db)
    
    except Exception as e:
        logger.error(f"Error generating PDF report: {e}")
        await callback_query.message.answer(f"❌ Xatolik yuz berdi: {str(e)}")
    
    await state.clear()


async def generate_warehouse_pdf(message: types.Message, db):
    """Ombor PDF hisobotini yaratish"""
    
    # Xom ashyo ma'lumotlari
    raw_materials = db.query(models.RawMaterial).all()
    raw_materials_data = []
    
    for rm in raw_materials:
        raw_materials_data.append({
            'name': rm.name,
            'unit': rm.unit,
            'current_stock': rm.current_stock,
            'min_stock': rm.min_stock,
            'price_per_unit': rm.price_per_unit
        })
    
    # Mahsulotlar
    products = db.query(models.Product).filter(
        models.Product.is_active == True
    ).all()
    products_data = []
    
    for prod in products:
        products_data.append({
            'name': prod.name,
            'unit': prod.unit,
            'selling_price': prod.selling_price,
            'production_cost': prod.production_cost
        })
    
    # PDF yaratish
    pdf_file = pdf_generator.generate_warehouse_report(
        raw_materials_data, products_data
    )
    
    # Faylni yuborish
    with open(pdf_file, 'rb') as f:
        await message.answer_document(
            document=InputFile(f, filename="ombor_hisoboti.pdf"),
            caption="📋 Ombor holati PDF hisoboti"
        )


async def generate_financial_pdf(message: types.Message, db, start_date, end_date, period_text):
    """Moliya PDF hisobotini yaratish"""
    
    # Statistikani hisoblash
    financial_stats = crud.get_financial_statistics(db, start_date, end_date)
    financial_stats.update({
        'other_income': 0,
        'utility_costs': 0,
        'rent_costs': 0,
        'other_expenses': 0
    })
    
    # PDF yaratish
    pdf_file = pdf_generator.generate_financial_report(
        financial_stats, period_text
    )
    
    # Faylni yuborish
    with open(pdf_file, 'rb') as f:
        await message.answer_document(
            document=InputFile(f, filename=f"moliya_{period_text}.pdf"),
            caption=f"💰 Moliya hisoboti PDF ({period_text})"
        )


async def generate_production_pdf(message: types.Message, db, start_date, end_date):
    """Ishlab chiqarish PDF hisobotini yaratish"""
    
    # Buyurtmalar
    orders = db.query(models.ProductionOrder).filter(
        models.ProductionOrder.created_at >= start_date,
        models.ProductionOrder.created_at <= end_date
    ).all()
    
    orders_data = []
    for order in orders:
        product = db.query(models.Product).filter(
            models.Product.id == order.product_id
        ).first()
        
        orders_data.append({
            'product_name': product.name if product else 'Noma\'lum',
            'quantity': order.quantity,
            'total_cost': order.total_cost or 0,
            'status': order.status.value if order.status else 'jarayonda'
        })
    
    # Statistika
    stats = crud.get_production_statistics(db, start_date, end_date)
    
    # PDF yaratish
    pdf_file = pdf_generator.generate_production_report(orders_data, stats)
    
    # Faylni yuborish
    with open(pdf_file, 'rb') as f:
        await message.answer_document(
            document=InputFile(f, filename="ishlab_chiqarish_hisoboti.pdf"),
            caption="🏭 Ishlab chiqarish hisoboti PDF"
        )


async def generate_employee_pdf(message: types.Message, db):
    """Xodimlar PDF hisobotini yaratish"""
    
    # Xodimlar
    employees = db.query(models.Employee).filter(
        models.Employee.status == models.EmployeeStatus.ACTIVE
    ).all()
    
    employees_data = []
    for emp in employees:
        employees_data.append({
            'full_name': emp.full_name,
            'position': emp.position,
            'department': emp.department,
            'salary': emp.salary
        })
    
    # Statistika
    total_employees = len(employees)
    avg_salary = sum(emp.salary for emp in employees) / total_employees if total_employees > 0 else 0
    total_salary = sum(emp.salary for emp in employees)
    
    stats = {
        'avg_salary': avg_salary,
        'total_salary': total_salary
    }
    
    # PDF yaratish
    pdf_file = pdf_generator.generate_employee_report(employees_data, stats)
    
    # Faylni yuborish
    with open(pdf_file, 'rb') as f:
        await message.answer_document(
            document=InputFile(f, filename="xodimlar_hisoboti.pdf"),
            caption="👥 Xodimlar hisoboti PDF"
        )


def register_handlers_pdf(dp: Dispatcher):
    """PDF hisobotlar handlerlarini ro'yxatdan o'tkazish"""
    
    dp.message.register(pdf_reports_menu, F.text == "📄 PDF hisobotlar")
    
    dp.message.register(handle_pdf_report_selection,
                        F.text.in_(["📄 Ombor PDF", "📄 Moliya PDF", 
                                   "📄 Ishlab chiqarish PDF", "📄 Xodimlar PDF", 
                                   "⬅️ Orqaga"]))
    
    dp.callback_query.register(handle_pdf_period_selection,
                               F.data.startswith('pdf_'),
                               PDFReportStates.waiting_period)
