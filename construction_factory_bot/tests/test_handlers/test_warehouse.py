"""
Warehouse handler testlari - SQLAlchemy bilan refactored versiya
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from database import models
from database.crud import (
    create_raw_material, get_raw_material, update_raw_material,
    delete_raw_material, check_low_stock_materials, get_warehouse_statistics
)


class TestWarehouseStatusQuery:
    """Ombor holati so'rovlarini test qilish"""

    def test_warehouse_status_query_returns_all_materials(self, db_session):
        """Barcha materiallarni olish"""
        # Materiallar qo'shish
        for i in range(3):
            create_raw_material(db_session, {
                "name": f"Material {i}",
                "unit": "kg",
                "current_stock": 1000 * (i + 1),
                "min_stock": 100,
                "price_per_unit": 50 * (i + 1)
            })

        materials = db_session.query(models.RawMaterial).order_by(
            models.RawMaterial.name
        ).all()

        assert len(materials) == 3

    def test_warehouse_status_filters_low_stock(self, db_session):
        """Kam qoldiq materiallarni aniqlash"""
        # Yetarli material
        create_raw_material(db_session, {
            "name": "Enough Material",
            "unit": "kg",
            "current_stock": 5000,
            "min_stock": 100,
            "price_per_unit": 100
        })

        # Kam qoldiq material
        create_raw_material(db_session, {
            "name": "Low Material",
            "unit": "kg",
            "current_stock": 50,
            "min_stock": 100,
            "price_per_unit": 200
        })

        low_stock = check_low_stock_materials(db_session)

        assert len(low_stock) == 1
        assert low_stock[0].name == "Low Material"

    def test_warehouse_status_product_stock_calculation(self, db_session):
        """Mahsulot zaxirasini hisoblash (ishlab chiqarilgan - sotilgan)"""
        # Mahsulot yaratish
        product = models.Product(
            name="Test Cement",
            category="sement",
            unit="qop",
            selling_price=12000,
            production_cost=7000,
            is_active=True
        )
        db_session.add(product)
        db_session.flush()

        # Ishlab chiqarish (kirim)
        prod_txn = models.WarehouseTransaction(
            product_id=product.id,
            quantity=100,
            transaction_type=models.TransactionType.PRODUCTION,
            user_id=123
        )
        db_session.add(prod_txn)

        # Sotish (chiqim)
        sale_txn = models.WarehouseTransaction(
            product_id=product.id,
            quantity=30,
            transaction_type=models.TransactionType.SALE,
            user_id=123
        )
        db_session.add(sale_txn)
        db_session.commit()

        # Hisoblash
        produced = db_session.query(
            func.coalesce(func.sum(models.WarehouseTransaction.quantity), 0)
        ).filter(
            models.WarehouseTransaction.product_id == product.id,
            models.WarehouseTransaction.transaction_type == models.TransactionType.PRODUCTION
        ).scalar()

        sold = db_session.query(
            func.coalesce(func.sum(models.WarehouseTransaction.quantity), 0)
        ).filter(
            models.WarehouseTransaction.product_id == product.id,
            models.WarehouseTransaction.transaction_type == models.TransactionType.SALE
        ).scalar()

        assert produced == 100
        assert sold == 30
        assert produced - sold == 70

    def test_warehouse_status_material_value_calculation(self, db_session):
        """Material qiymatini hisoblash (miqdor * narx)"""
        create_raw_material(db_session, {
            "name": "Klinker",
            "unit": "kg",
            "current_stock": 10000,
            "min_stock": 1000,
            "price_per_unit": 500
        })

        create_raw_material(db_session, {
            "name": "Gips",
            "unit": "kg",
            "current_stock": 5000,
            "min_stock": 500,
            "price_per_unit": 300
        })

        stats = get_warehouse_statistics(db_session)

        expected_value = (10000 * 500) + (5000 * 300)
        assert stats["total_raw_materials_value"] == expected_value

    def test_warehouse_status_counts_materials(self, db_session):
        """Materiallar sonini hisoblash"""
        for i in range(5):
            create_raw_material(db_session, {
                "name": f"Count Material {i}",
                "unit": "kg",
                "current_stock": 100,
                "min_stock": 10,
                "price_per_unit": 10
            })

        stats = get_warehouse_statistics(db_session)

        assert stats["total_materials_count"] == 5


class TestWarehouseMaterialAdd:
    """Xom ashyo qo'shish testlari"""

    def test_add_material_via_sqlalchemy(self, db_session):
        """SQLAlchemy orqali yangi material qo'shish"""
        new_material = models.RawMaterial(
            name="New Material",
            unit="dona",
            current_stock=500,
            price_per_unit=200
        )
        db_session.add(new_material)
        db_session.commit()

        retrieved = db_session.query(models.RawMaterial).filter(
            models.RawMaterial.name == "New Material"
        ).first()

        assert retrieved is not None
        assert retrieved.unit == "dona"
        assert retrieved.current_stock == 500

    def test_add_material_duplicate_name_fails(self, db_session):
        """Bir xil nomli material qo'shish - UNIQUE xatolik"""
        material1 = models.RawMaterial(
            name="Duplicate Material",
            unit="kg",
            current_stock=100,
            price_per_unit=50
        )
        db_session.add(material1)
        db_session.commit()

        material2 = models.RawMaterial(
            name="Duplicate Material",
            unit="dona",
            current_stock=200,
            price_per_unit=100
        )
        db_session.add(material2)

        with pytest.raises(Exception):
            db_session.commit()

        db_session.rollback()

    def test_add_material_with_category(self, db_session):
        """Kategoriya bilan material qo'shish"""
        material = models.RawMaterial(
            name="Categorized Material",
            category="Metall",
            unit="kg",
            current_stock=1000,
            price_per_unit=2000,
            supplier="Test Supplier"
        )
        db_session.add(material)
        db_session.commit()

        retrieved = db_session.query(models.RawMaterial).filter(
            models.RawMaterial.name == "Categorized Material"
        ).first()

        assert retrieved.category == "Metall"
        assert retrieved.supplier == "Test Supplier"

    def test_material_stock_update(self, db_session):
        """Material zaxirasini yangilash"""
        material = create_raw_material(db_session, {
            "name": "Update Stock Material",
            "unit": "kg",
            "current_stock": 1000,
            "price_per_unit": 100
        })

        material.current_stock -= 300
        db_session.commit()

        updated = db_session.query(models.RawMaterial).filter(
            models.RawMaterial.id == material.id
        ).first()

        assert updated.current_stock == 700


