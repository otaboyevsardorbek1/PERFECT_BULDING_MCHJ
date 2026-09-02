"""
Hisob-kitob modullari uchun unit testlar
"""

import pytest
from utils.calculations import (
    ProductionCalculator,
    WarehouseCalculator,
    FinancialCalculator,
    EfficiencyCalculator,
    CalculationResult,
    CostCategory,
    format_currency,
    format_percentage,
    calculate_growth_rate
)


class TestProductionCalculator:
    """Ishlab chiqarish hisob-kitoblari testlari"""
    
    def setup_method(self):
        """Test oldidan sozlash"""
        self.calculator = ProductionCalculator()
    
    def test_calculate_production_cost(self):
        """Ishlab chiqarish xarajatini hisoblash"""
        result = self.calculator.calculate_production_cost(1, 100)
        
        assert result.success == True
        assert result.data['total_cost'] > 0
        assert result.data['quantity'] == 100
        assert result.data['unit_cost'] > 0
    
    def test_calculate_production_cost_zero_quantity(self):
        """Nol miqdor bilan"""
        result = self.calculator.calculate_production_cost(1, 0)
        
        assert result.success == True
        assert result.data['quantity'] == 0
    
    def test_material_costs(self):
        """Material xarajatlari"""
        result = self.calculator.calculate_production_cost(1, 10)
        
        assert 'materials_needed' in result.data
        assert len(result.data['materials_needed']) > 0
    
    def test_additional_costs(self):
        """Qo'shimcha xarajatlar"""
        result = self.calculator.calculate_production_cost(1, 100)
        
        assert 'additional_costs' in result.data
        assert 'labor' in result.data['additional_costs']
        assert 'energy' in result.data['additional_costs']
    
    def test_profit_margins(self):
        """Foyda marjasi"""
        result = self.calculator.calculate_production_cost(1, 100)
        
        assert 'profit_margins' in result.data
        assert result.data['profit_margins']['profit_margin'] > 0


class TestWarehouseCalculator:
    """Ombor hisob-kitoblari testlari"""
    
    def test_calculate_inventory_value(self):
        """Inventar qiymatini hisoblash"""
        inventory = [
            {'name': 'Material 1', 'quantity': 100, 'unit_price': 500},
            {'name': 'Material 2', 'quantity': 200, 'unit_price': 300},
        ]
        
        result = WarehouseCalculator.calculate_inventory_value(inventory)
        
        assert result['total_value'] == 110000  # 100*500 + 200*300
        assert result['item_count'] == 2
    
    def test_calculate_inventory_value_empty(self):
        """Bo'sh inventar"""
        result = WarehouseCalculator.calculate_inventory_value([])
        
        assert result['total_value'] == 0
        assert result['item_count'] == 0
    
    def test_calculate_reorder_point(self):
        """Qayta buyurtma nuqtasini hisoblash"""
        result = WarehouseCalculator.calculate_reorder_point(
            current_stock=500,
            daily_usage=50,
            lead_time_days=7,
            safety_stock=100
        )
        
        assert result['reorder_point'] == 450  # 50*7 + 100
        assert result['days_remaining'] == 10.0  # 500/50
    
    def test_calculate_reorder_point_critical(self):
        """Favqulodda holat"""
        result = WarehouseCalculator.calculate_reorder_point(
            current_stock=50,
            daily_usage=50,
            lead_time_days=7,
            safety_stock=100
        )
        
        assert result['status'] == 'critical'
    
    def test_calculate_inventory_turnover(self):
        """Inventar aylanishini hisoblash"""
        result = WarehouseCalculator.calculate_inventory_turnover(
            sales_value=1000000,
            average_inventory_value=200000
        )
        
        assert result['turnover_ratio'] == 5.0
        assert result['days_in_inventory'] == 73.0


