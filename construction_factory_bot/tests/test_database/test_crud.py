"""
Database CRUD operatsiyalari uchun testlar
"""

import pytest
from datetime import datetime, date, timedelta
from database import models, crud
from database.session import get_db_session


class TestRawMaterialCRUD:
    """Xom ashyo CRUD testlari"""
    
    def test_create_raw_material(self, db_session):
        """Xom ashyo yaratish"""
        material_data = {
            "name": "Test Material",
            "category": "Test",
            "unit": "kg",
            "current_stock": 1000,
            "min_stock": 100,
            "price_per_unit": 500,
            "supplier": "Test Supplier"
        }
        
        material = crud.create_raw_material(db_session, material_data)
        
        assert material.id is not None
        assert material.name == "Test Material"
        assert material.current_stock == 1000
    
    def test_get_raw_material(self, db_session):
        """Xom ashyoni olish"""
        # Yaratish
        material_data = {
            "name": "Get Test Material",
            "unit": "kg",
            "current_stock": 500,
            "price_per_unit": 300
        }
        created = crud.create_raw_material(db_session, material_data)
        
        # Olish
        retrieved = crud.get_raw_material(db_session, created.id)
        
        assert retrieved is not None
        assert retrieved.name == "Get Test Material"
    
    def test_update_raw_material(self, db_session):
        """Xom ashyoni yangilash"""
        # Yaratish
        material_data = {
            "name": "Update Test Material",
            "unit": "kg",
            "current_stock": 500,
            "price_per_unit": 300
        }
        created = crud.create_raw_material(db_session, material_data)
        
        # Yangilash
        update_data = {"current_stock": 1000, "price_per_unit": 350}
        updated = crud.update_raw_material(db_session, created.id, update_data)
        
        assert updated.current_stock == 1000
        assert updated.price_per_unit == 350
    
    def test_delete_raw_material(self, db_session):
        """Xom ashyoni o'chirish"""
        # Yaratish
        material_data = {
            "name": "Delete Test Material",
            "unit": "kg",
            "current_stock": 500,
            "price_per_unit": 300
        }
        created = crud.create_raw_material(db_session, material_data)
        
        # O'chirish
        result = crud.delete_raw_material(db_session, created.id)
        
        assert result == True
        assert crud.get_raw_material(db_session, created.id) is None
    
    def test_check_low_stock_materials(self, db_session):
        """Kam qoldiq materiallarni tekshirish"""
        # Yaratish
        material_data = {
            "name": "Low Stock Material",
            "unit": "kg",
            "current_stock": 50,  # Min 100 dan kam
            "min_stock": 100,
            "price_per_unit": 300
        }
        crud.create_raw_material(db_session, material_data)
        
        # Tekshirish
        low_stock = crud.check_low_stock_materials(db_session)
        
        assert len(low_stock) > 0


class TestProductCRUD:
    """Mahsulot CRUD testlari"""
    
    def test_create_product(self, db_session):
        """Mahsulot yaratish"""
        product_data = {
            "name": "Test Product",
            "category": "test",
            "unit": "dona",
            "selling_price": 10000,
            "production_cost": 7000,
            "profit_margin": 0.3,
            "is_active": True
        }
        
        product = crud.create_product(db_session, product_data)
        
        assert product.id is not None
        assert product.name == "Test Product"
        assert product.selling_price == 10000
    
    def test_get_product(self, db_session):
        """Mahsulotni olish"""
        product_data = {
            "name": "Get Test Product",
            "category": "test",
            "unit": "dona",
            "selling_price": 10000,
            "production_cost": 7000,
            "is_active": True
        }
        created = crud.create_product(db_session, product_data)
        
        retrieved = crud.get_product(db_session, created.id)
        
        assert retrieved is not None
        assert retrieved.name == "Get Test Product"
    
    def test_get_products_by_category(self, db_session):
        """Kategoriya bo'yicha mahsulotlar"""
        # Yaratish
        for i in range(3):
            product_data = {
                "name": f"Category Test Product {i}",
                "category": "test_category",
                "unit": "dona",
                "selling_price": 10000,
                "production_cost": 7000,
                "is_active": True
            }
            crud.create_product(db_session, product_data)
        
        # Olish
        products = crud.get_products_by_category(db_session, "test_category")
        
        assert len(products) == 3


class TestEmployeeCRUD:
    """Xodimlar CRUD testlari"""
    
    def test_create_employee(self, db_session):
        """Xodim yaratish"""
        employee_data = {
            "full_name": "Test Employee",
            "phone_number": "+998901234567",
            "position": "Ishchi",
            "department": "Ishlab chiqarish",
            "status": models.EmployeeStatus.ACTIVE,
            "hire_date": datetime.now(),
            "salary": 2500000
        }
        
        employee = crud.create_employee(db_session, employee_data)
        
        assert employee.id is not None
        assert employee.full_name == "Test Employee"
        assert employee.salary == 2500000
    
    def test_get_employee_by_telegram_id(self, db_session):
        """Telegram ID bo'yicha xodim"""
        employee_data = {
            "full_name": "Telegram Test Employee",
            "phone_number": "+998901234567",
            "position": "Ishchi",
            "department": "Ishlab chiqarish",
            "status": models.EmployeeStatus.ACTIVE,
            "hire_date": datetime.now(),
            "telegram_id": 123456789,
            "salary": 2500000
        }
        crud.create_employee(db_session, employee_data)
        
        employee = crud.get_employee_by_telegram_id(db_session, 123456789)
        
        assert employee is not None
        assert employee.full_name == "Telegram Test Employee"


class TestWorkHoursCRUD:
    """Ish vaqtlari CRUD testlari"""
    
    def test_add_work_hours(self, db_session):
        """Ish vaqtini qo'shish"""
        # Avval xodim yaratish
        employee_data = {
            "full_name": "Work Hours Test Employee",
            "phone_number": "+998901234567",
            "position": "Ishchi",
            "department": "Ishlab chiqarish",
            "status": models.EmployeeStatus.ACTIVE,
            "hire_date": datetime.now(),
            "salary": 2500000
        }
        employee = crud.create_employee(db_session, employee_data)
        
        # Ish vaqtini qo'shish
        work_data = {
            "employee_id": employee.id,
            "date": datetime.now(),
            "start_time": datetime.now().replace(hour=8),
            "end_time": datetime.now().replace(hour=17),
            "hours_worked": 8,
            "overtime_hours": 1
        }
        
        work_hours = crud.add_work_hours(db_session, work_data)
        
        assert work_hours.id is not None
        assert work_hours.hours_worked == 8


class TestStatistics:
    """Statistika testlari"""
    
    def test_warehouse_statistics(self, db_session):
        """Ombor statistikasi"""
        # Material qo'shish
        material_data = {
            "name": "Stats Test Material",
            "unit": "kg",
            "current_stock": 1000,
            "min_stock": 100,
            "price_per_unit": 500
        }
        crud.create_raw_material(db_session, material_data)
        
        stats = crud.get_warehouse_statistics(db_session)
        
        assert 'total_raw_materials_value' in stats
        assert 'low_stock_materials_count' in stats
        assert stats['total_materials_count'] > 0
    
    def test_financial_statistics(self, db_session):
        """Moliya statistikasi"""
        stats = crud.get_financial_statistics(
            db_session,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today()
        )
        
        assert 'total_sales_amount' in stats
        assert 'production_costs' in stats
        assert 'net_profit' in stats
