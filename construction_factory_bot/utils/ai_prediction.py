"""
AI Bashorat - Sun'iy intellekt asosidagi bashorat moduli
Talabni bashorat qilish, narxni optimallashtirish
"""

import math
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, date
from dataclasses import dataclass
from enum import Enum


class PredictionType(Enum):
    """Bashorat turlari"""
    DEMAND = "talab"
    PRICE = "narx"
    INVENTORY = "ombor"
    PRODUCTION = "ishlab_chiqarish"


@dataclass
class PredictionResult:
    """Bashorat natijasi"""
    prediction_type: PredictionType
    product_name: str
    current_value: float
    predicted_value: float
    confidence: float  # 0-100%
    trend: str  # "osmoqda", "kamaymoqda", "barqaror"
    recommendation: str
    period: str
    
    def to_dict(self) -> dict:
        return {
            'prediction_type': self.prediction_type.value,
            'product_name': self.product_name,
            'current_value': self.current_value,
            'predicted_value': self.predicted_value,
            'confidence': self.confidence,
            'trend': self.trend,
            'recommendation': self.recommendation,
            'period': self.period
        }


class DemandPredictor:
    """Talab bashoratchisi"""
    
    def __init__(self):
        # O'rtacha o'sish koeffitsientlari (qurilish materiallari uchun)
        self.seasonal_factors = {
            1: 0.7,   # Yanvar - past (qish)
            2: 0.75,  # Fevral
            3: 0.9,   # Mart - o'sish
            4: 1.1,   # Aprel - yuqori
            5: 1.2,   # May - eng yuqori
            6: 1.25,  # Iyun - eng yuqori
            7: 1.2,   # Iyul
            8: 1.15,  # Avgust
            9: 1.1,   # Sentabr
            10: 0.9,  # Oktabr - kamayish
            11: 0.8,  # Noyabr
            12: 0.7   # Dekabr - past (qish)
        }
        
        # Mahsulot kategoriyalari bo'yicha o'rtacha talab
        self.category_demand = {
            "sement": {"base": 100, "growth": 0.05},
            "rodbin": {"base": 80, "growth": 0.04},
            "kafel": {"base": 150, "growth": 0.06},
            "pol": {"base": 120, "growth": 0.05},
            "gips": {"base": 60, "growth": 0.03}
        }
    
    def predict_demand(self, product_name: str, category: str,
                       historical_data: List[float] = None,
                       months_ahead: int = 3) -> List[PredictionResult]:
        """
        Talabni bashorat qilish
        
        Args:
            product_name: Mahsulot nomi
            category: Kategoriya
            historical_data: Tarixiy ma'lumotlar (oxirgi 12 oy)
            months_ahead: Necha oy oldin bashorat
            
        Returns:
            List[PredictionResult]: Bashoratlar
        """
        
        results = []
        
        # Kategoriya ma'lumotlari
        cat_data = self.category_demand.get(category, {"base": 100, "growth": 0.05})
        base_demand = cat_data["base"]
        growth_rate = cat_data["growth"]
        
        # Agar tarixiy ma'lumot bo'lsa, o'rtacha hisoblash
        if historical_data and len(historical_data) >= 3:
            avg_demand = sum(historical_data) / len(historical_data)
            # Oxirgi 3 oy trendini aniqlash
            recent = historical_data[-3:]
            trend = (recent[-1] - recent[0]) / recent[0] if recent[0] > 0 else 0
        else:
            avg_demand = base_demand
            trend = growth_rate
        
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        for i in range(1, months_ahead + 1):
            target_month = current_month + i
            target_year = current_year
            
            if target_month > 12:
                target_month -= 12
                target_year += 1
            
            # Oylik omil
            seasonal = self.seasonal_factors.get(target_month, 1.0)
            
            # Bashorat
            predicted = avg_demand * (1 + trend * i) * seasonal
            
            # Ishonch darajasi ( oy uzoqlashganda kamayadi)
            confidence = max(50, 90 - (i * 10))
            
            # Trend aniqlash
            if trend > 0.02:
                trend_text = "📈 Osmoqda"
            elif trend < -0.02:
                trend_text = "📉 Kamaymoqda"
            else:
                trend_text = "➡️ Barqaror"
            
            # Tavsiya
            if predicted > avg_demand * 1.2:
                recommendation = "Ishlab chiqarishni oshiring - talab oshishi kutilmoqda"
            elif predicted < avg_demand * 0.8:
                recommendation = "Ishlab chiqarishni kamaytiring - talab kamayishi kutilmoqda"
            else:
                recommendation = "Joriy rejani saqlang"
            
            month_names = {
                1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel",
                5: "May", 6: "Iyun", 7: "Iyul", 8: "Avgust",
                9: "Sentabr", 10: "Oktabr", 11: "Noyabr", 12: "Dekabr"
            }
            
            results.append(PredictionResult(
                prediction_type=PredictionType.DEMAND,
                product_name=product_name,
                current_value=avg_demand,
                predicted_value=round(predicted, 1),
                confidence=confidence,
                trend=trend_text,
                recommendation=recommendation,
                period=f"{month_names[target_month]} {target_year}"
            ))
        
        return results


