from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InputFile

from database.session import get_db_session
from database import crud
from keyboards.main_menu import get_report_period_keyboard, get_main_menu
from utils.excel_reports import (
    create_warehouse_excel_report,
    create_financial_excel_report,
    create_employee_report
)
from utils.charts import (
    create_stock_chart,
    create_production_chart,
    create_financial_chart,
    create_employee_chart
)
import os
from datetime import datetime, timedelta, date
import logging

logger = logging.getLogger(__name__)

class ReportStates(StatesGroup):
    waiting_report_type = State()
    waiting_period = State()

async def reports_menu(message: types.Message):
    """Hisobotlar menyusi"""
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        "📦 Ombor hisoboti",
        "🏭 Ishlab chiqarish hisoboti",
        "💰 Moliya hisoboti",
        "👥 Xodimlar hisoboti",
        "📈 Umumiy statistika",
        "⬅️ Orqaga"
    ]
    keyboard.add(*buttons)
    
    await message.answer("Hisobot turini tanlang:", reply_markup=keyboard)

async def handle_report_selection(message: types.Message, state: FSMContext):
    """Hisobot turini tanlash"""
    
    report_map = {
        "📦 Ombor hisoboti": "warehouse",
        "🏭 Ishlab chiqarish hisoboti": "production",
        "💰 Moliya hisoboti": "financial",
        "👥 Xodimlar hisoboti": "employee",
        "📈 Umumiy statistika": "overall"
    }
    
    report_type = report_map.get(message.text)
    
    if report_type:
        await state.update_data(report_type=report_type)
        await message.answer("Hisobot davrini tanlang:", reply_markup=get_report_period_keyboard())
        await ReportStates.waiting_period.set()
    elif message.text == "⬅️ Orqaga":
        await message.answer("Asosiy menyu:", reply_markup=get_main_menu())
        await state.finish()
    else:
        await message.answer("Noto'g'ri tanlov. Iltimos, tugmalardan foydalaning.")

async def handle_period_selection(callback_query: types.CallbackQuery, state: FSMContext):
    """Hisobot davrini tanlash"""
    
    await callback_query.answer()
    
    if callback_query.data == "back_to_main":
        await callback_query.message.answer("Asosiy menyu:", reply_markup=get_main_menu())
        await state.finish()
        return
    
    period = callback_query.data.replace("report_", "")
    
    data = await state.get_data()
    report_type = data.get('report_type')
    
    await callback_query.message.answer(f"⏳ Hisobot tayyorlanmoqda...")
    
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
            
            # Hisobotni yaratish
            if report_type == "warehouse":
                await generate_warehouse_report(callback_query.message, db, period_text)
            elif report_type == "production":
                await generate_production_report(callback_query.message, db, start_date, end_date, period_text)
            elif report_type == "financial":
                await generate_financial_report(callback_query.message, db, start_date, end_date, period_text)
            elif report_type == "employee":
                await generate_employee_report(callback_query.message, db, start_date, end_date, period_text)
            elif report_type == "overall":
                await generate_overall_report(callback_query.message, db, start_date, end_date, period_text)
    
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        await callback_query.message.answer(f"❌ Xatolik yuz berdi: {str(e)}")
    
    await state.finish()
    await callback_query.message.answer("Hisobotlar menyusiga qaytish uchun '📈 Hisobotlar' tugmasini bosing.")

