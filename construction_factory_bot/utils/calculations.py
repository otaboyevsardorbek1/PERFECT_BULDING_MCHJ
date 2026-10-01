"""
Qurilish materiallari korxonasi uchun barcha hisob-kitob funksiyalari
"""

import math
from typing import Dict, List, Optional, Tuple, Union, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

@dataclass
class CalculationResult:
    """Hisob-kitob natijalari"""
    success: bool
    data: Dict
    warnings: List[str]
    errors: List[str]
    
    def to_dict(self) -> Dict:
        """Dictionary formatga o'tkazish"""
        return {
            "success": self.success,
            "data": self.data,
            "warnings": self.warnings,
            "errors": self.errors
        }

class CostCategory(Enum):
    """Xarajat toifalari"""
    MATERIAL = "material"
    LABOR = "labor"
    ENERGY = "energy"
    OVERHEAD = "overhead"
    TRANSPORT = "transport"
    PACKAGING = "packaging"
    QUALITY = "quality"
    OTHER = "other"

class ProductionCalculator:
    """Ishlab chiqarish hisob-kitoblari"""
    
    def __init__(self, db_manager: Optional[Any] = None):
        self.db = db_manager
        
        # Standart koeffitsientlar
        self.COST_COEFFICIENTS = {
            CostCategory.LABOR: 0.25,      # Material xarajatining 25%
            CostCategory.ENERGY: 0.15,     # Material xarajatining 15%
            CostCategory.OVERHEAD: 0.10,   # Material xarajatining 10%
            CostCategory.TRANSPORT: 0.05,  # Material xarajatining 5%
            CostCategory.PACKAGING: 0.03,  # Material xarajatining 3%
            CostCategory.QUALITY: 0.02,    # Material xarajatining 2%
        }
        
        # Mahsulot turlari bo'yicha ko'rsatkichlar
        self.PRODUCT_COEFFICIENTS = {
            "sement": {
                "labor": 0.20,    # 20%
                "energy": 0.18,   # 18% (yuqori energiya talabi)
                "production_time_per_unit": 0.5  # soat/qop
            },
            "armatura": {
                "labor": 0.30,    # 30%
                "energy": 0.25,   # 25%
                "production_time_per_unit": 0.3  # soat/metr
            },
            "kafel": {
                "labor": 0.35,    # 35%
                "energy": 0.20,   # 20%
                "production_time_per_unit": 0.4  # soat/dona
            },
            "pol": {
                "labor": 0.25,    # 25%
                "energy": 0.15,   # 15%
                "production_time_per_unit": 0.2  # soat/m2
            },
            "beton": {
                "labor": 0.15,    # 15%
                "energy": 0.10,   # 10%
                "production_time_per_unit": 0.1  # soat/m3
            }
        }
        
        # Mehnat stavkalari (soatlik)
        self.LABOR_RATES = {
            "master": 30000,      # Usta
            "operator": 25000,    # Operator
            "worker": 20000,      # Ishchi
            "helper": 15000,      # Yordamchi
            "controller": 35000   # Nazoratchi
        }
        
        # Energiya narxlari
        self.ENERGY_RATES = {
            "electricity": 750,   # so'm/kWh
            "gas": 450,           # so'm/m3
            "diesel": 1200,       # so'm/liter
            "water": 2            # so'm/liter
        }
    
    def calculate_production_cost(self, product_id: int, quantity: int, 
                                 custom_coefficients: Optional[Dict] = None) -> CalculationResult:
        """
        Ishlab chiqarish xarajatlarini hisoblash
        """
        warnings = []
        errors = []
        
        try:
            # Agar database manager bo'lmasa, mock formula ishlatish
            if self.db and hasattr(self.db, 'get_product_formula'):
                formula = self.db.get_product_formula(product_id)
            else:
                # Mock formula
                formula = [
                    {'material_name': 'Klinker', 'quantity': 45, 'price_per_unit': 500, 'unit': 'kg'},
                    {'material_name': 'Gips', 'quantity': 5, 'price_per_unit': 300, 'unit': 'kg'},
                ]
            
            if not formula:
                return CalculationResult(
                    success=False,
                    data={},
                    warnings=[],
                    errors=["Mahsulot formulasi topilmadi"]
                )
            
            # Material xarajatlarini hisoblash
            material_calculation = self._calculate_material_costs(formula, quantity)
            total_material_cost = material_calculation["total_cost"]
            materials_needed = material_calculation["materials_needed"]
            
            warnings.extend(material_calculation["warnings"])
            
            # Mahsulot turini aniqlash (ko'rsatkichlar uchun)
            product_category = self._get_product_category(product_id)
            
            # Qo'shimcha xarajatlarni hisoblash
            additional_costs = self._calculate_additional_costs(
                product_category, 
                total_material_cost, 
                quantity,
                custom_coefficients
            )
            
            # Umumiy xarajatlar
            total_cost = total_material_cost + sum(additional_costs.values())
            unit_cost = total_cost / quantity if quantity > 0 else 0
            
            # Xarajatlar taqsimoti (foizda)
            cost_distribution = self._calculate_cost_distribution(
                total_material_cost, 
                additional_costs, 
                total_cost
            )
            
            # Foyda hisobi
            profit_calculation = self._calculate_profit_margins(
                product_id, unit_cost, quantity
            )
            
            result_data = {
                'total_cost': round(total_cost, 2),
                'unit_cost': round(unit_cost, 2),
                'quantity': quantity,
                'material_cost': round(total_material_cost, 2),
                'additional_costs': {k.value: round(v, 2) for k, v in additional_costs.items()},
                'cost_distribution': cost_distribution,
                'materials_needed': materials_needed,
                'profit_margins': profit_calculation,
                'production_efficiency': self._calculate_efficiency_metrics(
                    product_category, quantity, total_cost
                )
            }
            
            return CalculationResult(
                success=True,
                data=result_data,
                warnings=warnings,
                errors=errors
            )
            
        except Exception as e:
            return CalculationResult(
                success=False,
                data={},
                warnings=[],
                errors=[f"Hisoblashda xatolik: {str(e)}"]
            )
    
    def _calculate_material_costs(self, formula: List[Dict], quantity: int) -> Dict:
        """Material xarajatlarini hisoblash"""
        total_cost = 0
        materials_needed = []
        warnings = []
        
        for item in formula:
            try:
                material_quantity = item.get('quantity', 0) * quantity
                unit_price = item.get('price_per_unit', 0)
                
                if unit_price <= 0:
                    material_name = item.get('material_name', 'Noma\'lum')
                    warnings.append(f"{material_name} uchun narx belgilanmagan")
                    unit_price = self._estimate_material_price(material_name)
                
                material_cost = material_quantity * unit_price
                total_cost += material_cost
                
                materials_needed.append({
                    'name': item.get('material_name', 'Noma\'lum'),
                    'quantity': round(material_quantity, 3),
                    'unit': item.get('unit', 'kg'),
                    'unit_price': round(unit_price, 2),
                    'total_cost': round(material_cost, 2)
                })
                
            except KeyError as e:
                warnings.append(f"Formulada maydon yo'q: {e}")
            except Exception as e:
                warnings.append(f"Material hisobida xatolik: {e}")
        
        return {
            "total_cost": total_cost,
            "materials_needed": materials_needed,
            "warnings": warnings
        }
    
    def _calculate_additional_costs(self, product_category: str, 
                                   material_cost: float, 
                                   quantity: int,
                                   custom_coefficients: Optional[Dict] = None) -> Dict:
        """Qo'shimcha xarajatlarni hisoblash"""
        coefficients = self.COST_COEFFICIENTS.copy()
        
        # Mahsulot turi bo'yicha sozlash
        if product_category in self.PRODUCT_COEFFICIENTS:
            for key, value in self.PRODUCT_COEFFICIENTS[product_category].items():
                if key in ["labor", "energy"]:
                    try:
                        coefficients[CostCategory(key.upper())] = value
                    except:
                        pass
        
        # Maxsus koeffitsientlar
        if custom_coefficients:
            for key, value in custom_coefficients.items():
                try:
                    if isinstance(key, str):
                        coefficients[CostCategory(key.upper())] = value
                    else:
                        coefficients[key] = value
                except (KeyError, ValueError):
                    pass
        
        additional_costs = {}
        
        # Mehnat xarajatlari
        labor_rate = coefficients.get(CostCategory.LABOR, 0.25)
        additional_costs[CostCategory.LABOR] = material_cost * labor_rate
        
        # Energiya xarajatlari
        energy_rate = coefficients.get(CostCategory.ENERGY, 0.15)
        additional_costs[CostCategory.ENERGY] = material_cost * energy_rate
        
        # Boshqa xarajatlar
        for cost_type, coefficient in coefficients.items():
            if cost_type not in [CostCategory.LABOR, CostCategory.ENERGY]:
                additional_costs[cost_type] = material_cost * coefficient
        
        return additional_costs
    
    def _calculate_cost_distribution(self, material_cost: float, 
                                    additional_costs: Dict, 
                                    total_cost: float) -> Dict:
        """Xarajatlar taqsimotini hisoblash"""
        distribution = {}
        
        if total_cost <= 0:
            return distribution
        
        # Material xarajatlari
        distribution["material"] = {
            "amount": material_cost,
            "percentage": (material_cost / total_cost * 100)
        }
        
        # Qo'shimcha xarajatlar
        for cost_type, amount in additional_costs.items():
            if isinstance(cost_type, CostCategory):
                key = cost_type.value
            else:
                key = str(cost_type)
            
            distribution[key] = {
                "amount": amount,
                "percentage": (amount / total_cost * 100)
            }
        
        return distribution
    
    def _calculate_profit_margins(self, product_id: int, unit_cost: float, quantity: int) -> Dict:
        """Foyda marjalarini hisoblash"""
        try:
            # Agar database bo'lsa, mahsulot narxini olish
            selling_price = 0
            if self.db and hasattr(self.db, 'get_product_selling_price'):
                selling_price = self.db.get_product_selling_price(product_id)
            
            if selling_price <= 0:
                selling_price = unit_cost * 1.4  # 40% foyda
            
            profit_per_unit = selling_price - unit_cost
            total_profit = profit_per_unit * quantity
            
            profit_margin = (profit_per_unit / unit_cost * 100) if unit_cost > 0 else 0
            markup = (profit_per_unit / selling_price * 100) if selling_price > 0 else 0
            
            # Minimal foyda tekshiruvi
            min_profit_percentage = 20  # 20%
            if profit_margin < min_profit_percentage:
                recommended_price = unit_cost * (1 + min_profit_percentage/100)
            else:
                recommended_price = selling_price
            
            return {
                "selling_price": round(selling_price, 2),
                "profit_per_unit": round(profit_per_unit, 2),
                "total_profit": round(total_profit, 2),
                "profit_margin": round(profit_margin, 2),
                "markup": round(markup, 2),
                "recommended_price": round(recommended_price, 2),
                "is_profitable": profit_margin >= min_profit_percentage
            }
            
        except Exception:
            # Standart hisob
            selling_price = unit_cost * 1.4
            profit_per_unit = selling_price - unit_cost
            
            return {
                "selling_price": round(selling_price, 2),
                "profit_per_unit": round(profit_per_unit, 2),
                "total_profit": round(profit_per_unit * quantity, 2),
                "profit_margin": 40.0,
                "markup": 28.57,
                "recommended_price": round(selling_price, 2),
                "is_profitable": True
            }
    
    def _calculate_efficiency_metrics(self, product_category: str, 
                                     quantity: int, total_cost: float) -> Dict:
        """Samaradorlik ko'rsatkichlarini hisoblash"""
        metrics = {}
        
        # Ishlab chiqarish vaqti
        if product_category in self.PRODUCT_COEFFICIENTS:
            time_per_unit = self.PRODUCT_COEFFICIENTS[product_category].get(
                "production_time_per_unit", 0.3
            )
            total_time = time_per_unit * quantity
            metrics["production_time_hours"] = round(total_time, 2)
            metrics["units_per_hour"] = round(1 / time_per_unit, 2) if time_per_unit > 0 else 0
        
        # Xarajat samaradorligi
        metrics["cost_per_unit"] = round(total_cost / quantity, 2) if quantity > 0 else 0
        
        # Mehnat unumdorligi
        labor_cost = total_cost * self.COST_COEFFICIENTS.get(CostCategory.LABOR, 0.25)
        metrics["labor_productivity"] = round(quantity / (labor_cost / 20000), 2) if labor_cost > 0 else 0
        
        return metrics
    
    def _get_product_category(self, product_id: int) -> str:
        """Mahsulot kategoriyasini olish"""
        # Agar database bo'lsa, kategoriyani olish
        if self.db and hasattr(self.db, 'get_product_category'):
            return self.db.get_product_category(product_id)
        return "sement"  # Default
    
    def _estimate_material_price(self, material_name: str) -> float:
        """Material narxini taxminiy hisoblash"""
        price_map = {
            "klinker": 500,
            "gips": 300,
            "qum": 50,
            "shag'al": 80,
            "temir": 2000,
            "gil": 150,
            "plastik": 1200,
            "kimyoviy": 2500,
            "default": 1000
        }
        
        for key, price in price_map.items():
            if key.lower() in material_name.lower():
                return price
        
        return price_map["default"]