class PriceOptimizer:
    """Narx optimallashtiruvchisi"""
    
    def __init__(self):
        # Bozor narxlari (taxminiy, so'm/birlik)
        self.market_prices = {
            "sement": {"min": 10000, "max": 15000, "avg": 12000},
            "rodbin": {"min": 3500, "max": 5500, "avg": 4500},
            "kafel": {"min": 600, "max": 1200, "avg": 850},
            "pol": {"min": 2200, "max": 3500, "avg": 2800},
            "gips": {"min": 2800, "max": 4200, "avg": 3500}
        }
        
        # Raqobatchilik koeffitsientlari
        self.competition_factor = 0.85  # Bozor narxining 85%
    
    def optimize_price(self, product_name: str, category: str,
                       current_price: float, production_cost: float,
                       demand_level: str = "normal") -> Dict:
        """
        Narxni optimallashtirish
        
        Args:
            product_name: Mahsulot nomi
            category: Kategoriya
            current_price: Joriy narx
            production_cost: Ishlab chiqarish xarajati
            demand_level: Talab darajasi ("past", "normal", "yuqori")
            
        Returns:
            Dict: Optimallashtirish natijasi
        """
        
        market = self.market_prices.get(category, {"min": 1000, "max": 5000, "avg": 3000})
        
        # Minimal foyda marjasi (20%)
        min_price = production_cost * 1.2
        
        # Bozor narxi asosida optimal narx
        market_optimal = market["avg"] * self.competition_factor
        
        # Talab darajasiga qarab sozlash
        demand_multiplier = {
            "past": 0.95,
            "normal": 1.0,
            "yuqori": 1.05
        }
        
        multiplier = demand_multiplier.get(demand_level, 1.0)
        
        # Optimal narx
        optimal_price = max(min_price, market_optimal * multiplier)
        
        # Narx diapazoni
        price_range = {
            "min": round(min_price, -2),  # 100 ga yaqinlashtirish
            "optimal": round(optimal_price, -2),
            "max": round(market["max"] * 0.95, -2)  # Bozor narxidan pastroq
        }
        
        # Foyda hisobi
        profit_per_unit = optimal_price - production_cost
        profit_margin = (profit_per_unit / optimal_price * 100) if optimal_price > 0 else 0
        
        # Tavsiyalar
        recommendations = []
        
        if current_price < min_price:
            recommendations.append("⚠️ Narx ishlab chiqarish xarajatidan past! Zarar ko'rish mumkin.")
        
        if current_price > market["max"]:
            recommendations.append("⚠️ Narx bozor narxidan yuqori! Raqobatchilar ortida qolasiz.")
        
        if profit_margin < 20:
            recommendations.append("📉 Foyda marjasi past. Narxni oshiring yoki xarajatlarni kamaytiring.")
        elif profit_margin > 50:
            recommendations.append("📈 Foyda marjasi yuqori. Narxni biroz kamaytirish mumkin.")
        
        if demand_level == "yuqori":
            recommendations.append("📈 Talab yuqori - narxni 5-10% oshirish mumkin.")
        elif demand_level == "past":
            recommendations.append("📉 Talab past - narxni kamaytirish yoki aksiyalar tashkil qilish.")
        
        return {
            "product_name": product_name,
            "current_price": current_price,
            "production_cost": production_cost,
            "price_range": price_range,
            "profit_per_unit": round(profit_per_unit, 2),
            "profit_margin": round(profit_margin, 1),
            "market_avg": market["avg"],
            "demand_level": demand_level,
            "recommendations": recommendations
        }


