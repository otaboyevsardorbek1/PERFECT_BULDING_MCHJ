"""
Formulalar moduli uchun unit testlar
"""

import pytest
from utils.formulas import (
    FormulaManager,
    ProductCategory,
    MaterialRequirement,
    ProductionCalculation
)


class TestFormulaManager:
    """FormulaManager testlari"""
    
    def setup_method(self):
        """Test oldidan sozlash"""
        self.manager = FormulaManager()
    
    def test_standard_formulas_exist(self):
        """Standart formulalar mavjudligi"""
        assert "Sement M500" in self.manager.STANDARD_FORMULAS
        assert "Rodbin 12mm" in self.manager.STANDARD_FORMULAS
        assert "Kafel 30x30" in self.manager.STANDARD_FORMULAS
        assert "Nalinoy pol" in self.manager.STANDARD_FORMULAS
    
    def test_material_prices_exist(self):
        """Material narxlari mavjudligi"""
        assert "Klinker" in self.manager.DEFAULT_MATERIAL_PRICES
        assert "Gips" in self.manager.DEFAULT_MATERIAL_PRICES
        assert "Temir sutka" in self.manager.DEFAULT_MATERIAL_PRICES
    
    def test_calculate_production_cost_cement(self):
        """Sement ishlab chiqarish xarajati"""
        result = self.manager.calculate_production_cost("Sement M500", 100)
        
        assert result.product_name == "Sement M500"
        assert result.quantity == 100
        assert result.total_cost > 0
        assert result.unit_cost > 0
    
    def test_calculate_production_cost_rebar(self):
        """Rodbin ishlab chiqarish xarajati"""
        result = self.manager.calculate_production_cost("Rodbin 12mm", 50)
        
        assert result.product_name == "Rodbin 12mm"
        assert result.quantity == 50
        assert result.total_cost > 0
    
    def test_calculate_production_cost_tile(self):
        """Kafel ishlab chiqarish xarajati"""
        result = self.manager.calculate_production_cost("Kafel 30x30", 200)
        
        assert result.product_name == "Kafel 30x30"
        assert result.quantity == 200
    
    def test_custom_prices(self):
        """Maxsus narxlar bilan"""
        custom_prices = {"Klinker": 600, "Gips": 350}
        
        result = self.manager.calculate_production_cost(
            "Sement M500", 100, custom_prices=custom_prices
        )
        
        assert result.total_cost > 0
    
    def test_labor_multiplier(self):
        """Mehnat ko'paytirgichi"""
        result1 = self.manager.calculate_production_cost("Sement M500", 100, labor_multiplier=1.0)
        result2 = self.manager.calculate_production_cost("Sement M500", 100, labor_multiplier=1.5)
        
        assert result2.labor_cost > result1.labor_cost
    
    def test_energy_multiplier(self):
        """Energiya ko'paytirgichi"""
        result1 = self.manager.calculate_production_cost("Sement M500", 100, energy_multiplier=1.0)
        result2 = self.manager.calculate_production_cost("Sement M500", 100, energy_multiplier=2.0)
        
        assert result2.energy_cost > result1.energy_cost
    
    def test_invalid_product(self):
        """Noto'g'ri mahsulot"""
        with pytest.raises(ValueError):
            self.manager.calculate_production_cost("Noto'g'ri mahsulot", 100)
    
    def test_material_requirements(self):
        """Material talablari"""
        result = self.manager.calculate_production_cost("Sement M500", 100)
        
        assert len(result.materials) > 0
        for material in result.materials:
            assert material.unit_price > 0
    
    def test_profit_calculation(self):
        """Foyda hisobi"""
        result = self.manager.calculate_production_cost("Sement M500", 100)
        
        assert result.selling_price > result.unit_cost
        assert result.profit_per_unit > 0
        assert result.total_profit > 0


class TestMaterialRequirement:
    """MaterialRequirement testlari"""
    
    def test_to_dict(self):
        """Dictionary formatga o'tkazish"""
        req = MaterialRequirement(
            material_id=1,
            material_name="Test",
            quantity=100,
            unit="kg",
            unit_price=500,
            total_cost=50000
        )
        
        d = req.to_dict()
        assert d['material_id'] == 1
        assert d['material_name'] == "Test"
        assert d['quantity'] == 100


class TestProductionCalculation:
    """ProductionCalculation testlari"""
    
    def test_to_dict(self):
        """Dictionary formatga o'tkazish"""
        calc = ProductionCalculation(
            product_id=1,
            product_name="Test",
            quantity=100,
            material_cost=50000,
            labor_cost=10000,
            energy_cost=5000,
            overhead_cost=5000,
            total_cost=70000,
            unit_cost=700,
            selling_price=1000,
            profit_per_unit=300,
            total_profit=30000,
            materials=[],
            can_produce=True,
            missing_materials=[]
        )
        
        d = calc.to_dict()
        assert d['product_id'] == 1
        assert d['total_cost'] == 70000
        assert d['can_produce'] == True


class TestProductCategory:
    """ProductCategory enum testlari"""
    
    def test_categories(self):
        """Kategoriyalar"""
        assert ProductCategory.CEMENT.value == "sement"
        assert ProductCategory.REBAR.value == "armatura"
        assert ProductCategory.TILE.value == "kafel"
        assert ProductCategory.FLOORING.value == "pol"
        assert ProductCategory.GYPSUM.value == "gips"
        assert ProductCategory.CONCRETE.value == "beton"