async def generate_warehouse_report(message: types.Message, db, period_text: str):
    """Ombor hisobotini yaratish"""
    
    # Xom ashyo ma'lumotlarini olish
    raw_materials = db.query(crud.models.RawMaterial).all()
    raw_materials_data = []
    
    for rm in raw_materials:
        raw_materials_data.append({
            'name': rm.name,
            'unit': rm.unit,
            'current_stock': rm.current_stock,
            'min_stock': rm.min_stock,
            'price_per_unit': rm.price_per_unit,
            'status': '✅ Yetarli' if rm.current_stock > rm.min_stock else '⚠️ Yetarli emas'
        })
    
    # Mahsulot ma'lumotlarini olish
    products = db.query(crud.models.Product).filter(crud.models.Product.is_active == True).all()
    products_data = []
    
    for product in products:
        # Ishlab chiqarilgan va sotilgan miqdorni hisoblash
        produced = db.query(func.sum(crud.models.WarehouseTransaction.quantity)).filter(
            crud.models.WarehouseTransaction.product_id == product.id,
            crud.models.WarehouseTransaction.transaction_type == crud.models.TransactionType.PRODUCTION
        ).scalar() or 0
        
        sold = db.query(func.sum(crud.models.WarehouseTransaction.quantity)).filter(
            crud.models.WarehouseTransaction.product_id == product.id,
            crud.models.WarehouseTransaction.transaction_type == crud.models.TransactionType.SALE
        ).scalar() or 0
        
        products_data.append({
            'name': product.name,
            'unit': product.unit,
            'selling_price': product.selling_price,
            'production_cost': product.production_cost,
            'current_stock': produced - sold,
            'profit_margin': ((product.selling_price - product.production_cost) / product.production_cost * 100) if product.production_cost > 0 else 0
        })
    
    # 1. Excel hisobot yaratish
    excel_file = create_warehouse_excel_report(raw_materials_data, products_data)
    
    # 2. Grafik yaratish
    chart_file = create_stock_chart(raw_materials_data)
    
    # 3. Xabarni yuborish
    report_text = f"""
📊 **OMBOR HISOBOTI** ({period_text.upper()})
    
📦 **Xom ashyolar:**
• Jami tur: {len(raw_materials_data)} ta
• Yetarli bo'lmaganlar: {len([rm for rm in raw_materials_data if rm['current_stock'] <= rm['min_stock']])} ta
• Umumiy qiymat: {sum(rm['current_stock'] * rm['price_per_unit'] for rm in raw_materials_data):,.0f} so'm

🏭 **Tayyor mahsulotlar:**
• Jami tur: {len(products_data)} ta
• O'rtacha foyda marjasi: {sum(p['profit_margin'] for p in products_data)/len(products_data) if products_data else 0:.1f}%
"""
    
    await message.answer(report_text, parse_mode="Markdown")
    
    # Fayllarni yuborish
    with open(excel_file, 'rb') as excel:
        await message.answer_document(
            document=InputFile(excel, filename=f"ombor_hisoboti_{period_text}.xlsx"),
            caption="📋 Excel hisobot"
        )
    
    with open(chart_file, 'rb') as chart:
        await message.answer_photo(
            photo=InputFile(chart, filename=f"ombor_grafigi_{period_text}.png"),
            caption="📈 Ombor grafigi"
        )