class WarehouseCalculator:
    """Ombor hisob-kitoblari"""
    
    @staticmethod
    def calculate_inventory_value(inventory: List[Dict]) -> Dict:
        """Inventar qiymatini hisoblash"""
        total_value = 0
        items = []
        
        for item in inventory:
            try:
                quantity = item.get('quantity', 0)
                unit_price = item.get('unit_price', 0)
                item_value = quantity * unit_price
                total_value += item_value
                
                items.append({
                    'name': item.get('name', 'Noma\'lum'),
                    'quantity': quantity,
                    'unit_price': unit_price,
                    'total_value': item_value
                })
            except Exception as e:
                print(f"Inventar hisobida xatolik: {e}")
        
        # Qiymat taqsimoti
        sorted_items = sorted(items, key=lambda x: x['total_value'], reverse=True)
        top_items = sorted_items[:5] if len(sorted_items) > 5 else sorted_items
        
        return {
            'total_value': round(total_value, 2),
            'item_count': len(items),
            'average_value_per_item': round(total_value / len(items), 2) if items else 0,
            'items': items,
            'top_items': top_items
        }
    
    @staticmethod
    def calculate_reorder_point(current_stock: float, 
                               daily_usage: float, 
                               lead_time_days: int, 
                               safety_stock: Optional[float] = None) -> Dict:
        """
        Qayta buyurtma nuqtasini hisoblash
        """
        if daily_usage <= 0:
            return {
                'reorder_point': 0,
                'safety_stock': 0,
                'lead_time_demand': 0,
                'days_remaining': 0,
                'status': 'not_used'
            }
        
        # Yetkazib berish muddatidagi talab
        lead_time_demand = daily_usage * lead_time_days
        
        # Xavfsizlik zaxirasi (agar berilmagan bo'lsa, standart)
        if safety_stock is None:
            safety_stock = daily_usage * 3  # 3 kunlik zaxira
        
        # Qayta buyurtma nuqtasi
        reorder_point = lead_time_demand + safety_stock
        
        # Qancha kun yetadi
        days_remaining = current_stock / daily_usage if daily_usage > 0 else 0
        
        # Holat
        if current_stock <= safety_stock:
            status = 'critical'
        elif current_stock <= reorder_point:
            status = 'low'
        elif current_stock <= reorder_point * 1.5:
            status = 'normal'
        else:
            status = 'high'
        
        return {
            'reorder_point': round(reorder_point, 2),
            'safety_stock': round(safety_stock, 2),
            'lead_time_demand': round(lead_time_demand, 2),
            'current_stock': round(current_stock, 2),
            'days_remaining': round(days_remaining, 1),
            'status': status,
            'recommended_order': max(0, round(reorder_point - current_stock, 2))
        }
    
    @staticmethod
    def calculate_inventory_turnover(sales_value: float, 
                                    average_inventory_value: float) -> Dict:
        """
        Inventar aylanishini hisoblash
        """
        if average_inventory_value <= 0:
            return {
                'turnover_ratio': 0,
                'days_in_inventory': 0,
                'efficiency': 'very_low'
            }
        
        # Aylanish koeffitsiyenti
        turnover_ratio = sales_value / average_inventory_value
        
        # Inventarda qolish kunlari
        days_in_inventory = 365 / turnover_ratio if turnover_ratio > 0 else 365
        
        # Samaradorlik bahosi
        if turnover_ratio > 12:
            efficiency = 'excellent'
        elif turnover_ratio > 8:
            efficiency = 'good'
        elif turnover_ratio > 4:
            efficiency = 'average'
        elif turnover_ratio > 2:
            efficiency = 'low'
        else:
            efficiency = 'very_low'
        
        return {
            'turnover_ratio': round(turnover_ratio, 2),
            'days_in_inventory': round(days_in_inventory, 1),
            'efficiency': efficiency,
            'recommended_turnover': 6,  # Yiliga 6 marta optimal
            'needs_improvement': turnover_ratio < 4
        }