class InventoryPredictor:
    """Ombor bashoratchisi"""
    
    def __init__(self):
        # Kunlik sarf normasi (taxminiy, kg/kun)
        self.daily_usage_rates = {
            "Klinker": 50,
            "Gips": 25,
            "Qum": 100,
            "Temir sutka": 40,
            "Gil": 30,
            "Kvart qumi": 30,
            "Shag'al": 75
        }
    
    def predict_stockout(self, material_name: str, current_stock: float,
                         daily_usage: float = None) -> Dict:
        """
        Ombor tugashini bashorat qilish
        
        Args:
            material_name: Material nomi
            current_stock: Joriy qoldiq
            daily_usage: Kunlik sarf (agar berilmasa, standart)
            
        Returns:
            Dict: Bashorat natijasi
        """
        
        if daily_usage is None:
            daily_usage = self.daily_usage_rates.get(material_name, 30)
        
        if daily_usage <= 0:
            return {
                "material_name": material_name,
                "current_stock": current_stock,
                "days_until_stockout": float('inf'),
                "status": "not_used",
                "recommendation": "Material hozircha ishlatilmayapti"
            }
        
        # Tugash kunlari
        days_until_stockout = current_stock / daily_usage
        
        # Holat aniqlash
        if days_until_stockout <= 3:
            status = "critical"
            recommendation = "🚨 JUDA SHOSHILINCH! 3 kundan kam qoldi. Darhol buyurtma bering!"
        elif days_until_stockout <= 7:
            status = "warning"
            recommendation = "⚠️ Ogohlantirish! 1 haftadan kam qoldi. Buyurtma tayyorlang."
        elif days_until_stockout <= 14:
            status = "normal"
            recommendation = "✅ Normal holat. Lekin rejalashtirib qo'ying."
        else:
            status = "good"
            recommendation = "✅ Yetarli zaxira. Keyingi 2 hafta xavfsiz."
        
        # Yetkazib berish vaqtini hisobga olish (taxminiy 3-5 kun)
        delivery_time = 4  # kun
        safe_stock = daily_usage * delivery_time
        
        if current_stock <= safe_stock:
            recommendation += f"\n📦 Yetkazib berish vaqti ({delivery_time} kun) hisobga olinganda, zaxira yetarli emas!"
        
        return {
            "material_name": material_name,
            "current_stock": current_stock,
            "daily_usage": daily_usage,
            "days_until_stockout": round(days_until_stockout, 1),
            "status": status,
            "safe_stock": safe_stock,
            "recommendation": recommendation,
            "delivery_time_days": delivery_time
        }
    
    def calculate_optimal_order(self, material_name: str, current_stock: float,
                                daily_usage: float = None,
                                lead_time_days: int = 4,
                                safety_days: int = 7) -> Dict:
        """
        Optimal buyurtma miqdorini hisoblash
        
        Args:
            material_name: Material nomi
            current_stock: Joriy qoldiq
            daily_usage: Kunlik sarf
            lead_time_days: Yetkazib berish vaqti (kun)
            safety_days: Xavfsiz zaxira (kun)
            
        Returns:
            Dict: Buyurtma ma'lumotlari
        """
        
        if daily_usage is None:
            daily_usage = self.daily_usage_rates.get(material_name, 30)
        
        # Yetkazib berish vaqtidagi talab
        lead_time_demand = daily_usage * lead_time_days
        
        # Xavfsiz zaxira
        safety_stock = daily_usage * safety_days
        
        # Qayta buyurtma nuqtasi
        reorder_point = lead_time_demand + safety_stock
        
        # Optimal buyurtma (30 kunlik)
        optimal_order = daily_usage * 30
        
        # Joriy holat
        if current_stock <= reorder_point:
            should_order = True
            urgency = "yuqori" if current_stock <= lead_time_demand else "o'rta"
        else:
            should_order = False
            urgency = "past"
        
        return {
            "material_name": material_name,
            "current_stock": current_stock,
            "daily_usage": daily_usage,
            "lead_time_demand": lead_time_demand,
            "safety_stock": safety_stock,
            "reorder_point": reorder_point,
            "optimal_order_quantity": round(optimal_order),
            "should_order": should_order,
            "urgency": urgency,
            "days_until_stockout": round(current_stock / daily_usage, 1) if daily_usage > 0 else float('inf')
        }