async def generate_production_report(message: types.Message, db, start_date: date, end_date: date, period_text: str):
    """Ishlab chiqarish hisobotini yaratish"""
    
    # Ishlab chiqarish buyurtmalarini olish
    orders = db.query(crud.models.ProductionOrder).filter(
        crud.models.ProductionOrder.created_at >= start_date,
        crud.models.ProductionOrder.created_at <= end_date
    ).all()
    
    if not orders:
        await message.answer(f"❌ Tanlangan davrda ishlab chiqarish buyurtmalari topilmadi.")
        return
    
    # Statistikani hisoblash
    total_orders = len(orders)
    completed_orders = len([o for o in orders if o.status == crud.models.OrderStatus.COMPLETED])
    total_quantity = sum([o.quantity for o in orders])
    total_cost = sum([o.total_cost or 0 for o in orders])
    total_revenue = sum([o.total_revenue or 0 for o in orders])
    total_profit = total_revenue - total_cost
    
    # Ma'lumotlarni tayyorlash
    production_data = []
    for order in orders:
        production_data.append({
            'order_number': order.order_number,
            'product_name': order.product.name,
            'quantity': order.quantity,
            'status': order.status.value,
            'total_cost': order.total_cost or 0,
            'total_revenue': order.total_revenue or 0,
            'profit': (order.total_revenue or 0) - (order.total_cost or 0),
            'profit_margin': ((order.total_revenue or 0) - (order.total_cost or 0)) / (order.total_cost or 1) * 100 if order.total_cost else 0,
            'date': order.created_at.date()
        })
    
    # 1. Excel hisobot yaratish
    excel_file = create_excel_report(production_data, 'production', 
                                    f'Ishlab chiqarish hisoboti - {period_text}')
    
    # 2. Grafik yaratish
    chart_file = create_production_chart(production_data)
    
    # 3. Xabarni yuborish
    report_text = f"""
🏭 **ISHLAB CHIQARISH HISOBOTI** ({period_text.upper()})
    
📋 **Umumiy ko'rsatkichlar:**
• Jami buyurtmalar: {total_orders} ta
• Bajarilgan buyurtmalar: {completed_orders} ta
• Bajarilish darajasi: {completed_orders/total_orders*100:.1f}%
• Jami miqdor: {total_quantity} birlik

💰 **Moliya ko'rsatkichlari:**
• Jami xarajat: {total_cost:,.0f} so'm
• Jami daromad: {total_revenue:,.0f} so'm
• Jami foyda: {total_profit:,.0f} so'm
• O'rtacha foyda marjasi: {total_profit/total_cost*100 if total_cost > 0 else 0:.1f}%
"""
    
    await message.answer(report_text, parse_mode="Markdown")
    
    # Fayllarni yuborish
    with open(excel_file, 'rb') as excel:
        await message.answer_document(
            document=InputFile(excel, filename=f"ishlab_chiqarish_{period_text}.xlsx"),
            caption="📋 Excel hisobot"
        )
    
    with open(chart_file, 'rb') as chart:
        await message.answer_photo(
            photo=InputFile(chart, filename=f"ishlab_chiqarish_{period_text}.png"),
            caption="📈 Ishlab chiqarish grafigi"
        )

async def generate_financial_report(message: types.Message, db, start_date: date, end_date: date, period_text: str):
    """Moliya hisobotini yaratish"""
    
    # Statistikani hisoblash
    financial_stats = crud.get_financial_statistics(db, start_date, end_date)
    
    # Qo'shimcha ma'lumotlar
    financial_stats.update({
        'other_income': 0,
        'utility_costs': 0,
        'rent_costs': 0,
        'other_expenses': 0
    })
    
    # 1. Excel hisobot yaratish
    excel_file = create_financial_excel_report(financial_stats, period_text)
    
    # 2. Grafik yaratish
    chart_file = create_financial_chart(financial_stats, period_text)
    
    # 3. Xabarni yuborish
    report_text = f"""
💰 **MOLIYA HISOBOTI** ({period_text.upper()})
    
📈 **Daromadlar:**
• Sotuvdan daromad: {financial_stats['total_sales_amount']:,.0f} so'm
• Boshqa daromadlar: {financial_stats.get('other_income', 0):,.0f} so'm
• Jami daromad: {financial_stats['total_sales_amount'] + financial_stats.get('other_income', 0):,.0f} so'm

💸 **Xarajatlar:**
• Ishlab chiqarish: {financial_stats['production_costs']:,.0f} so'm
• Maosh to'lovlari: {financial_stats['salary_costs']:,.0f} so'm
• Jami xarajat: {financial_stats['total_costs']:,.0f} so'm

💎 **Natijalar:**
• Sof foyda: {financial_stats['net_profit']:,.0f} so'm
• Foyda marjasi: {financial_stats['profit_margin']:.1f}%
"""
    
    await message.answer(report_text, parse_mode="Markdown")
    
    # Fayllarni yuborish
    with open(excel_file, 'rb') as excel:
        await message.answer_document(
            document=InputFile(excel, filename=f"moliya_{period_text}.xlsx"),
            caption="📋 Excel hisobot"
        )
    
    with open(chart_file, 'rb') as chart:
        await message.answer_photo(
            photo=InputFile(chart, filename=f"moliya_{period_text}.png"),
            caption="📈 Moliya grafigi"
        )