class FinancialCalculator:
    """Moliyaviy hisob-kitoblar"""
    
    @staticmethod
    def calculate_break_even(fixed_costs: float, 
                            price_per_unit: float, 
                            variable_cost_per_unit: float) -> Dict:
        """
        Zararsizlik nuqtasini hisoblash
        """
        if price_per_unit <= variable_cost_per_unit:
            return {
                'break_even_units': float('inf'),
                'break_even_sales': float('inf'),
                'contribution_margin': 0,
                'margin_ratio': 0,
                'is_feasible': False
            }
        
        # Kontributsiya marjasi
        contribution_margin = price_per_unit - variable_cost_per_unit
        margin_ratio = contribution_margin / price_per_unit if price_per_unit > 0 else 0
        
        # Zararsizlik nuqtasi (birliklar soni)
        break_even_units = fixed_costs / contribution_margin
        
        # Zararsizlik nuqtasi (sotish summasi)
        break_even_sales = break_even_units * price_per_unit
        
        return {
            'break_even_units': round(break_even_units),
            'break_even_sales': round(break_even_sales, 2),
            'contribution_margin': round(contribution_margin, 2),
            'margin_ratio': round(margin_ratio, 3),
            'is_feasible': True
        }
    
    @staticmethod
    def calculate_roi(investment: float, 
                     net_profit: float, 
                     period_years: float = 1) -> Dict:
        """
        Investitsiya rentabelligini hisoblash (ROI)
        """
        if investment <= 0:
            return {
                'roi_percentage': 0,
                'annual_roi': 0,
                'payback_period': float('inf'),
                'return_rating': 'invalid'
            }
        
        # ROI foizda
        roi_percentage = (net_profit / investment) * 100
        
        # Yillik ROI
        annual_roi = roi_percentage / period_years if period_years > 0 else roi_percentage
        
        # Qaytarilish muddati
        payback_period = investment / net_profit if net_profit > 0 else float('inf')
        
        # Baholash
        if annual_roi > 50:
            rating = 'excellent'
        elif annual_roi > 30:
            rating = 'very_good'
        elif annual_roi > 20:
            rating = 'good'
        elif annual_roi > 10:
            rating = 'average'
        elif annual_roi > 0:
            rating = 'poor'
        else:
            rating = 'loss'
        
        return {
            'roi_percentage': round(roi_percentage, 2),
            'annual_roi': round(annual_roi, 2),
            'payback_period_years': round(payback_period, 2),
            'payback_period_months': round(payback_period * 12, 1),
            'return_rating': rating,
            'is_profitable': roi_percentage > 0
        }
    
    @staticmethod
    def calculate_depreciation(asset_value: float, 
                              salvage_value: float, 
                              useful_life_years: int,
                              method: str = 'straight_line') -> Dict:
        """
        Amortizatsiyani hisoblash
        """
        if useful_life_years <= 0:
            return {
                'annual_depreciation': 0,
                'monthly_depreciation': 0,
                'total_depreciation': 0,
                'depreciation_schedule': []
            }
        
        depreciable_amount = asset_value - salvage_value
        
        if method == 'straight_line':
            # To'g'ri chiziqli usul
            annual_depreciation = depreciable_amount / useful_life_years
            monthly_depreciation = annual_depreciation / 12
            
            # Jadval yaratish
            schedule = []
            book_value = asset_value
            
            for year in range(1, useful_life_years + 1):
                book_value -= annual_depreciation
                if book_value < salvage_value:
                    book_value = salvage_value
                
                schedule.append({
                    'year': year,
                    'depreciation': round(annual_depreciation, 2),
                    'book_value': round(book_value, 2)
                })
        
        elif method == 'declining_balance':
            # Kamayuvchi qoldiq usuli (2 barobar)
            rate = 2 / useful_life_years
            schedule = []
            book_value = asset_value
            
            for year in range(1, useful_life_years + 1):
                depreciation = book_value * rate
                # So'nggi yilda qoldiq qiymatga yetguncha
                if year == useful_life_years:
                    depreciation = book_value - salvage_value
                
                book_value -= depreciation
                if book_value < salvage_value:
                    book_value = salvage_value
                    depreciation = book_value - salvage_value
                
                schedule.append({
                    'year': year,
                    'depreciation': round(depreciation, 2),
                    'book_value': round(book_value, 2)
                })
            
            annual_depreciation = schedule[0]['depreciation']
            monthly_depreciation = annual_depreciation / 12
        
        else:
            # To'g'ri chiziqli (default)
            annual_depreciation = depreciable_amount / useful_life_years
            monthly_depreciation = annual_depreciation / 12
            schedule = []
        
        return {
            'annual_depreciation': round(annual_depreciation, 2),
            'monthly_depreciation': round(monthly_depreciation, 2),
            'total_depreciation': round(depreciable_amount, 2),
            'depreciation_schedule': schedule,
            'method': method
        }


