"""
Production handler testlari - SQLAlchemy bilan refactored versiya
"""

import pytest
from datetime import datetime
from sqlalchemy import func, extract

from database import models
from database.crud import (
    get_warehouse_statistics, get_production_statistics
)
from database.models import (
    OrderStatus, TransactionType, EmployeeStatus
)


@pytest.fixture
def setup_production_data(db_session):
    """Ishlab chiqarish uchun boshlang'ich ma'lumotlar"""
    # Mahsulotlar
    products = []
    product_data = [
        ("Cement M500", "sement", "qop", 12000, 7000),
        ("Rodbin 12mm", "rodbin", "metr", 4500, 3200),
        ("Kafel 30x30", "kafel", "dona", 850, 450),
    ]

    for name, cat, unit, price, cost in product_data:
        product = models.Product(
            name=name, category=cat, unit=unit,
            selling_price=price, production_cost=cost,
            is_active=True
        )
        db_session.add(product)
        products.append(product)

    db_session.flush()

    # Xom ashyolar
    materials = []
    material_data = [
        ("Klinker", "kg", 10000, 1000, 500),
        ("Gips", "kg", 5000, 500, 300),
        ("Qum", "kg", 20000, 2000, 50),
    ]

    for name, unit, stock, min_stock, price in material_data:
        mat = models.RawMaterial(
            name=name, unit=unit, current_stock=stock,
            min_stock=min_stock, price_per_unit=price
        )
        db_session.add(mat)
        materials.append(mat)

    db_session.flush()

    # Formulalar (Cement uchun: 45kg Klinker + 5kg Gips)
    formulas = [
        models.ProductFormula(
            product_id=products[0].id,
            raw_material_id=materials[0].id,
            quantity=45,
            waste_percentage=0.05
        ),
        models.ProductFormula(
            product_id=products[0].id,
            raw_material_id=materials[1].id,
            quantity=5,
            waste_percentage=0.05
        ),
    ]

    for formula in formulas:
        db_session.add(formula)

    db_session.commit()

    return {
        "products": products,
        "materials": materials,
        "formulas": formulas
    }


class TestProductionFormulaQuery:
    """Mahsulot formulalari so'rovlarini test qilish"""

    def test_formula_query_returns_materials(self, db_session, setup_production_data):
        """Formula so'rovi materiallarni qaytaradi"""
        product_id = setup_production_data["products"][0].id

        formula_items = db_session.query(
            models.RawMaterial.name,
            models.RawMaterial.current_stock,
            models.ProductFormula.quantity.label('required_per_unit'),
            models.RawMaterial.price_per_unit,
            models.RawMaterial.id.label('material_id')
        ).join(
            models.RawMaterial,
            models.ProductFormula.raw_material_id == models.RawMaterial.id
        ).filter(
            models.ProductFormula.product_id == product_id
        ).all()

        assert len(formula_items) == 2

        names = [item.name for item in formula_items]
        assert "Klinker" in names
        assert "Gips" in names

    def test_formula_quantities_correct(self, db_session, setup_production_data):
        """Formula miqdorlari to'g'ri"""
        product_id = setup_production_data["products"][0].id

        formula_items = db_session.query(
            models.ProductFormula.quantity,
            models.RawMaterial.name
        ).join(
            models.RawMaterial,
            models.ProductFormula.raw_material_id == models.RawMaterial.id
        ).filter(
            models.ProductFormula.product_id == product_id
        ).all()

        quantities = {item.name: item.quantity for item in formula_items}

        assert quantities["Klinker"] == 45
        assert quantities["Gips"] == 5

    def test_formula_material_stock_sufficient(self, db_session, setup_production_data):
        """Formula uchun material yetarli"""
        product_id = setup_production_data["products"][0].id
        quantity = 100  # 100 birlik ishlab chiqarish

        formula_items = db_session.query(
            models.RawMaterial.name,
            models.RawMaterial.current_stock,
            models.ProductFormula.quantity.label('required_per_unit')
        ).join(
            models.RawMaterial,
            models.ProductFormula.raw_material_id == models.RawMaterial.id
        ).filter(
            models.ProductFormula.product_id == product_id
        ).all()

        can_produce = True
        for item in formula_items:
            required_total = item.required_per_unit * quantity
            if item.current_stock < required_total:
                can_produce = False
                break

        assert can_produce is True

    def test_formula_material_insufficient(self, db_session, setup_production_data):
        """Formula uchun material yetarli emas"""
        product_id = setup_production_data["products"][0].id
        quantity = 1000  # 1000 birlik - yetarli emas

        formula_items = db_session.query(
            models.RawMaterial.name,
            models.RawMaterial.current_stock,
            models.ProductFormula.quantity.label('required_per_unit')
        ).join(
            models.RawMaterial,
            models.ProductFormula.raw_material_id == models.RawMaterial.id
        ).filter(
            models.ProductFormula.product_id == product_id
        ).all()

        can_produce = True
        missing = []
        for item in formula_items:
            required_total = item.required_per_unit * quantity
            if item.current_stock < required_total:
                can_produce = False
                missing.append({
                    "name": item.name,
                    "required": required_total,
                    "available": item.current_stock
                })

        assert can_produce is False
        assert len(missing) > 0


