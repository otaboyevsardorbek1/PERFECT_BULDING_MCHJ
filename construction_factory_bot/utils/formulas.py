"""
Qurilish materiallari ishlab chiqarish formulalari va hisob-kitob modullari
"""

import json
import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

@dataclass
class MaterialRequirement:
    """Material talab klassi"""
    material_id: int
    material_name: str
    quantity: float  # birlikdagi miqdor
    unit: str
    unit_price: float  # 1 birlik narxi
    total_cost: float  # umumiy xarajat
    
    def to_dict(self) -> dict:
        """Dictionary formatga o'tkazish"""
        return {
            'material_id': self.material_id,
            'material_name': self.material_name,
            'quantity': self.quantity,
            'unit': self.unit,
            'unit_price': self.unit_price,
            'total_cost': self.total_cost
        }

@dataclass
class ProductionCalculation:
    """Ishlab chiqarish hisobi natijasi"""
    product_id: int
    product_name: str
    quantity: int
    material_cost: float
    labor_cost: float
    energy_cost: float
    overhead_cost: float
    total_cost: float
    unit_cost: float
    selling_price: float
    profit_per_unit: float
    total_profit: float
    materials: List[MaterialRequirement]
    can_produce: bool
    missing_materials: List[Dict]
    
    def to_dict(self) -> dict:
        """Dictionary formatga o'tkazish"""
        return {
            'product_id': self.product_id,
            'product_name': self.product_name,
            'quantity': self.quantity,
            'material_cost': self.material_cost,
            'labor_cost': self.labor_cost,
            'energy_cost': self.energy_cost,
            'overhead_cost': self.overhead_cost,
            'total_cost': self.total_cost,
            'unit_cost': self.unit_cost,
            'selling_price': self.selling_price,
            'profit_per_unit': self.profit_per_unit,
            'total_profit': self.total_profit,
            'materials': [m.to_dict() for m in self.materials],
            'can_produce': self.can_produce,
            'missing_materials': self.missing_materials
        }

class ProductCategory(Enum):
    """Mahsulot kategoriyalari"""
    CEMENT = "sement"
    REBAR = "armatura"
    TILE = "kafel"
    FLOORING = "pol"
    GYPSUM = "gips"
    CONCRETE = "beton"
    BRICK = "g'isht"
    OTHER = "boshqa"

