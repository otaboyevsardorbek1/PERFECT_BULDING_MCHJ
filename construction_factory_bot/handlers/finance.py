"""
Moliya moduli — v3
Nasiya qarzlari, Foyda/Zarar (P&L), soliq kalkulyatori
"""
from datetime import datetime, timedelta

from aiogram import types, Dispatcher, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from database.session import get_db_session
from database import models, crud
from utils.access import ensure_access


def get_finance_menu():
    buttons = [
        [KeyboardButton(text="📋 Nasiya qarzlari"), KeyboardButton(text="🔴 Muddati o'tganlar")],
        [KeyboardButton(text="📊 Foyda/Zarar (P&L)"), KeyboardButton(text="💰 Soliq kalkulyatori")],
        [KeyboardButton(text="⬅️ Orqaga")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


async def finance_menu(message: types.Message):
    if not await ensure_access(message, "finance"):
        return
    await message.answer(
        "💰 <b>MOLIYA</b>\n\n"
        "Nasiya qarzlari, foyda/zarar va soliq hisob-kitoblari.",
        reply_markup=get_finance_menu(), parse_mode="HTML"
    )


async def credit_debts(message: types.Message):
    with get_db_session() as db:
        sales = crud.get_credit_sales(db, limit=30)
        if not sales:
            await message.answer("🎉 To'lanmagan nasiya sotuvlari yo'q.",
                                 reply_markup=get_finance_menu())
            return
        text = "📋 <b>NASIYA QARZLARI</b>\n\n"
        total_remaining = 0.0
        for s in sales:
            remaining = (s.total_amount or 0) - (s.paid_amount or 0)
            total_remaining += remaining
            overdue = "🔴" if s.due_date and s.due_date < datetime.utcnow() and s.credit_status != "toliq_tolangan" else "🟡"
            text += (
                f"{overdue} {s.invoice_number} — {s.customer_name or '-'}\n"
                f"   Summa: {s.total_amount:,.0f} | To'langan: {s.paid_amount:,.0f}\n"
                f"   Qoldiq: {remaining:,.0f} | Muddat: {s.due_date.strftime('%d.%m.%Y') if s.due_date else '-'}\n\n"
            )
        text += f"📊 <b>Jami qoldiq: {total_remaining:,.0f} so'm</b>\n\n"
        text += "💡 To'lov olish uchun: 👥 Mijozlar → 🧾 Qarz to'lovi"
        await message.answer(text[:4000], reply_markup=get_finance_menu(), parse_mode="HTML")


async def overdue_debts(message: types.Message):
    with get_db_session() as db:
        report = crud.get_customer_debts_report(db)
        if report["overdue_count"] == 0:
            await message.answer("✅ Muddati o'tgan qarzlar yo'q!", reply_markup=get_finance_menu())
            return
        text = f"🔴 <b>MUDDATI O'TGAN QARZLAR</b> ({report['overdue_count']})\n\n"
        for item in report["overdue_list"]:
            text += f"• {item['customer']}: {item['debt']:,.0f} so'm ({item['overdue_count']} ta sotuv)\n"
        text += f"\n📊 Umumiy qarz: {report['total_debt']:,.0f} so'm\n"
        text += "💡 Eslatma uchun: 🔔 Bildirishnomalar bo'limidan foydalaning"
        await message.answer(text, reply_markup=get_finance_menu(), parse_mode="HTML")


async def pl_report(message: types.Message):
    with get_db_session() as db:
        today = datetime.utcnow().date()
        month_start = today.replace(day=1)
        month_report = crud.get_pl_report(db, month_start, today)

        week_ago = today - timedelta(days=7)
        week_report = crud.get_pl_report(db, week_ago, today)

        text = (
            f"📊 <b>FOYDA/ZARAR (P&L)</b>\n\n"
            f"📅 <b>Bu oy ({month_start.strftime('%B %Y')}):</b>\n"
            f"• Daromad: {month_report['revenue']:,.0f} so'm\n"
            f"• Chegirmalar: {month_report['discounts']:,.0f} so'm\n"
            f"• Tannarx (COGS): {month_report['cogs']:,.0f} so'm\n"
            f"• Ishlab chiqarish xarajati: {month_report['production_cost']:,.0f} so'm\n"
            f"• Maosh: {month_report['salary_cost']:,.0f} so'm\n"
            f"• 💎 Sof foyda: <b>{month_report['net_profit']:,.0f} so'm</b>\n"
            f"• Foyda marjasi: {month_report['profit_margin']}%\n\n"
            f"📅 <b>Oxirgi 7 kun:</b>\n"
            f"• Daromad: {week_report['revenue']:,.0f} so'm\n"
            f"• Sof foyda: {week_report['net_profit']:,.0f} so'm\n"
        )
        await message.answer(text, reply_markup=get_finance_menu(), parse_mode="HTML")


async def tax_calculator(message: types.Message):
    with get_db_session() as db:
        today = datetime.utcnow().date()
        month_start = today.replace(day=1)
        month_report = crud.get_pl_report(db, month_start, today)
        revenue = month_report["revenue"]
        tax_qqs = crud.calculate_tax(revenue, 12.0)
        tax_turnover = crud.calculate_tax(revenue, 4.0)

        text = (
            f"💰 <b>SOLIQ KALKULYATORI</b>\n\n"
            f"📅 Davr: {month_start.strftime('%Y-%m')}\n"
            f"📊 Aylanma (daromad): {revenue:,.0f} so'm\n\n"
            f"🧾 <b>QQS (12%):</b>\n"
            f"• QQS summasi: {tax_qqs['qqs']:,.0f} so'm\n"
            f"• Soliqsiz: {tax_qqs['net']:,.0f} so'm\n\n"
            f"🧾 <b>Aylanma soliq (4%):</b>\n"
            f"• Soliq summasi: {tax_turnover['qqs']:,.0f} so'm\n"
            f"• Soliqsiz: {tax_turnover['net']:,.0f} so'm\n\n"
            f"⚖️ Soliq rejimini tanlashda hisobchi/buxgalter bilan maslahatlashing."
        )
        await message.answer(text, reply_markup=get_finance_menu(), parse_mode="HTML")


def register_handlers_finance(dp: Dispatcher):
    dp.message.register(finance_menu, F.text == "💰 Moliya")
    dp.message.register(finance_menu, F.text == "🧾 Nasiya to'lovlari")
    dp.message.register(credit_debts, F.text == "📋 Nasiya qarzlari")
    dp.message.register(overdue_debts, F.text == "🔴 Muddati o'tganlar")
    dp.message.register(pl_report, F.text == "📊 Foyda/Zarar (P&L)")
    dp.message.register(tax_calculator, F.text == "💰 Soliq kalkulyatori")