class TestFinancialCalculator:
    """Moliyaviy hisob-kitoblar testlari"""
    
    def test_calculate_break_even(self):
        """Zararsizlik nuqtasini hisoblash"""
        result = FinancialCalculator.calculate_break_even(
            fixed_costs=5000000,
            price_per_unit=12000,
            variable_cost_per_unit=8000
        )
        
        assert result['break_even_units'] == 1250  # 5000000 / (12000-8000)
        assert result['contribution_margin'] == 4000
        assert result['is_feasible'] == True
    
    def test_calculate_break_even_not_feasible(self):
        """Noto'g'ri narx"""
        result = FinancialCalculator.calculate_break_even(
            fixed_costs=5000000,
            price_per_unit=5000,
            variable_cost_per_unit=8000
        )
        
        assert result['is_feasible'] == False
    
    def test_calculate_roi(self):
        """ROI hisoblash"""
        result = FinancialCalculator.calculate_roi(
            investment=10000000,
            net_profit=2500000,
            period_years=1
        )
        
        assert result['roi_percentage'] == 25.0
        assert result['annual_roi'] == 25.0
        assert result['is_profitable'] == True
    
    def test_calculate_depreciation_straight_line(self):
        """To'g'ri chiziqli amortizatsiya"""
        result = FinancialCalculator.calculate_depreciation(
            asset_value=10000000,
            salvage_value=1000000,
            useful_life_years=10,
            method='straight_line'
        )
        
        assert result['annual_depreciation'] == 900000  # (10M - 1M) / 10
        assert result['total_depreciation'] == 9000000


class TestEfficiencyCalculator:
    """Samaradorlik hisob-kitoblari testlari"""
    
    def test_calculate_productivity(self):
        """Mehnat unumdorligini hisoblash"""
        result = EfficiencyCalculator.calculate_productivity(
            total_output=500,
            total_hours=100,
            number_of_workers=5
        )
        
        assert result['output_per_hour'] == 5.0  # 500/100
        assert result['output_per_worker_hour'] == 1.0  # 500/(100*5)
        assert result['efficiency_score'] == 50.0  # (5/10)*100
    
    def test_calculate_productivity_excellent(self):
        """Ajoyib unumdorlik"""
        result = EfficiencyCalculator.calculate_productivity(
            total_output=1000,
            total_hours=100,
            number_of_workers=1
        )
        
        assert result['rating'] == 'excellent'
    
    def test_calculate_equipment_utilization(self):
        """Uskuna foydalanish koeffitsienti"""
        result = EfficiencyCalculator.calculate_equipment_utilization(
            actual_hours=160,
            available_hours=200
        )
        
        assert result['utilization_rate'] == 80.0
        assert result['status'] == 'optimal'


class TestHelperFunctions:
    """Yordamchi funksiyalar testlari"""
    
    def test_format_currency(self):
        """Pulni formatlash"""
        result = format_currency(1500000)
        assert "1,500,000" in result or "so'm" in result
    
    def test_format_currency_none(self):
        """None qiymat"""
        result = format_currency(None)
        assert "0" in result
    
    def test_format_percentage(self):
        """Foizni formatlash"""
        result = format_percentage(25.5)
        assert "25.5%" in result
    
    def test_calculate_growth_rate(self):
        """O'sish sur'atini hisoblash"""
        result = calculate_growth_rate(150, 100)
        assert result == 50.0  # (150-100)/100 * 100
    
    def test_calculate_growth_rate_zero(self):
        """Nol o'sish"""
        result = calculate_growth_rate(100, 100)
        assert result == 0.0


class TestCalculationResult:
    """CalculationResult testlari"""
    
    def test_to_dict(self):
        """Dictionary formatga o'tkazish"""
        result = CalculationResult(
            success=True,
            data={'test': 'value'},
            warnings=['warning1'],
            errors=[]
        )
        
        d = result.to_dict()
        assert d['success'] == True
        assert d['data']['test'] == 'value'
        assert len(d['warnings']) == 1
