"""
PDF hisobotlar moduli uchun testlar
"""

import pytest
import os
from utils.pdf_reports import pdf_generator, PDF_REPORTS_DIR


class TestPDFReportGenerator:
    """PDF hisobot yaratuvchi testlari"""
    
    @pytest.fixture
    def sample_data(self):
        """Namuna ma'lumotlar"""
        return {
            "raw_materials": [
                {"name": "Klinker", "unit": "kg", "current_stock": 10000, "min_stock": 1000, "price_per_unit": 500},
                {"name": "Gips", "unit": "kg", "current_stock": 5000, "min_stock": 500, "price_per_unit": 300},
            ],
            "products": [
                {"name": "Sement M500", "unit": "qop", "selling_price": 12000, "production_cost": 7000},
                {"name": "Rodbin 12mm", "unit": "metr", "selling_price": 4500, "production_cost": 3200},
            ],
            "financial_data": {
                "total_sales_amount": 15000000,
                "production_costs": 8000000,
                "salary_costs": 3000000,
                "utility_costs": 500000,
                "other_expenses": 200000,
                "total_costs": 11700000,
                "net_profit": 3300000,
                "profit_margin": 22.0,
                "other_income": 0
            },
            "employees": [
                {"full_name": "Test Employee 1", "position": "Ishchi", "department": "Ishlab chiqarish", "salary": 2500000},
                {"full_name": "Test Employee 2", "position": "Muhandis", "department": "Ishlab chiqarish", "salary": 3500000},
            ],
            "orders": [
                {"product_name": "Sement", "quantity": 100, "total_cost": 700000, "status": "tayyor"},
            ],
            "stats": {
                "total_orders": 10,
                "completed_orders": 8,
                "total_quantity": 500,
                "total_cost": 5000000,
                "total_revenue": 7000000,
                "total_profit": 2000000
            }
        }
    
    def test_generate_warehouse_report(self, sample_data):
        """Ombor hisobotini yaratish"""
        filepath = pdf_generator.generate_warehouse_report(
            raw_materials=sample_data["raw_materials"],
            products=sample_data["products"],
            filename="test_warehouse.pdf"
        )
        
        assert os.path.exists(filepath)
        assert os.path.getsize(filepath) > 0
        
        # Tozalash
        os.remove(filepath)
    
    def test_generate_financial_report(self, sample_data):
        """Moliya hisobotini yaratish"""
        filepath = pdf_generator.generate_financial_report(
            financial_data=sample_data["financial_data"],
            period="oylik",
            filename="test_financial.pdf"
        )
        
        assert os.path.exists(filepath)
        assert os.path.getsize(filepath) > 0
        
        os.remove(filepath)
    
    def test_generate_production_report(self, sample_data):
        """Ishlab chiqarish hisobotini yaratish"""
        filepath = pdf_generator.generate_production_report(
            orders=sample_data["orders"],
            stats=sample_data["stats"],
            filename="test_production.pdf"
        )
        
        assert os.path.exists(filepath)
        assert os.path.getsize(filepath) > 0
        
        os.remove(filepath)
    
    def test_generate_employee_report(self, sample_data):
        """Xodimlar hisobotini yaratish"""
        employee_stats = {
            "avg_salary": 3000000,
            "total_salary": 6000000
        }
        
        filepath = pdf_generator.generate_employee_report(
            employees=sample_data["employees"],
            stats=employee_stats,
            filename="test_employees.pdf"
        )
        
        assert os.path.exists(filepath)
        assert os.path.getsize(filepath) > 0
        
        os.remove(filepath)
    
    def test_report_creates_valid_pdf(self, sample_data):
        """PDF faylning to'g'riligini tekshirish"""
        filepath = pdf_generator.generate_warehouse_report(
            raw_materials=sample_data["raw_materials"],
            products=sample_data["products"],
            filename="test_valid.pdf"
        )
        
        # PDF header tekshirish
        with open(filepath, 'rb') as f:
            header = f.read(5)
            assert header == b'%PDF-'
        
        os.remove(filepath)
    
    def test_auto_filename(self, sample_data):
        """Avtomatik fayl nomi"""
        filepath = pdf_generator.generate_warehouse_report(
            raw_materials=sample_data["raw_materials"],
            products=sample_data["products"]
        )
        
        assert "ombor_hisoboti_" in filepath
        assert filepath.endswith(".pdf")
        
        os.remove(filepath)


class TestPDFStyles:
    """PDF stillar testlari"""
    
    def test_custom_styles_exist(self):
        """Maxsus stillar mavjudligi"""
        assert 'CustomTitle' in pdf_generator.styles.byName
        assert 'CustomHeading' in pdf_generator.styles.byName
        assert 'CustomText' in pdf_generator.styles.byName