class EfficiencyCalculator:
    """Samaradorlik hisob-kitoblari"""
    
    @staticmethod
    def calculate_productivity(total_output: float, 
                              total_hours: float, 
                              number_of_workers: int = 1) -> Dict:
        """
        Mehnat unumdorligini hisoblash
        """
        if total_hours <= 0 or number_of_workers <= 0:
            return {
                'output_per_hour': 0,
                'output_per_worker_hour': 0,
                'efficiency_score': 0,
                'rating': 'very_low'
            }
        
        # Soatiga ishlab chiqarish
        output_per_hour = total_output / total_hours
        
        # Ishchi-soatiga ishlab chiqarish
        output_per_worker_hour = total_output / (total_hours * number_of_workers)
        
        # Samaradorlik bahosi (standart: 10 birlik/soat = 100 ball)
        standard_output = 10  # birlik/soat
        efficiency_score = min(100, (output_per_hour / standard_output) * 100)
        
        # Baholash
        if efficiency_score >= 90:
            rating = 'excellent'
        elif efficiency_score >= 75:
            rating = 'good'
        elif efficiency_score >= 60:
            rating = 'average'
        elif efficiency_score >= 40:
            rating = 'low'
        else:
            rating = 'very_low'
        
        return {
            'total_output': total_output,
            'total_hours': total_hours,
            'workers': number_of_workers,
            'output_per_hour': round(output_per_hour, 2),
            'output_per_worker_hour': round(output_per_worker_hour, 2),
            'efficiency_score': round(efficiency_score, 1),
            'rating': rating,
            'recommended_improvement': EfficiencyCalculator._get_productivity_recommendations(rating)
        }
    
    @staticmethod
    def _get_productivity_recommendations(rating: str) -> List[str]:
        """Unumdorlik uchun tavsiyalar"""
        recommendations = {
            'very_low': [
                "Ish jarayonini qayta ko'rib chiqing",
                "Ishchilarni qayta o'qitish",
                "Texnologiyani yangilash"
            ],
            'low': [
                "Vaqtdan yaxshiroq foydalanish",
                "Ish tartibini takomillashtirish",
                "Kichik texnik yaxshilanishlar"
            ],
            'average': [
                "Optimal rejalashtirish",
                "Ishchilarni rag'batlantirish",
                "Doimiy monitoring"
            ],
            'good': [
                "Eng yaxshi amaliyotlarni saqlash",
                "Doimiy yaxshilash",
                "Jamoa ishini rivojlantirish"
            ],
            'excellent': [
                "Natijalarni saqlash",
                "Tajribani boshqa bo'limlarga o'tkazish",
                "Innovatsiyalarni davom ettirish"
            ]
        }
        return recommendations.get(rating, [])
    
    @staticmethod
    def calculate_equipment_utilization(actual_hours: float, 
                                       available_hours: float) -> Dict:
        """
        Uskuna foydalanish koeffitsiyentini hisoblash
        """
        if available_hours <= 0:
            return {
                'utilization_rate': 0,
                'idle_rate': 100,
                'status': 'not_available'
            }
        
        utilization_rate = (actual_hours / available_hours) * 100
        idle_rate = 100 - utilization_rate
        
        if utilization_rate >= 90:
            status = 'over_utilized'
        elif utilization_rate >= 75:
            status = 'optimal'
        elif utilization_rate >= 50:
            status = 'under_utilized'
        elif utilization_rate >= 25:
            status = 'low'
        else:
            status = 'very_low'
        
        return {
            'actual_hours': actual_hours,
            'available_hours': available_hours,
            'utilization_rate': round(utilization_rate, 1),
            'idle_rate': round(idle_rate, 1),
            'status': status,
            'recommended_hours': available_hours * 0.75  # 75% optimal
        }


