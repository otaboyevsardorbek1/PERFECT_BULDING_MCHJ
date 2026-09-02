"""
PDF Hisobot Testi - Namuna PDF yaratish va sinash
"""

import sys
import os

# Loyiha yo'llarini qo'shish
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.pdf_reports import pdf_generator

# Namuna ma'lumotlar
sample_raw_materials = [
    {"name": "Klinker", "unit": "kg", "current_stock": 10000, "min_stock": 1000, "price_per_unit": 500},
    {"name": "Gips", "unit": "kg", "current_stock": 5000, "min_stock": 500, "price_per_unit": 300},
    {"name": "Qum", "unit": "kg", "current_stock": 20000, "min_stock": 2000, "price_per_unit": 50},
    {"name": "Temir sutka", "unit": "kg", "current_stock": 8000, "min_stock": 800, "price_per_unit": 2000},
    {"name": "Gil", "unit": "kg", "current_stock": 10000, "min_stock": 1000, "price_per_unit": 150},
]

sample_products = [
    {"name": "Sement M500 (50kg)", "unit": "qop", "selling_price": 12000, "production_cost": 7000},
    {"name": "Rodbin 12mm", "unit": "metr", "selling_price": 4500, "production_cost": 3200},
    {"name": "Kafel 30x30", "unit": "dona", "selling_price": 850, "production_cost": 450},
    {"name": "Nalinoy pol", "unit": "m2", "selling_price": 2800, "production_cost": 1800},
]

sample_financial_data = {
    "total_sales_amount": 15000000,
    "production_costs": 8000000,
    "salary_costs": 3000000,
    "utility_costs": 500000,
    "other_expenses": 200000,
    "total_costs": 11700000,
    "net_profit": 3300000,
    "profit_margin": 22.0,
    "other_income": 0
}

sample_employees = [
    {"full_name": "Azizov Sardor", "position": "Direktor", "department": "Rahbariyat", "salary": 5000000},
    {"full_name": "Karimov Jasur", "position": "Muhandis", "department": "Ishlab chiqarish", "salary": 3500000},
    {"full_name": "Toshmatov Akbar", "position": "Ishchi", "department": "Ishlab chiqarish", "salary": 2500000},
    {"full_name": "Rahimova Nilufar", "position": "Buxgalter", "department": "Buxgalteriya", "salary": 3000000},
]

sample_orders = [
    {"product_name": "Sement M500 (50kg)", "quantity": 500, "total_cost": 3500000, "status": "tayyor"},
    {"product_name": "Rodbin 12mm", "quantity": 1000, "total_cost": 3200000, "status": "jarayonda"},
    {"product_name": "Kafel 30x30", "quantity": 2000, "total_cost": 900000, "status": "tayyor"},
]

sample_stats = {
    "total_orders": 15,
    "completed_orders": 12,
    "total_quantity": 5000,
    "total_cost": 25000000,
    "total_revenue": 35000000,
    "total_profit": 10000000
}


def test_warehouse_report():
    """Ombor hisobotini sinash"""
    print("📦 Ombor hisoboti yaratilmoqda...")
    
    filepath = pdf_generator.generate_warehouse_report(
        raw_materials=sample_raw_materials,
        products=sample_products,
        filename="test_ombor_hisoboti.pdf"
    )
    
    print(f"✅ Ombor hisoboti yaratildi: {filepath}")
    print(f"   Hajm: {os.path.getsize(filepath) / 1024:.1f} KB")
    
    return filepath


def test_financial_report():
    """Moliya hisobotini sinash"""
    print("\n💰 Moliya hisoboti yaratilmoqda...")
    
    filepath = pdf_generator.generate_financial_report(
        financial_data=sample_financial_data,
        period="oylik",
        filename="test_moliya_hisoboti.pdf"
    )
    
    print(f"✅ Moliya hisoboti yaratildi: {filepath}")
    print(f"   Hajm: {os.path.getsize(filepath) / 1024:.1f} KB")
    
    return filepath


def test_production_report():
    """Ishlab chiqarish hisobotini sinash"""
    print("\n🏭 Ishlab chiqarish hisoboti yaratilmoqda...")
    
    filepath = pdf_generator.generate_production_report(
        orders=sample_orders,
        stats=sample_stats,
        filename="test_ishlab_chiqarish_hisoboti.pdf"
    )
    
    print(f"✅ Ishlab chiqarish hisoboti yaratildi: {filepath}")
    print(f"   Hajm: {os.path.getsize(filepath) / 1024:.1f} KB")
    
    return filepath


def test_employee_report():
    """Xodimlar hisobotini sinash"""
    print("\n👥 Xodimlar hisoboti yaratilmoqda...")
    
    employee_stats = {
        "avg_salary": sum(e["salary"] for e in sample_employees) / len(sample_employees),
        "total_salary": sum(e["salary"] for e in sample_employees)
    }
    
    filepath = pdf_generator.generate_employee_report(
        employees=sample_employees,
        stats=employee_stats,
        filename="test_xodimlar_hisoboti.pdf"
    )
    
    print(f"✅ Xodimlar hisoboti yaratildi: {filepath}")
    print(f"   Hajm: {os.path.getsize(filepath) / 1024:.1f} KB")
    
    return filepath


def main():
    """Asosiy test funksiyasi"""
    
    print("=" * 50)
    print("📄 PDF HISOBOT TESTI")
    print("=" * 50)
    
    try:
        # Barcha hisobotlarni yaratish
        files = []
        
        files.append(test_warehouse_report())
        files.append(test_financial_report())
        files.append(test_production_report())
        files.append(test_employee_report())
        
        # Natijalar
        print("\n" + "=" * 50)
        print("✅ BARCHA TESTLAR MUVAFFAQIYATLI!")
        print("=" * 50)
        
        print(f"\n📁 Yaratilgan fayllar ({len(files)} ta):")
        for f in files:
            print(f"   📄 {f}")
        
        print(f"\n📂 Papka: construction_factory_bot/reports/pdf/")
        
        return True
        
    except Exception as e:
        print(f"\n❌ XATOLIK: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