class FormulaManager:
    """Mahsulot formulalari boshqaruvchisi"""
    
    # Qurilish materiallari standart formulalari
    STANDARD_FORMULAS = {
        # Sement formulalari
        "Sement M500": {
            "category": ProductCategory.CEMENT,
            "unit": "qop",
            "weight_per_unit": 50,  # kg
            "formula": [
                {"material": "Klinker", "percentage": 90, "kg_per_unit": 45},
                {"material": "Gips", "percentage": 5, "kg_per_unit": 2.5},
                {"material": "Mineral qo'shimchalar", "percentage": 5, "kg_per_unit": 2.5}
            ],
            "production_steps": [
                "Aralashtirish",
                "Maydalash (sharli tegirmon)",
                "Sinfga ajratish",
                "Qadoqlash"
            ],
            "production_time_per_ton": 2.5,  # soat/tonna
            "energy_consumption_per_ton": 110  # kWh/tonna
        },
        
        # Rodbin (Armatura) formulalari
        "Rodbin 12mm": {
            "category": ProductCategory.REBAR,
            "unit": "metr",
            "weight_per_meter": 0.888,  # kg/m
            "formula": [
                {"material": "Temir sutka", "percentage": 95, "kg_per_meter": 0.844},
                {"material": "Oksir", "percentage": 3, "kg_per_meter": 0.027},
                {"material": "Karbon", "percentage": 2, "kg_per_meter": 0.018}
            ],
            "production_steps": [
                "Qizdirish (1200-1300°C)",
                "Prolkatka",
                "Shakllantirish",
                "Sovutish",
                "Kesish va birlashtirish"
            ],
            "production_time_per_ton": 1.5,  # soat/tonna
            "energy_consumption_per_ton": 450  # kWh/tonna
        },
        
        # Kafel formulalari
        "Kafel 30x30": {
            "category": ProductCategory.TILE,
            "unit": "dona",
            "size": "30x30 cm",
            "thickness": "8 mm",
            "formula": [
                {"material": "Gil", "percentage": 60, "kg_per_unit": 2.4},
                {"material": "Kvart qumi", "percentage": 30, "kg_per_unit": 1.2},
                {"material": "Rang beruvchi", "percentage": 5, "kg_per_unit": 0.2},
                {"material": "Kimyoviy qo'shimchalar", "percentage": 5, "kg_per_unit": 0.2}
            ],
            "production_steps": [
                "Xom ashyo aralashtirish",
                "Shakllantirish (presslash)",
                "Quritish",
                "Pishirish (1050-1150°C)",
                "Sirish (ixtiyoriy)",
                "Kontrol va paketlash"
            ],
            "production_time_per_1000": 48,  # soat/1000 dona
            "energy_consumption_per_1000": 850  # kWh/1000 dona
        },
        
        # Nalinoy pol formulalari
        "Nalinoy pol": {
            "category": ProductCategory.FLOORING,
            "unit": "m2",
            "thickness": "3-5 mm",
            "formula": [
                {"material": "Polivinilxlorid (PVC)", "percentage": 70, "kg_per_m2": 2.1},
                {"material": "Plastifikatorlar", "percentage": 15, "kg_per_m2": 0.45},
                {"material": "To'ldirgichlar", "percentage": 10, "kg_per_m2": 0.3},
                {"material": "Rang beruvchi", "percentage": 5, "kg_per_m2": 0.15}
            ],
            "production_steps": [
                "Xom ashyo aralashtirish",
                "Ekstruziya yoki kalendrlash",
                "Shakllantirish",
                "Presslash",
                "Kesish va birlashtirish",
                "Qadoqlash"
            ],
            "production_time_per_100m2": 8,  # soat/100 m2
            "energy_consumption_per_100m2": 180  # kWh/100 m2
        },
        
        # Gips formulalari
        "Gips qop 25kg": {
            "category": ProductCategory.GYPSUM,
            "unit": "qop",
            "weight_per_unit": 25,  # kg
            "formula": [
                {"material": "Gips toshi", "percentage": 90, "kg_per_unit": 22.5},
                {"material": "Suvoq qo'shimchalari", "percentage": 10, "kg_per_unit": 2.5}
            ],
            "production_steps": [
                "Maydalash",
                "Quritish",
                "Dehidratatsiya",
                "Maydalash (nozik)",
                "Aralashtirish",
                "Qadoqlash"
            ],
            "production_time_per_ton": 1.2,  # soat/tonna
            "energy_consumption_per_ton": 85  # kWh/tonna
        },
        
        # Beton formulalari
        "Beton M300": {
            "category": ProductCategory.CONCRETE,
            "unit": "m3",
            "density": 2400,  # kg/m3
            "formula": [
                {"material": "Sement", "percentage": 15, "kg_per_m3": 360},
                {"material": "Qum", "percentage": 30, "kg_per_m3": 720},
                {"material": "Shag'al", "percentage": 45, "kg_per_m3": 1080},
                {"material": "Suv", "percentage": 10, "liters_per_m3": 180}
            ],
            "production_steps": [
                "Xom ashyo tayyorlash",
                "Aralashtirish (beton aralashgich)",
                "Transport qilish",
                "Qadoqlash yoki to'g'ridan-to'g'ri quyish"
            ],
            "production_time_per_m3": 0.25,  # soat/m3
            "energy_consumption_per_m3": 15  # kWh/m3
        }
    }
    
    # Xom ashyo birlik narxlari (default)
    DEFAULT_MATERIAL_PRICES = {
        "Klinker": 500,       # so'm/kg
        "Gips": 300,          # so'm/kg
        "Mineral qo'shimchalar": 200,
        "Temir sutka": 2000,  # so'm/kg
        "Oksir": 800,
        "Karbon": 1200,
        "Gil": 150,
        "Kvart qumi": 400,
        "Rang beruvchi": 5000,
        "Kimyoviy qo'shimchalar": 2500,
        "Polivinilxlorid (PVC)": 1200,
        "Plastifikatorlar": 1800,
        "To'ldirgichlar": 600,
        "Gips toshi": 180,
        "Suvoq qo'shimchalari": 350,
        "Sement": 12000,      # so'm/qop
        "Qum": 50,           # so'm/kg
        "Shag'al": 80,       # so'm/kg
        "Suv": 2             # so'm/liter
    }
    
    # Mehnat stavkalari (soatlik)
    LABOR_RATES = {
        "operator": 25000,    # so'm/soat
        "texnik": 20000,
        "yordamchi": 15000,
        "kontrolchi": 30000
    }
    
    # Energiya narxlari
    ENERGY_RATES = {
        "electricity": 750,   # so'm/kWh
        "gas": 450,          # so'm/m3
        "water": 2           # so'm/liter
    }
    
    def __init__(self, db_connection=None):
        """Initsializatsiya"""
        self.db = db_connection
    
    def calculate_production_cost(self, 
                                 product_name: str, 
                                 quantity: int,
                                 custom_prices: Dict = None,
                                 labor_multiplier: float = 1.0,
                                 energy_multiplier: float = 1.0) -> ProductionCalculation:
        """
        Ishlab chiqarish xarajatlarini hisoblash
        
        Args:
            product_name: Mahsulot nomi
            quantity: Ishlab chiqarish miqdori
            custom_prices: Maxsus narxlar (agar mavjud bo'lsa)
            labor_multiplier: Mehnat xarajati ko'paytirgichi
            energy_multiplier: Energiya xarajati ko'paytirgichi
            
        Returns:
            ProductionCalculation obyekti
        """
        # Formula ma'lumotlarini olish
        if product_name not in self.STANDARD_FORMULAS:
            raise ValueError(f"{product_name} uchun formula topilmadi")
        
        formula_info = self.STANDARD_FORMULAS[product_name]
        
        # Narxlarni aniqlash
        prices = self.DEFAULT_MATERIAL_PRICES.copy()
        if custom_prices:
            prices.update(custom_prices)
        
        # Material xarajatlarini hisoblash
        material_requirements = []
        material_cost_total = 0
        missing_materials = []
        
        for item in formula_info["formula"]:
            material_name = item["material"]
            quantity_needed = item.get(f"kg_per_{formula_info['unit']}", 0) * quantity
            
            if material_name in prices:
                unit_price = prices[material_name]
                total_cost = quantity_needed * unit_price
                material_cost_total += total_cost
                
                material_requirements.append(
                    MaterialRequirement(
                        material_id=0,  # Ma'lumotlar bazasidan olinadi
                        material_name=material_name,
                        quantity=quantity_needed,
                        unit="kg",
                        unit_price=unit_price,
                        total_cost=total_cost
                    )
                )
            else:
                missing_materials.append({
                    "material": material_name,
                    "quantity_needed": quantity_needed,
                    "message": f"Narx aniqlanmagan"
                })
        
        # Mehnat xarajatlarini hisoblash
        labor_cost = self._calculate_labor_cost(product_name, quantity, formula_info, labor_multiplier)
        
        # Energiya xarajatlarini hisoblash
        energy_cost = self._calculate_energy_cost(product_name, quantity, formula_info, energy_multiplier)
        
        # Umumiy xarajatlar (25% overhead)
        overhead_cost = material_cost_total * 0.25
        
        # Jami xarajat
        total_cost = material_cost_total + labor_cost + energy_cost + overhead_cost
        unit_cost = total_cost / quantity if quantity > 0 else 0
        
        # Sotish narxi va foyda
        selling_price = self._estimate_selling_price(product_name, unit_cost)
        profit_per_unit = selling_price - unit_cost
        total_profit = profit_per_unit * quantity
        
        # Yetarli materiallar mavjudligini tekshirish
        can_produce = len(missing_materials) == 0
        
        return ProductionCalculation(
            product_id=0,
            product_name=product_name,
            quantity=quantity,
            material_cost=material_cost_total,
            labor_cost=labor_cost,
            energy_cost=energy_cost,
            overhead_cost=overhead_cost,
            total_cost=total_cost,
            unit_cost=unit_cost,
            selling_price=selling_price,
            profit_per_unit=profit_per_unit,
            total_profit=total_profit,
            materials=material_requirements,
            can_produce=can_produce,
            missing_materials=missing_materials
        )
    
    def _calculate_labor_cost(self, 
                             product_name: str, 
                             quantity: int, 
                             formula_info: Dict,
                             multiplier: float) -> float:
        """Mehnat xarajatlarini hisoblash"""
        # Ishlab chiqarish vaqtini hisoblash
        if "production_time_per_ton" in formula_info:
            weight_per_unit = formula_info.get("weight_per_unit", 1)
            total_weight = weight_per_unit * quantity / 1000  # tonnaga o'tkazish
            production_time = total_weight * formula_info["production_time_per_ton"]
        elif "production_time_per_1000" in formula_info:
            production_time = (quantity / 1000) * formula_info["production_time_per_1000"]
        elif "production_time_per_100m2" in formula_info:
            production_time = (quantity / 100) * formula_info["production_time_per_100m2"]
        elif "production_time_per_m3" in formula_info:
            production_time = quantity * formula_info["production_time_per_m3"]
        else:
            # Standart hisob: 1 birlik uchun 0.5 soat
            production_time = quantity * 0.5
        
        # Mehnatchilar soni va turi
        labor_team = {
            "operator": 2,    # 2 ta operator
            "texnik": 1,      # 1 ta texnik
            "yordamchi": 2,   # 2 ta yordamchi ishchi
            "kontrolchi": 1   # 1 ta nazoratchi
        }
        
        # Jami mehnat xarajati
        total_labor_cost = 0
        for position, count in labor_team.items():
            hourly_rate = self.LABOR_RATES.get(position, 20000)
            total_labor_cost += count * production_time * hourly_rate
        
        return total_labor_cost * multiplier
    
    def _calculate_energy_cost(self, 
                              product_name: str, 
                              quantity: int, 
                              formula_info: Dict,
                              multiplier: float) -> float:
        """Energiya xarajatlarini hisoblash"""
        # Elektr energiyasi xarajati
        electricity_cost = 0
        if "energy_consumption_per_ton" in formula_info:
            weight_per_unit = formula_info.get("weight_per_unit", 1)
            total_weight = weight_per_unit * quantity / 1000  # tonnaga o'tkazish
            electricity_consumption = total_weight * formula_info["energy_consumption_per_ton"]
        elif "energy_consumption_per_1000" in formula_info:
            electricity_consumption = (quantity / 1000) * formula_info["energy_consumption_per_1000"]
        elif "energy_consumption_per_100m2" in formula_info:
            electricity_consumption = (quantity / 100) * formula_info["energy_consumption_per_100m2"]
        elif "energy_consumption_per_m3" in formula_info:
            electricity_consumption = quantity * formula_info["energy_consumption_per_m3"]
        else:
            # Standart hisob: 1 birlik uchun 10 kWh
            electricity_consumption = quantity * 10
        
        electricity_cost = electricity_consumption * self.ENERGY_RATES["electricity"]
        
        # Gaz xarajati (agar kerak bo'lsa)
        gas_cost = 0
        if product_name in ["Sement M500", "Kafel 30x30"]:
            # Pishirish uchun gaz
            gas_consumption = electricity_consumption * 0.3  # taxminiy
            gas_cost = gas_consumption * self.ENERGY_RATES["gas"]
        
        # Suv xarajati
        water_cost = 0
        if product_name == "Beton M300":
            water_needed = quantity * 180  # liter/m3
            water_cost = water_needed * self.ENERGY_RATES["water"]
        
        return (electricity_cost + gas_cost + water_cost) * multiplier
    
    def _estimate_selling_price(self, product_name: str, unit_cost: float) -> float:
        """Sotish narxini taxminiy hisoblash"""
        # Foyda marjasi (40% standart)
        profit_margin = 0.40
        
        # Mahsulot turi bo'yicha foyda marjasini sozlash
        profit_margins = {
            "Sement M500": 0.35,      # 35%
            "Rodbin 12mm": 0.40,      # 40%
            "Kafel 30x30": 0.50,      # 50%
            "Nalinoy pol": 0.45,      # 45%
            "Gips qop 25kg": 0.30,    # 30%
            "Beton M300": 0.25        # 25%
        }
        
        if product_name in profit_margins:
            profit_margin = profit_margins[product_name]
        
        # Sotish narxi = Xarajat × (1 + Foyda marjasi)
        selling_price = unit_cost * (1 + profit_margin)
        
        # Minimal narx chegarasi
        min_prices = {
            "Sement M500": 10000,
            "Rodbin 12mm": 4000,
            "Kafel 30x30": 700,
            "Nalinoy pol": 2500,
            "Gips qop 25kg": 3000,
            "Beton M300": 500000
        }
        
        if product_name in min_prices:
            selling_price = max(selling_price, min_prices[product_name])
        
        return round(selling_price, 2)
    
    def get_production_steps(self, product_name: str) -> List[str]:
        """Ishlab chiqarish bosqichlarini olish"""
        if product_name in self.STANDARD_FORMULAS:
            return self.STANDARD_FORMULAS[product_name].get("production_steps", [])
        return []
    
    def get_product_info(self, product_name: str) -> Dict:
        """Mahsulot haqida ma'lumot olish"""
        if product_name in self.STANDARD_FORMULAS:
            return self.STANDARD_FORMULAS[product_name]
        return {}
    
    def validate_formula(self, formula_data: Dict) -> Tuple[bool, List[str]]:
        """
        Formulani tekshirish
        
        Args:
            formula_data: Formula ma'lumotlari
            
        Returns:
            (tekshirish natijasi, xato xabarlari)
        """
        errors = []
        
        # Majburiy maydonlarni tekshirish
        required_fields = ["product_name", "unit", "formula"]
        for field in required_fields:
            if field not in formula_data:
                errors.append(f"Majburiy maydon yo'q: {field}")
        
        # Formula bo'lishini tekshirish
        if "formula" in formula_data:
            formula_items = formula_data["formula"]
            total_percentage = sum(item.get("percentage", 0) for item in formula_items)
            
            if abs(total_percentage - 100) > 0.1:  # 0.1% chegarasi
                errors.append(f"Formulalar yig'indisi 100% bo'lishi kerak. Hozir: {total_percentage}%")
        
        # Miqdorlarni tekshirish
        for i, item in enumerate(formula_data.get("formula", [])):
            if "material" not in item:
                errors.append(f"Formula {i+1}: material nomi yo'q")
            if "percentage" not in item:
                errors.append(f"Formula {i+1}: foiz yo'q")
            elif item["percentage"] <= 0:
                errors.append(f"Formula {i+1}: foiz musbat bo'lishi kerak")
        
        return len(errors) == 0, errors
    
    def save_formula_to_db(self, formula_data: Dict) -> bool:
        """Formulani ma'lumotlar bazasiga saqlash"""
        if not self.db:
            return False
        
        try:
            # Formulani tekshirish
            is_valid, errors = self.validate_formula(formula_data)
            if not is_valid:
                print("Formula noto'g'ri:", errors)
                return False
            
            # Ma'lumotlar bazasiga saqlash logikasi
            # Bu yerda ma'lumotlar bazasi amaliyoti bo'ladi
            return True
            
        except Exception as e:
            print(f"Formulani saqlashda xatolik: {e}")
            return False
    
    def create_custom_formula(self, 
                             product_name: str,
                             materials: List[Dict],
                             unit: str = "qop") -> Dict:
        """
        Maxsus formula yaratish
        
        Args:
            product_name: Mahsulot nomi
            materials: Materiallar ro'yxati
            unit: O'lchov birligi
            
        Returns:
            Formula ma'lumotlari
        """
        # Materiallarning umumiy foizini hisoblash
        total_percentage = sum(material.get("percentage", 0) for material in materials)
        
        # Agar 100% dan farq qilsa, normalizatsiya qilish
        if abs(total_percentage - 100) > 0.1:
            # Normalizatsiya qilish
            for material in materials:
                if "percentage" in material:
                    material["percentage"] = (material["percentage"] / total_percentage) * 100
        
        formula = {
            "product_name": product_name,
            "category": "custom",
            "unit": unit,
            "formula": materials,
            "production_steps": [
                "Xom ashyo tayyorlash",
                "Aralashtirish",
                "Shakllantirish",
                "Qadoqlash"
            ],
            "notes": "Maxsus formula"
        }
        
        return formula