class ProductionPredictor:
    """Ishlab chiqarish bashoratchisi"""
    
    def __init__(self):
        # Mehnat unumdorligi (birlik/soat)
        self.productivity_rates = {
            "sement": 20,   # 20 qop/soat
            "rodbin": 50,   # 50 metr/soat
            "kafel": 100,   # 100 dona/soat
            "pol": 30,      # 30 m2/soat
            "gips": 40      # 40 qop/soat
        }
    
    def predict_production_time(self, category: str, quantity: int,
                                workers: int = 1) -> Dict:
        """
        Ishlab chiqarish vaqtini bashorat qilish
        
        Args:
            category: Mahsulot kategoriyasi
            quantity: Miqdor
            workers: Ishchilar soni
            
        Returns:
            Dict: Bashorat natijasi
        """
        
        productivity = self.productivity_rates.get(category, 25)
        
        # Jami ish vaqti (soat)
        total_hours = quantity / (productivity * workers)
        
        # Shiftlar (8 soatlik)
        shifts = math.ceil(total_hours / 8)
        
        # Kunlar
        days = math.ceil(shifts / 1)  # 1 shift = 1 kun
        
        return {
            "category": category,
            "quantity": quantity,
            "workers": workers,
            "productivity_per_hour": productivity,
            "total_hours": round(total_hours, 1),
            "shifts_needed": shifts,
            "days_needed": days,
            "estimated_completion": (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
        }


# Global instancylar
demand_predictor = DemandPredictor()
price_optimizer = PriceOptimizer()
inventory_predictor = InventoryPredictor()
production_predictor = ProductionPredictor()


def get_ai_recommendations(product_name: str, category: str,
                           current_stock: float = 0,
                           production_cost: float = 0,
                           current_price: float = 0) -> Dict:
    """
    AI tavsiyalarini olish
    
    Args:
        product_name: Mahsulot nomi
        category: Kategoriya
        current_stock: Joriy zaxira
        production_cost: Ishlab chiqarish xarajati
        current_price: Joriy narx
        
    Returns:
        Dict: Tavsiyalar
    """
    
    recommendations = {
        "product_name": product_name,
        "demand_prediction": None,
        "price_optimization": None,
        "inventory_status": None,
        "overall_recommendation": ""
    }
    
    # Talab bashorati
    demand_predictions = demand_predictor.predict_demand(
        product_name, category, months_ahead=3
    )
    if demand_predictions:
        recommendations["demand_prediction"] = [p.to_dict() for p in demand_predictions]
    
    # Narx optimallashtirishi
    if current_price > 0 and production_cost > 0:
        price_opt = price_optimizer.optimize_price(
            product_name, category, current_price, production_cost
        )
        recommendations["price_optimization"] = price_opt
    
    # Ombor bashorati
    if current_stock > 0:
        inventory_status = inventory_predictor.predict_stockout(
            product_name, current_stock
        )
        recommendations["inventory_status"] = inventory_status
    
    # Umumiy tavsiya
    overall = []
    
    if demand_predictions and demand_predictions[0].predicted_value > demand_predictions[0].current_value * 1.1:
        overall.append("📈 Talab oshishi kutilmoqda - ishlab chiqarishni tayyorlang")
    
    if recommendations.get("inventory_status", {}).get("status") in ["critical", "warning"]:
        overall.append("⚠️ Ombor zaxirasi kamaymoqda - xom ashyo buyurtma qiling")
    
    if recommendations.get("price_optimization", {}).get("profit_margin", 0) < 20:
        overall.append("💰 Foyda marjasi past - narxni ko'rib chiqing")
    
    if not overall:
        overall.append("✅ Tizim normal rejada ishlayapti")
    
    recommendations["overall_recommendation"] = " | ".join(overall)
    
    return recommendations
