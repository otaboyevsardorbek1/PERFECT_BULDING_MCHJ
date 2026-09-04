from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart, Command

from keyboards.main_menu import get_main_menu
from config import ADMIN_IDS
from database.session import get_db_session

async def cmd_start(message: types.Message, state: FSMContext):
    """Start command handler"""
    await state.clear()
    
    # Foydalanuvchini ADMIN_IDS ro'yxatida tekshirish
    is_admin = message.from_user.id in ADMIN_IDS
    
    # Rolga qarab menyu
    role = None
    with get_db_session() as db:
        from utils.access import get_user_role, role_label
        role = get_user_role(db, message.from_user.id)
        role_text = role_label(db, message.from_user.id)
    
    welcome_text = f"""
    👋 Assalomu alaykum, {message.from_user.full_name}!

    🏭 **Qurilish Materiallari Korxonasi Botiga xush kelibsiz!**

    🤖 Men sizning ishlab chiqarish jarayoningizni boshqarishga yordam beraman.

    📋 **Mening imkoniyatlarim:**
    • 🏭 Ishlab chiqarishni boshqarish
    • 📦 Ombordagi holatni kuzatish
    • 💰 Sotuvlar va mijozlar (CRM)
    • 🚚 Yetkazib beruvchilar va ta'minot
    • 🔒 Rezervatsiya, ko'chirish, inventarizatsiya
    • 📊 Statistika, hisobotlar va moliya
    """
    
    if is_admin:
        welcome_text += "\n\n👑 Siz **Administrator** maqomidasiz!"
    else:
        welcome_text += f"\n\n🔐 Sizning rolingiz: **{role_text}**"
    
    await message.answer(welcome_text, reply_markup=get_main_menu(role), parse_mode="Markdown")

async def cmd_help(message: types.Message):
    """Help command handler"""
    help_text = """
    🤖 **Botdan foydalanish bo'yicha ko'rsatmalar:**

    🏭 **Ishlab chiqarish:**
    • Yangi mahsulot ishlab chiqarish buyurtmasi berish
    • Jarayondagi buyurtmalarni kuzatish
    • Tayyor mahsulotlarni ombarga kiritish

    📦 **Ombor boshqaruvi:**
    • Xom ashyo holatini ko'rish
    • Yangi xom ashyo kiritish
    • Minimum zaxira chegarasini sozlash

    💰 **Moliya va hisob-kitob:**
    • Ishlab chiqarish xarajatlarini hisoblash
    • Foyda-marginal hisob-kitob
    • Narx tahlili

    📊 **Hisobotlar:**
    • Kunlik/haftalik/oylik hisobotlar
    • Excel formatda yuklab olish
    • Grafik va diagrammalar

    ⚙️ **Sozlamalar:**
    • Mahsulot formulalarini sozlash
    • Xodimlar ro'yxati
    • Ruxsatlarni boshqarish

    📞 **Qo'llab-quvvatlash:**
    Muammo yuzaga kelsa, administrator bilan bog'laning.
    """
    
    await message.answer(help_text, parse_mode="Markdown")

async def cmd_cancel(message: types.Message, state: FSMContext):
    """Cancel operation"""
    await state.clear()
    await message.answer("❌ Amal bekor qilindi.", reply_markup=get_main_menu())