# Qo'shimcha hisoblash funksiyalari
class CostCalculator:
    """Xarajat hisoblagichi"""
    
    @staticmethod
    def calculate_break_even_point(fixed_costs: float, price_per_unit: float, variable_cost_per_unit: float) -> float:
        """
        Zararsizlik nuqtasini hisoblash
        
        Args:
            fixed_costs: Doimiy xarajatlar
            price_per_unit: Birlik narxi
            variable_cost_per_unit: O'zgaruvchan xarajat/birlik
            
        Returns:
            Zararsizlik nuqtasi (birliklar soni)
        """
        if price_per_unit <= variable_cost_per_unit:
            return float('inf')  # Hech qachon zararsiz bo'lmaydi
        
        return fixed_costs / (price_per_unit - variable_cost_per_unit)
    
    @staticmethod
    def calculate_profit_margin(selling_price: float, cost_price: float) -> float:
        """Foyda marjasini hisoblash (%)"""
        if cost_price == 0:
            return 0
        return ((selling_price - cost_price) / cost_price) * 100
    
    @staticmethod
    def calculate_markup(selling_price: float, cost_price: float) -> float:
        """Narx belgilash qiymatini hisoblash (%)"""
        if cost_price == 0:
            return 0
        return ((selling_price - cost_price) / selling_price) * 100
    
    @staticmethod
    def calculate_inventory_turnover(sales: float, average_inventory: float) -> float:
        """Inventar aylanish koeffitsiyentini hisoblash"""
        if average_inventory == 0:
            return 0
        return sales / average_inventory