# Qo'shimcha yordamchi funksiyalar
def format_currency(amount: float) -> str:
    """Summani formatlash"""
    if amount is None:
        return "0 so'm"
    return f"{amount:,.0f} so'm".replace(",", " ")

def format_percentage(value: float) -> str:
    """Foizni formatlash"""
    if value is None:
        return "0%"
    return f"{value:.1f}%"

def calculate_growth_rate(current: float, previous: float) -> float:
    """O'sish sur'atini hisoblash"""
    if previous == 0:
        return 0
    return ((current - previous) / previous) * 100

# Asosiy ishlatish uchun test
def main():
    """Test funksiyasi"""
    print("=== HISOB-KITOB MODULI TESTI ===\n")
    
    # Ishlab chiqarish hisobi
    print("1. Ishlab chiqarish xarajati hisobi:")
    calculator = ProductionCalculator()
    
    result = calculator.calculate_production_cost(1, 100)
    
    if result.success:
        data = result.data
        print(f"  Jami xarajat: {format_currency(data['total_cost'])}")
        print(f"  Birlik xarajati: {format_currency(data['unit_cost'])}")
        print(f"  Material xarajati: {format_currency(data['material_cost'])}")
        if 'profit_margins' in data:
            print(f"  Foyda marjasi: {format_percentage(data['profit_margins'].get('profit_margin', 0))}")
    else:
        print(f"  Xatolik: {result.errors}")
    
    print("\n2. Ombor hisoblari:")
    inventory = [
        {'name': 'Klinker', 'quantity': 10000, 'unit_price': 500},
        {'name': 'Gips', 'quantity': 5000, 'unit_price': 300},
        {'name': 'Qum', 'quantity': 20000, 'unit_price': 50},
    ]
    
    inv_value = WarehouseCalculator.calculate_inventory_value(inventory)
    print(f"  Inventar qiymati: {format_currency(inv_value['total_value'])}")
    
    reorder = WarehouseCalculator.calculate_reorder_point(
        current_stock=800,
        daily_usage=50,
        lead_time_days=7,
        safety_stock=100
    )
    print(f"  Qayta buyurtma nuqtasi: {reorder['reorder_point']} kg")
    print(f"  Holat: {reorder['status']}")
    
    print("\n3. Moliyaviy hisoblar:")
    break_even = FinancialCalculator.calculate_break_even(
        fixed_costs=5000000,
        price_per_unit=12000,
        variable_cost_per_unit=8500
    )
    print(f"  Zararsizlik nuqtasi: {break_even['break_even_units']} birlik")
    
    roi = FinancialCalculator.calculate_roi(
        investment=10000000,
        net_profit=2500000,
        period_years=1
    )
    print(f"  ROI: {format_percentage(roi['annual_roi'])}")
    
    print("\n4. Samaradorlik hisoblari:")
    productivity = EfficiencyCalculator.calculate_productivity(
        total_output=500,
        total_hours=100,
        number_of_workers=5
    )
    print(f"  Unumdorlik: {productivity['output_per_hour']} birlik/soat")
    print(f"  Baho: {productivity['rating']}")

if __name__ == "__main__":
    main()