async def expense_report(message: types.Message):
    """Xarajat hisobi"""
    from utils.access import ensure_access
    if not await ensure_access(message, "finance"):
        return
    from database.session import get_db_session
    from database import crud, models
    from datetime import datetime, timedelta, date
    from sqlalchemy import func

    with get_db_session() as db:
        today = date.today()
        month_start = today.replace(day=1)

        # Ishlab chiqarish xarajatlari
        production_costs = db.query(func.sum(models.ProductionOrder.total_cost)).filter(
            models.ProductionOrder.created_at >= month_start
        ).scalar() or 0

        # Maosh xarajatlari
        salary_costs = db.query(func.sum(models.SalaryPayment.total_amount)).filter(
            models.SalaryPayment.payment_date >= month_start,
            models.SalaryPayment.status == "paid"
        ).scalar() or 0

        # Sotuv daromadi
        sales_amount = db.query(func.sum(models.Sale.total_amount)).filter(
            models.Sale.sale_date >= month_start
        ).scalar() or 0

        net_profit = sales_amount - production_costs - salary_costs

    text = (
        f"💰 **XARAJAT HISOBI** ({today.strftime('%Y-%m')} oy)\n\n"
        f"📉 **Xarajatlar:**\n"
        f"• Ishlab chiqarish: {production_costs:,.0f} so'm\n"
        f"• Maosh to'lovlari: {salary_costs:,.0f} so'm\n"
        f"• Jami xarajat: {production_costs + salary_costs:,.0f} so'm\n\n"
        f"📈 **Daromadlar:**\n"
        f"• Sotuv daromadi: {sales_amount:,.0f} so'm\n\n"
        f"💎 **Natija:**\n"
        f"• Sof foyda: {net_profit:,.0f} so'm\n"
        f"• Foyda marjasi: {(net_profit / sales_amount * 100) if sales_amount > 0 else 0:.1f}%"
    )
    await message.answer(text, parse_mode="Markdown")


async def overall_statistics(message: types.Message):
    """Umumiy statistika"""
    from utils.access import ensure_access
    if not await ensure_access(message, "reports"):
        return
    from database.session import get_db_session
    from database import crud, models
    from sqlalchemy import func

    with get_db_session() as db:
        stats = crud.get_warehouse_statistics(db)

        total_orders = db.query(models.ProductionOrder).count()
        completed_orders = db.query(models.ProductionOrder).filter(
            models.ProductionOrder.status == models.OrderStatus.COMPLETED
        ).count()

        total_sales = db.query(models.Sale).count()
        total_sales_amount = db.query(func.sum(models.Sale.total_amount)).scalar() or 0

        total_employees = db.query(models.Employee).filter(
            models.Employee.status == models.EmployeeStatus.ACTIVE
        ).count()

    text = (
        f"📊 **UMUMIY STATISTIKA**\n\n"
        f"🏭 **Ishlab chiqarish:**\n"
        f"• Jami buyurtmalar: {total_orders} ta\n"
        f"• Bajarilgan: {completed_orders} ta\n\n"
        f"💰 **Sotuvlar:**\n"
        f"• Jami sotuvlar: {total_sales} ta\n"
        f"• Jami daromad: {total_sales_amount:,.0f} so'm\n\n"
        f"📦 **Ombor:**\n"
        f"• Xom ashyo turi: {stats['total_materials_count']} ta\n"
        f"• Yetarli bo'lmaganlar: {stats['low_stock_materials_count']} ta\n"
        f"• Umumiy qiymat: {stats['total_raw_materials_value']:,.0f} so'm\n\n"
        f"👥 **Xodimlar:**\n"
        f"• Faol: {total_employees} kishi"
    )
    await message.answer(text, parse_mode="Markdown")


async def settings_menu(message: types.Message):
    """Sozlamalar menyusi"""
    text = (
        f"⚙️ **SOZLAMALAR**\n\n"
        f"🔧 **Tizim:**\n"
        f"• Til: O'zbek\n"
        f"• Valyuta: UZS\n"
        f"• Vaqt zonasi: Asia/Tashkent\n\n"
        f"📝 **Sozlamalarni o'zgartirish uchun admin paneliga o'ting.**\n"
        f"👇 /admin buyrug'ini bering."
    )
    await message.answer(text, parse_mode="Markdown")


def register_handlers_start(dp: Dispatcher):
    """Register start handlers"""
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_help, Command("help"))
    dp.message.register(cmd_cancel, Command("cancel"))
    dp.message.register(cmd_cancel, F.text.in_(["⬅️ Orqaga", "❌ Bekor qilish"]))
    dp.message.register(expense_report, F.text == "💰 Xarajat hisobi")
    dp.message.register(overall_statistics, F.text == "📊 Statistika")
    dp.message.register(settings_menu, F.text == "⚙️ Sozlamalar")