# Material sifatini baholash funksiyalari
class QualityAssessor:
    """Material sifatini baholovchi"""
    
    @staticmethod
    def assess_cement_quality(parameters: Dict) -> Dict:
        """
        Sement sifatini baholash
        
        Args:
            parameters: Sement parametrlari
        
        Returns:
            Sifat bahosi
        """
        score = 100
        
        # Klinker darajasi (90-95% optimal)
        clinker_rate = parameters.get("clinker_rate", 0)
        if clinker_rate < 90:
            score -= (90 - clinker_rate) * 2
        elif clinker_rate > 95:
            score -= (clinker_rate - 95) * 1
        
        # Pishirish darajasi
        burning_degree = parameters.get("burning_degree", "normal")
        if burning_degree == "under":
            score -= 20
        elif burning_degree == "over":
            score -= 15
        
        # Maydalanish darajasi
        fineness = parameters.get("fineness", 3000)  # cm²/g
        if fineness < 2800:
            score -= 10
        elif fineness > 4000:
            score -= 5
        
        # Birlashtirish vaqti
        setting_time = parameters.get("setting_time", {"initial": 45, "final": 600})
        if setting_time["initial"] < 30:
            score -= 15
        if setting_time["final"] > 720:
            score -= 10
        
        # Kuch (MPa)
        strength = parameters.get("strength", {"3d": 15, "28d": 45})
        if strength["3d"] < 10:
            score -= 25
        if strength["28d"] < 42.5:
            score -= 30
        
        # Sifat darajasi
        if score >= 90:
            quality = "Yuqori"
        elif score >= 75:
            quality = "Yaxshi"
        elif score >= 60:
            quality = "O'rtacha"
        else:
            quality = "Past"
        
        return {
            "score": score,
            "quality": quality,
            "recommendations": QualityAssessor._get_cement_recommendations(parameters)
        }
    
    @staticmethod
    def _get_cement_recommendations(params: Dict) -> List[str]:
        """Sement uchun tavsiyalar"""
        recommendations = []
        
        if params.get("clinker_rate", 0) < 90:
            recommendations.append("Klinker nisbatini oshiring (90-95% optimal)")
        
        if params.get("fineness", 3000) < 2800:
            recommendations.append("Maydalash darajasini oshiring (2800-3500 cm²/g)")
        
        if params.get("strength", {}).get("28d", 0) < 42.5:
            recommendations.append("28 kunlik kuchni oshiring (kamida 42.5 MPa)")
        
        return recommendations