class TestProductionCostCalculation:
    """Ishlab chiqarish xarajatlari hisob-kitobini test qilish"""

    def test_material_cost_calculation(self, db_session, setup_production_data):
        """Material xarajatlarini hisoblash"""
        product_id = setup_production_data["products"][0].id
        quantity = 100

        formula_items = db_session.query(
            models.ProductFormula.quantity.label('required_per_unit'),
            models.RawMaterial.price_per_unit
        ).join(
            models.RawMaterial,
            models.ProductFormula.raw_material_id == models.RawMaterial.id
        ).filter(
            models.ProductFormula.product_id == product_id
        ).all()

        total_cost = 0
        for item in formula_items:
            required_total = item.required_per_unit * quantity
            material_cost = required_total * item.price_per_unit
            total_cost += material_cost

        # 100 qop * (45kg * 500 so'm + 5kg * 300 so'm) = 100 * (22500 + 1500) = 2400000
        expected = 100 * (45 * 500 + 5 * 300)
        assert total_cost == expected

    def test_labor_cost_calculation(self, db_session, setup_production_data):
        """Mehnat xarajatlarini hisoblash (30%)"""
        material_cost = 2400000
        labor_rate = 0.3

        labor_cost = material_cost * labor_rate

        assert labor_cost == 720000

    def test_energy_cost_calculation(self, db_session, setup_production_data):
        """Energiya xarajatlarini hisoblash (10%)"""
        material_cost = 2400000
        energy_rate = 0.1

        energy_cost = material_cost * energy_rate

        assert energy_cost == 240000

    def test_total_cost_with_overhead(self, db_session, setup_production_data):
        """Jami xarajat (material + mehnat + energiya)"""
        material_cost = 2400000
        labor_cost = material_cost * 0.3
        energy_cost = material_cost * 0.1
        total = material_cost + labor_cost + energy_cost

        expected = 2400000 + 720000 + 240000
        assert total == expected

    def test_unit_cost_calculation(self, db_session, setup_production_data):
        """Birlik xarajatini hisoblash"""
        total_cost = 3360000
        quantity = 100

        unit_cost = total_cost / quantity

        assert unit_cost == 33600

    def test_profit_margin_calculation(self, db_session, setup_production_data):
        """Foyda marjasini hisoblash"""
        selling_price = 12000
        unit_cost = 33600

        profit_per_unit = selling_price - unit_cost
        profit_margin = (profit_per_unit / selling_price * 100) if selling_price > 0 else 0

        # Bu holda foyda manfiy - zarar
        assert profit_per_unit < 0

    def test_profitable_product(self, db_session, setup_production_data):
        """Foydali mahsulot"""
        selling_price = 50000
        production_cost = 30000

        profit_per_unit = selling_price - production_cost
        profit_margin = (profit_per_unit / selling_price * 100)

        assert profit_per_unit == 20000
        assert profit_margin == 40.0