class TestWarehouseTransactions:
    """Ombor tranzaksiyalari testlari"""

    def test_create_production_transaction(self, db_session):
        """Ishlab chiqarish tranzaksiyasini yaratish"""
        product = models.Product(
            name="Transaction Test Product",
            category="sement",
            unit="qop",
            selling_price=12000,
            production_cost=7000,
            is_active=True
        )
        db_session.add(product)
        db_session.flush()

        material = models.RawMaterial(
            name="Transaction Test Material",
            unit="kg",
            current_stock=10000,
            price_per_unit=500
        )
        db_session.add(material)
        db_session.flush()

        transaction = models.WarehouseTransaction(
            product_id=product.id,
            raw_material_id=material.id,
            quantity=500,
            transaction_type=models.TransactionType.PRODUCTION,
            user_id=123,
            user_name="Test User",
            notes="Test tranzaksiya"
        )
        db_session.add(transaction)
        db_session.commit()

        retrieved = db_session.query(models.WarehouseTransaction).first()
        assert retrieved is not None
        assert retrieved.quantity == 500
        assert retrieved.transaction_type == models.TransactionType.PRODUCTION

    def test_production_decreases_raw_material_stock(self, db_session):
        """Ishlab chiqarish xom ashyo zaxirasini kamaytirish"""
        material = models.RawMaterial(
            name="Stock Decrease Material",
            unit="kg",
            current_stock=10000,
            price_per_unit=500
        )
        db_session.add(material)
        db_session.flush()

        required_quantity = 2000
        material.current_stock -= required_quantity
        db_session.commit()

        updated = db_session.query(models.RawMaterial).filter(
            models.RawMaterial.id == material.id
        ).first()

        assert updated.current_stock == 8000


class TestWarehouseStatistics:
    """Ombor statistikasi testlari"""

    def test_statistics_with_empty_database(self, db_session):
        """Bo'sh database uchun statistika"""
        stats = get_warehouse_statistics(db_session)

        assert stats["total_raw_materials_value"] == 0
        assert stats["total_materials_count"] == 0
        assert stats["low_stock_materials_count"] == 0

    def test_statistics_with_multiple_materials(self, db_session):
        """Ko'p materiallar bilan statistika"""
        materials_data = [
            {"name": "Mat A", "unit": "kg", "current_stock": 1000, "min_stock": 100, "price_per_unit": 100},
            {"name": "Mat B", "unit": "kg", "current_stock": 2000, "min_stock": 200, "price_per_unit": 200},
            {"name": "Mat C", "unit": "dona", "current_stock": 500, "min_stock": 50, "price_per_unit": 500},
        ]

        for data in materials_data:
            create_raw_material(db_session, data)

        stats = get_warehouse_statistics(db_session)

        expected_value = (1000 * 100) + (2000 * 200) + (500 * 500)
        assert stats["total_raw_materials_value"] == expected_value
        assert stats["total_materials_count"] == 3

    def test_statistics_low_stock_count(self, db_session):
        """Kam qoldiq materiallar soni"""
        # Yetarli
        create_raw_material(db_session, {
            "name": "OK Material",
            "unit": "kg",
            "current_stock": 5000,
            "min_stock": 100,
            "price_per_unit": 100
        })

        # Kam qoldiq
        create_raw_material(db_session, {
            "name": "Low Stock 1",
            "unit": "kg",
            "current_stock": 50,
            "min_stock": 100,
            "price_per_unit": 200
        })

        # Juda kam
        create_raw_material(db_session, {
            "name": "Low Stock 2",
            "unit": "kg",
            "current_stock": 10,
            "min_stock": 100,
            "price_per_unit": 300
        })

        stats = get_warehouse_statistics(db_session)

        assert stats["low_stock_materials_count"] == 2

    def test_statistics_products_count(self, db_session):
        """Mahsulotlar soni"""
        for i in range(3):
            product = models.Product(
                name=f"Stats Product {i}",
                category="sement",
                unit="qop",
                selling_price=10000,
                production_cost=7000,
                is_active=True
            )
            db_session.add(product)

        # Faol emas mahsulot
        inactive = models.Product(
            name="Inactive Product",
            category="test",
            unit="dona",
            selling_price=5000,
            production_cost=3000,
            is_active=False
        )
        db_session.add(inactive)
        db_session.commit()

        stats = get_warehouse_statistics(db_session)

        assert stats["total_products_count"] == 3