# Eksport uchun
def export_formulas_to_json(formulas: Dict, filename: str = "formulas.json") -> bool:
    """Formulalarni JSON formatida eksport qilish"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(formulas, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Eksport qilishda xatolik: {e}")
        return False

def import_formulas_from_json(filename: str) -> Dict:
    """Formulalarni JSON formatidan import qilish"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Import qilishda xatolik: {e}")
        return {}

# Modulni test qilish uchun
if __name__ == "__main__":
    # Test hisoblash
    formula_manager = FormulaManager()
    
    # Sement hisobi
    print("=== SEMENT M500 ISHLAB CHIQARISH HISOBI ===")
    calculation = formula_manager.calculate_production_cost("Sement M500", 100)
    
    print(f"Mahsulot: {calculation.product_name}")
    print(f"Miqdor: {calculation.quantity} {calculation.unit}")
    print(f"Jami xarajat: {calculation.total_cost:,.0f} so'm")
    print(f"Birlik xarajati: {calculation.unit_cost:,.0f} so'm")
    print(f"Sotish narxi: {calculation.selling_price:,.0f} so'm")
    print(f"Birlik foydasi: {calculation.profit_per_unit:,.0f} so'm")
    print(f"Jami foyda: {calculation.total_profit:,.0f} so'm")
    
    print("\nMateriallar:")
    for material in calculation.materials:
        print(f"  • {material.material_name}: {material.quantity} kg - {material.total_cost:,.0f} so'm")
    
    print("\nXarajatlar taqsimoti:")
    print(f"  Materiallar: {calculation.material_cost:,.0f} so'm")
    print(f"  Mehnat: {calculation.labor_cost:,.0f} so'm")
    print(f"  Energiya: {calculation.energy_cost:,.0f} so'm")
    print(f"  Qo'shimcha: {calculation.overhead_cost:,.0f} so'm")
    
    print("\nIshlab chiqarish bosqichlari:")
    for i, step in enumerate(formula_manager.get_production_steps("Sement M500"), 1):
        print(f"  {i}. {step}")