async def generate_employee_report(message: types.Message, db, start_date: date, end_date: date, period_text: str):
    """Xodimlar hisobotini yaratish"""
    
    # Xodimlarni olish
    employees = db.query(crud.models.Employee).filter(
        crud.models.Employee.status == crud.models.EmployeeStatus.ACTIVE
    ).all()
    
    if not employees:
        await message.answer("❌ Faol xodimlar topilmadi.")
        return
    
    employees_data = []
    work_hours_data = {}
    salary_data = {}
    
    for emp in employees:
        # Xodim ma'lumotlari
        emp_data = {
            'id': emp.id,
            'full_name': emp.full_name,
            'position': emp.position,
            'department': emp.department,
            'phone_number': emp.phone_number,
            'hire_date': emp.hire_date,
            'salary': emp.salary,
            'status': emp.status.value
        }
        employees_data.append(emp_data)
        
        # Ish vaqtlari
        work_hours = crud.get_employee_work_hours(db, emp.id, start_date, end_date)
        total_hours = sum([wh.hours_worked for wh in work_hours])
        overtime_hours = sum([wh.overtime_hours for wh in work_hours])
        
        # Maosh to'lovlari
        salary_payments = crud.get_employee_salary_payments(db, emp.id)
        total_salary = sum([sp.total_amount for sp in salary_payments])
        
        work_hours_data[emp.id] = {
            'total_hours': total_hours,
            'overtime_hours': overtime_hours
        }
        
        salary_data[emp.id] = {
            'total_salary': total_salary,
            'last_payment': salary_payments[0].payment_date if salary_payments else None
        }
    
    # Umumiy statistikani hisoblash
    total_employees = len(employees)
    avg_salary = sum([emp.salary for emp in employees]) / total_employees if total_employees > 0 else 0
    
    # 1. Excel hisobot yaratish
    excel_file = create_employee_report(employees_data, work_hours_data, salary_data)
    
    # 2. Grafik yaratish
    chart_data = {
        'avg_salary_by_position': {},
        'work_hours_stats': {
            'avg_hours': sum([wh['total_hours'] for wh in work_hours_data.values()]) / len(work_hours_data) if work_hours_data else 0,
            'overtime': sum([wh['overtime_hours'] for wh in work_hours_data.values()])
        }
    }
    
    # Lavozimlar bo'yicha o'rtacha maosh
    positions = {}
    for emp in employees:
        if emp.position not in positions:
            positions[emp.position] = []
        positions[emp.position].append(emp.salary)
    
    for position, salaries in positions.items():
        chart_data['avg_salary_by_position'][position] = sum(salaries) / len(salaries)
    
    chart_file = create_employee_chart(employees_data, chart_data)
    
    # 3. Xabarni yuborish
    report_text = f"""
👥 **XODIMLAR HISOBOTI** ({period_text.upper()})
    
📊 **Umumiy ko'rsatkichlar:**
• Jami xodimlar: {total_employees} kishi
• O'rtacha maosh: {avg_salary:,.0f} so'm
• Jami maosh to'lovlari: {sum([sd['total_salary'] for sd in salary_data.values()]):,.0f} so'm

⏱️ **Ish vaqti statistikasi:**
• O'rtacha ish soati: {chart_data['work_hours_stats']['avg_hours']:.1f} soat
• Jami qo'shimcha ish: {chart_data['work_hours_stats']['overtime']:.1f} soat
"""
    
    await message.answer(report_text, parse_mode="Markdown")
    
    # Fayllarni yuborish
    with open(excel_file, 'rb') as excel:
        await message.answer_document(
            document=InputFile(excel, filename=f"xodimlar_{period_text}.xlsx"),
            caption="📋 Excel hisobot"
        )
    
    with open(chart_file, 'rb') as chart:
        await message.answer_photo(
            photo=InputFile(chart, filename=f"xodimlar_{period_text}.png"),
            caption="📈 Xodimlar grafigi"
        )