class TestProductionOrderCreation:
    """Ishlab chiqarish buyurtmasini yaratish testlari"""

    def test_create_production_order(self, db_session, setup_production_data):
        """Buyurtma yaratish"""
        product_id = setup_production_data["products"][0].id

        today = datetime.now()
        order_count = db_session.query(models.ProductionOrder).filter(
            extract('year', models.ProductionOrder.created_at) == today.year,
            extract('month', models.ProductionOrder.created_at) == today.month
        ).count() + 1

        order_number = f"PO-{today.strftime('%Y%m')}-{order_count:04d}"

        order = models.ProductionOrder(
            order_number=order_number,
            product_id=product_id,
            quantity=100,
            total_cost=3360000,
            status=OrderStatus.IN_PROGRESS
        )
        db_session.add(order)
        db_session.commit()

        assert order.id is not None
        assert order.order_number == "PO-" + today.strftime('%Y%m') + "-0001"
        assert order.quantity == 100

    def test_order_status_transition(self, db_session, setup_production_data):
        """Buyurtma holatini o'zgartirish"""
        product_id = setup_production_data["products"][0].id

        order = models.ProductionOrder(
            order_number="PO-TEST-0001",
            product_id=product_id,
            quantity=50,
            total_cost=1680000,
            status=OrderStatus.IN_PROGRESS
        )
        db_session.add(order)
        db_session.commit()

        # Jarayonda -> Tayyor
        order.status = OrderStatus.COMPLETED
        order.actual_end = datetime.utcnow()
        db_session.commit()

        updated = db_session.query(models.ProductionOrder).filter(
            models.ProductionOrder.id == order.id
        ).first()

        assert updated.status == OrderStatus.COMPLETED
        assert updated.actual_end is not None

    def test_order_raw_material_deduction(self, db_session, setup_production_data):
        """Buyurtma uchun xom ashyo kamaytirish"""
        material = setup_production_data["materials"][0]  # Klinker
        initial_stock = material.current_stock

        quantity = 100
        formula_items = db_session.query(
            models.ProductFormula.quantity.label('required_per_unit')
        ).join(
            models.RawMaterial,
            models.ProductFormula.raw_material_id == models.RawMaterial.id
        ).filter(
            models.ProductFormula.product_id == setup_production_data["products"][0].id,
            models.RawMaterial.name == "Klinker"
        ).all()

        for item in formula_items:
            required_total = item.required_per_unit * quantity
            material.current_stock -= required_total

        db_session.commit()

        updated = db_session.query(models.RawMaterial).filter(
            models.RawMaterial.id == material.id
        ).first()

        assert updated.current_stock == initial_stock - (45 * 100)


class TestProductionStatistics:
    """Ishlab chiqarish statistikasi testlari"""

    def test_empty_production_statistics(self, db_session):
        """Bo'sh ishlab chiqarish statistikasi"""
        from datetime import date, timedelta

        stats = get_production_statistics(
            db_session,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today()
        )

        assert stats["total_orders"] == 0
        assert stats["completed_orders"] == 0

    def test_production_statistics_with_orders(self, db_session, setup_production_data):
        """Buyurtmalar bilan statistika"""
        from datetime import timedelta

        product_id = setup_production_data["products"][0].id

        # 3 ta buyurtma yaratish
        for i in range(3):
            order = models.ProductionOrder(
                order_number=f"STAT-{i+1:04d}",
                product_id=product_id,
                quantity=100 * (i + 1),
                total_cost=700000 * (i + 1),
                status=OrderStatus.COMPLETED if i < 2 else OrderStatus.IN_PROGRESS,
                created_at=datetime.utcnow()
            )
            db_session.add(order)
        db_session.commit()

        stats = get_production_statistics(
            db_session,
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow() + timedelta(days=1)
        )

        assert stats["total_orders"] == 3
        assert stats["completed_orders"] == 2
        assert stats["total_quantity"] == 600  # 100 + 200 + 300

    def test_production_completion_rate(self, db_session, setup_production_data):
        """Bajarilish darajasi"""
        product_id = setup_production_data["products"][0].id

        # 4 ta buyurtma, 3 tasi bajarilgan
        for i in range(4):
            order = models.ProductionOrder(
                order_number=f"RATE-{i+1:04d}",
                product_id=product_id,
                quantity=100,
                total_cost=700000,
                status=OrderStatus.COMPLETED if i < 3 else OrderStatus.IN_PROGRESS,
                created_at=datetime.utcnow()
            )
            db_session.add(order)
        db_session.commit()

        from datetime import timedelta
        stats = get_production_statistics(
            db_session,
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow() + timedelta(days=1)
        )

        assert stats["total_orders"] == 4
        assert stats["completed_orders"] == 3
        assert stats["completion_rate"] == 75.0


class TestProductLookup:
    """Mahsulot qidirish testlari"""

    def test_get_product_by_name(self, db_session, setup_production_data):
        """Nom bo'yicha mahsulot qidirish"""
        product = db_session.query(models.Product).filter(
            models.Product.name == "Cement M500"
        ).first()

        assert product is not None
        assert product.category == "sement"
        assert product.selling_price == 12000

    def test_get_active_products(self, db_session, setup_production_data):
        """Faol mahsulotlarni olish"""
        active_products = db_session.query(models.Product).filter(
            models.Product.is_active == True
        ).all()

        assert len(active_products) == 3

    def test_get_products_by_category(self, db_session, setup_production_data):
        """Kategoriya bo'yicha mahsulotlar"""
        sement_products = db_session.query(models.Product).filter(
            models.Product.category == "sement",
            models.Product.is_active == True
        ).all()

        assert len(sement_products) == 1
        assert sement_products[0].name == "Cement M500"

    def test_product_price_lookup(self, db_session, setup_production_data):
        """Mahsulot narxini olish"""
        product = db_session.query(models.Product).filter(
            models.Product.name == "Cement M500"
        ).first()

        assert product.selling_price == 12000
        assert product.production_cost == 7000
        assert product.selling_price > product.production_cost
