"""
AI Bashorat Handler - Sun'iy intellekt bashoratlari
"""

from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.session import get_db_session
from database import models
from keyboards.main_menu import get_main_menu
from utils.ai_prediction import (
    demand_predictor, price_optimizer, inventory_predictor,
    production_predictor, get_ai_recommendations
)
import logging

logger = logging.getLogger(__name__)


class AIPredictionStates(StatesGroup):
    waiting_product_selection = State()
    waiting_prediction_type = State()


async def ai_prediction_menu(message: types.Message):
    """AI bashorat menyusi"""
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        "🔮 Talab bashorati",
        "💰 Narx optimallashtirish",
        "📦 Ombor bashorati",
        "🏭 Ishlab chiqarish vaqti",
        "🤖 Umumiy tavsiyalar",
        "⬅️ Orqaga"
    ]
    keyboard.add(*buttons)
    
    await message.answer(
        "🤖 <b>AI BASHORAT TIZIMI</b>\n\n"
        "Sun'iy intellekt asosidagi bashoratlar va tavsiyalar.\n\n"
        "Amallardan birini tanlang:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def demand_prediction_start(message: types.Message):
    """Talab bashoratini boshlash"""
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    with get_db_session() as db:
        products = db.query(models.Product).filter(
            models.Product.is_active == True
        ).all()
        
        for product in products:
            keyboard.insert(
                types.InlineKeyboardButton(
                    text=product.name,
                    callback_data=f"pred_demand_{product.id}"
                )
            )
    
    await message.answer(
        "🔮 <b>TALAB BASHORATI</b>\n\n"
        "Mahsulotni tanlang:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await AIPredictionStates.waiting_product_selection.set()


async def process_demand_prediction(callback_query: types.CallbackQuery, state: FSMContext):
    """Talab bashoratini hisoblash"""
    await callback_query.answer()
    
    product_id = int(callback_query.data.replace("pred_demand_", ""))
    
    with get_db_session() as db:
        product = db.query(models.Product).filter(
            models.Product.id == product_id
        ).first()
        
        if not product:
            await callback_query.message.answer("❌ Mahsulot topilmadi.")
            await state.clear()
            return
        
        # Bashorat qilish
        predictions = demand_predictor.predict_demand(
            product_name=product.name,
            category=product.category,
            months_ahead=3
        )
        
        if not predictions:
            await callback_query.message.answer("❌ Bashorat qilib bo'lmadi.")
            await state.clear()
            return
        
        text = f"🔮 <b>{product.name} - TALAB BASHORATI</b>\n\n"
        
        for pred in predictions:
            text += (
                f"📅 <b>{pred.period}</b>\n"
                f"   📊 Joriy: {pred.current_value:.0f} birlik\n"
                f"   🔮 Bashorat: {pred.predicted_value:.0f} birlik\n"
                f"   📈 Trend: {pred.trend}\n"
                f"   🎯 Ishonch: {pred.confidence:.0f}%\n"
                f"   💡 {pred.recommendation}\n\n"
            )
        
        await callback_query.message.answer(text, parse_mode="HTML")
    
    await state.clear()


async def price_optimization_start(message: types.Message):
    """Narx optimallashtirishni boshlash"""
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    with get_db_session() as db:
        products = db.query(models.Product).filter(
            models.Product.is_active == True
        ).all()
        
        for product in products:
            keyboard.insert(
                types.InlineKeyboardButton(
                    text=product.name,
                    callback_data=f"pred_price_{product.id}"
                )
            )
    
    await message.answer(
        "💰 <b>NARX OPTIMALLASHTIRISH</b>\n\n"
        "Mahsulotni tanlang:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await AIPredictionStates.waiting_product_selection.set()


async def process_price_optimization(callback_query: types.CallbackQuery, state: FSMContext):
    """Narx optimallashtirishni hisoblash"""
    await callback_query.answer()
    
    product_id = int(callback_query.data.replace("pred_price_", ""))
    
    with get_db_session() as db:
        product = db.query(models.Product).filter(
            models.Product.id == product_id
        ).first()
        
        if not product:
            await callback_query.message.answer("❌ Mahsulot topilmadi.")
            await state.clear()
            return
        
        # Optimallashtirish
        result = price_optimizer.optimize_price(
            product_name=product.name,
            category=product.category,
            current_price=product.selling_price,
            production_cost=product.production_cost
        )
        
        text = (
            f"💰 <b>{product.name} - NARX OPTIMALLASHTIRISH</b>\n\n"
            f"📊 <b>Joriy holat:</b>\n"
            f"• Sotish narxi: {result['current_price']:,.0f} so'm\n"
            f"• Ishlab chiqarish: {result['production_cost']:,.0f} so'm\n"
            f"• Foyda: {result['profit_per_unit']:,.0f} so'm/birlik\n"
            f"• Foyda marjasi: {result['profit_margin']:.1f}%\n\n"
            f"📈 <b>Bozor tahlili:</b>\n"
            f"• O'rtacha bozor narxi: {result['market_avg']:,.0f} so'm\n"
            f"• Minimal narx: {result['price_range']['min']:,.0f} so'm\n"
            f"• Optimal narx: {result['price_range']['optimal']:,.0f} so'm\n"
            f"• Maksimal narx: {result['price_range']['max']:,.0f} so'm\n\n"
            f"💡 <b>Tavsiyalar:</b>\n"
        )
        
        for rec in result['recommendations']:
            text += f"• {rec}\n"
        
        await callback_query.message.answer(text, parse_mode="HTML")
    
    await state.clear()


async def inventory_prediction(message: types.Message):
    """Ombor bashorati"""
    
    with get_db_session() as db:
        materials = db.query(models.RawMaterial).all()
        
        if not materials:
            await message.answer("📭 Omborda materiallar mavjud emas.")
            return
        
        text = "📦 <b>OMBOR BASHORATI</b>\n\n"
        
        for mat in materials:
            status = inventory_predictor.predict_stockout(
                mat.name, mat.current_stock
            )
            
            status_icon = {
                "critical": "🔴",
                "warning": "🟡",
                "normal": "🟢",
                "good": "✅"
            }.get(status['status'], "⚪")
            
            text += (
                f"{status_icon} <b>{mat.name}</b>\n"
                f"   Qoldiq: {mat.current_stock:,.0f} {mat.unit}\n"
                f"   Kunlik sarf: {status['daily_usage']:.0f} {mat.unit}\n"
                f"   Tugash muddati: {status['days_until_stockout']:.0f} kun\n"
                f"   {status['recommendation']}\n\n"
            )
        
        await message.answer(text, parse_mode="HTML")


async def production_time_prediction(message: types.Message):
    """Ishlab chiqarish vaqtini bashorat qilish"""
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    with get_db_session() as db:
        products = db.query(models.Product).filter(
            models.Product.is_active == True
        ).all()
        
        for product in products:
            keyboard.insert(
                types.InlineKeyboardButton(
                    text=product.name,
                    callback_data=f"pred_time_{product.id}"
                )
            )
    
    await message.answer(
        "🏭 <b>ISHLAB CHIQARISH VAQTI</b>\n\n"
        "Mahsulotni tanlang:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def process_production_time(callback_query: types.CallbackQuery, state: FSMContext):
    """Ishlab chiqarish vaqtini hisoblash"""
    await callback_query.answer()
    
    product_id = int(callback_query.data.replace("pred_time_", ""))
    
    with get_db_session() as db:
        product = db.query(models.Product).filter(
            models.Product.id == product_id
        ).first()
        
        if not product:
            await callback_query.message.answer("❌ Mahsulot topilmadi.")
            return
        
        # 100 birlik uchun vaqtni bashorat qilish
        result = production_predictor.predict_production_time(
            category=product.category,
            quantity=100,
            workers=5
        )
        
        text = (
            f"🏭 <b>{product.name} - ISHLAB CHIQARISH VAQTI</b>\n\n"
            f"📊 <b>100 birlik uchun (5 ishchi):</b>\n\n"
            f"⏱️ Umumiy vaqt: {result['total_hours']:.1f} soat\n"
            f"📋 Shiftlar: {result['shifts_needed']} ta\n"
            f"📅 Kunlar: {result['days_needed']} kun\n"
            f"🎯 Tugash sanasi: {result['estimated_completion']}\n\n"
            f"💡 <b>Tavsiyalar:</b>\n"
        )
        
        if result['days_needed'] > 5:
            text += "• Ishchilar sonini oshiring yoki smenalar tashkil qiling\n"
        elif result['days_needed'] > 2:
            text += "• Vaqt yetarli, lekin rejalashtiring\n"
        else:
            text += "• Tezda bajarish mumkin\n"
        
        await callback_query.message.answer(text, parse_mode="HTML")
    
    await state.clear()


async def overall_ai_recommendations(message: types.Message):
    """Umumiy AI tavsiyalar"""
    
    with get_db_session() as db:
        products = db.query(models.Product).filter(
            models.Product.is_active == True
        ).all()
        
        text = "🤖 <b>UMUMIY AI TAVSIYALAR</b>\n\n"
        
        for product in products:
            recs = get_ai_recommendations(
                product_name=product.name,
                category=product.category,
                current_stock=1000,  # Taxminiy
                production_cost=product.production_cost,
                current_price=product.selling_price
            )
            
            text += f"📦 <b>{product.name}:</b>\n"
            text += f"   {recs['overall_recommendation']}\n\n"
        
        text += (
            "\n📊 <b>UMUMIY TAVSIYALAR:</b>\n"
            "• 📈 Talab oshishi kutilmoqda - zaxiralarni tayyorlang\n"
            "• 💰 Narxlarni bozor holatiga qarab sozlang\n"
            "• ⚠️ Xom ashyo zaxirasini nazorat qiling\n"
            "• 🏭 Ishlab chiqarish rejasini optimallashtiring"
        )
        
        await message.answer(text, parse_mode="HTML")


def register_handlers_ai(dp: Dispatcher):
    """AI bashorat handlerlarini ro'yxatdan o'tkazish"""
    
    dp.message.register(ai_prediction_menu, F.text == "🤖 AI bashorat")
    
    dp.message.register(demand_prediction_start, F.text == "🔮 Talab bashorati")
    
    dp.message.register(price_optimization_start, F.text == "💰 Narx optimallashtirish")
    
    dp.message.register(inventory_prediction, F.text == "📦 Ombor bashorati")
    
    dp.message.register(production_time_prediction, F.text == "🏭 Ishlab chiqarish vaqti")
    
    dp.message.register(overall_ai_recommendations, F.text == "🤖 Umumiy tavsiyalar")
    
    dp.message.register(ai_prediction_menu, F.text == "⬅️ Orqaga")
    
    dp.callback_query.register(process_demand_prediction,
                               F.data.startswith('pred_demand_'),
                               AIPredictionStates.waiting_product_selection)
    
    dp.callback_query.register(process_price_optimization,
                               F.data.startswith('pred_price_'),
                               AIPredictionStates.waiting_product_selection)
    
    dp.callback_query.register(process_production_time,
                               F.data.startswith('pred_time_'))