async def generate_overall_report(message: types.Message, db, start_date: date, end_date: date, period_text: str):
    """Umumiy statistik hisobot"""
    
    # Barcha statistikani yig'ish
    warehouse_stats = crud.get_warehouse_statistics(db)
    production_stats = crud.get_production_statistics(db, start_date, end_date)
    financial_stats = crud.get_financial_statistics(db, start_date, end_date)
    
    # Xodimlar statistikasi
    total_employees = db.query(crud.models.Employee).filter(
        crud.models.Employee.status == crud.models.EmployeeStatus.ACTIVE
    ).count()
    
    # Excel hisobot yaratish
    overall_data = [
        {"Ko'rsatkich": "Xom ashyo qiymati", "Qiymat": f"{warehouse_stats['total_raw_materials_value']:,.0f} so'm"},
        {"Ko'rsatkich": "Yetarli bo'lmagan materiallar", "Qiymat": f"{warehouse_stats['low_stock_materials_count']} ta"},
        {"Ko'rsatkich": "Ishlab chiqarilgan buyurtmalar", "Qiymat": f"{production_stats['completed_orders']} ta"},
        {"Ko'rsatkich": "Jami sotuv miqdori", "Qiymat": f"{production_stats['total_quantity']} birlik"},
        {"Ko'rsatkich": "Sotuv daromadi", "Qiymat": f"{financial_stats['total_sales_amount']:,.0f} so'm"},
        {"Ko'rsatkich": "Sof foyda", "Qiymat": f"{financial_stats['net_profit']:,.0f} so'm"},
        {"Ko'rsatkich": "Foyda marjasi", "Qiymat": f"{financial_stats['profit_margin']:.1f}%"},
        {"Ko'rsatkich": "Faol xodimlar", "Qiymat": f"{total_employees} kishi"},
        {"Ko'rsatkich": "Maosh xarajatlari", "Qiymat": f"{financial_stats['salary_costs']:,.0f} so'm"},
    ]
    
    from utils.excel_reports import create_excel_report
    excel_file = create_excel_report(overall_data, 'overall_stats', 
                                    f'Umumiy statistika - {period_text}')
    
    # Xabarni yuborish
    report_text = f"""
📊 **UMUMIY STATISTIKA** ({period_text.upper()})
    
🏭 **Ishlab chiqarish:**
• Buyurtmalar: {production_stats['total_orders']} ta
• Bajarilgan: {production_stats['completed_orders']} ta
• Miqdor: {production_stats['total_quantity']} birlik

💰 **Moliya:**
• Sotuv daromadi: {financial_stats['total_sales_amount']:,.0f} so'm
• Sof foyda: {financial_stats['net_profit']:,.0f} so'm
• Foyda marjasi: {financial_stats['profit_margin']:.1f}%

📦 **Ombor:**
• Xom ashyo qiymati: {warehouse_stats['total_raw_materials_value']:,.0f} so'm
• Yetarli bo'lmaganlar: {warehouse_stats['low_stock_materials_count']} ta

👥 **Xodimlar:**
• Faol xodimlar: {total_employees} kishi
• Maosh xarajatlari: {financial_stats['salary_costs']:,.0f} so'm
"""
    
    await message.answer(report_text, parse_mode="Markdown")
    
    # Excel faylni yuborish
    with open(excel_file, 'rb') as excel:
        await message.answer_document(
            document=InputFile(excel, filename=f"umumiy_statistika_{period_text}.xlsx"),
            caption="📋 Umumiy statistika hisoboti"
        )

def register_handlers_reports(dp: Dispatcher):
    """Register reports handlers"""
    dp.register_message_handler(reports_menu, lambda msg: msg.text == "📈 Hisobotlar", state="*")
    dp.register_message_handler(handle_report_selection, 
                               lambda msg: msg.text in ["📦 Ombor hisoboti", "🏭 Ishlab chiqarish hisoboti", 
                                                       "💰 Moliya hisoboti", "👥 Xodimlar hisoboti", 
                                                       "📈 Umumiy statistika", "⬅️ Orqaga"],
                               state="*")
    dp.register_callback_query_handler(handle_period_selection,
                                      lambda c: c.data.startswith('report_') or c.data == 'back_to_main',
                                      state=ReportStates.waiting_period)