############################################################################################################
#============================foydalanish uchun namunalar========================================#
# Formulalar menedjerini yaratish
# from utils.formulas import FormulaManager

# manager = FormulaManager()

# # Ishlab chiqarish xarajatini hisoblash
# calculation = manager.calculate_production_cost(
#     product_name="Sement M500",
#     quantity=100,  # 100 qop
#     custom_prices={"Klinker": 550},  # Maxsus narxlar
#     labor_multiplier=1.1,  # Mehnat xarajati 10% yuqori
#     energy_multiplier=0.9  # Energiya xarajati 10% past
# )

# # Natijalarni ko'rish
# print(f"Jami xarajat: {calculation.total_cost:,.0f} so'm")
# print(f"Birlik narxi: {calculation.unit_cost:,.0f} so'm")
# print(f"Sotish narxi: {calculation.selling_price:,.0f} so'm")

# # Ishlab chiqarish bosqichlari
# steps = manager.get_production_steps("Sement M500")
# for step in steps:
#     print(f"- {step}")

# # Maxsus formula yaratish
# custom_formula = manager.create_custom_formula(
#     product_name="Maxsus g'isht",
#     materials=[
#         {"material": "Gil", "percentage": 70, "kg_per_unit": 3.5},
#         {"material": "Qum", "percentage": 20, "kg_per_unit": 1.0},
#         {"material": "Kimyoviy moddalar", "percentage": 10, "kg_per_unit": 0.5}
#     ],
#     unit="dona"
# )

# # Sifatni baholash
# from utils.formulas import QualityAssessor

# quality_result = QualityAssessor.assess_cement_quality({
#     "clinker_rate": 92,
#     "burning_degree": "normal",
#     "fineness": 3200,
#     "strength": {"3d": 18, "28d": 48}
# })

# print(f"Sifat bahosi: {quality_result['score']}/100")
# print(f"Sifat darajasi: {quality_result['quality']}")