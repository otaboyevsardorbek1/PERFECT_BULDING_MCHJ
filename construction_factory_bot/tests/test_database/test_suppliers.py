"""
Yetkazib beruvchilar va qabul aktlari (v3) testlari
"""
from datetime import datetime
import pytest

from database import models, crud


@pytest.fixture
def sample_material(db_session):
    m = models.RawMaterial(name="Supplier Cement", unit="tonna",
                           current_stock=0, min_stock=100,
                           price_per_unit=500000)
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    return m


class TestSupplierCRUD:
    def test_create_supplier(self, db_session):
        s = crud.create_supplier(db_session, {"name": "Sement Zavodi", "phone": "+998901234567"})
        assert s.id is not None
        assert s.name == "Sement Zavodi"
        assert s.rating == 5.0

    def test_list(self, db_session):
        crud.create_supplier(db_session, {"name": "S1"})
        crud.create_supplier(db_session, {"name": "S2"})
        assert len(crud.list_suppliers(db_session)) == 2

    def test_update(self, db_session):
        s = crud.create_supplier(db_session, {"name": "S3"})
        updated = crud.update_supplier(db_session, s.id, {"phone": "+998901111111"})
        assert updated.phone == "+998901111111"


class TestSupplierDelivery:
    def test_full_acceptance_increases_stock(self, db_session, sample_material):
        supplier = crud.create_supplier(db_session, {"name": "Supplier A"})
        delivery = crud.create_supplier_delivery(
            db_session, supplier.id, sample_material.id,
            quantity_ordered=100, quantity_received=100,
            quality_status="qabul_qilingan", price_per_unit=500000,
            created_by="Tester",
        )
        db_session.refresh(sample_material)
        assert delivery.quantity_received == 100
        assert sample_material.current_stock == 100
        assert supplier.on_time_count == 1
        assert delivery.deficiency_amount == 0

    def test_shortage_creates_supplier_debt(self, db_session, sample_material):
        supplier = crud.create_supplier(db_session, {"name": "Supplier Short"})
        delivery = crud.create_supplier_delivery(
            db_session, supplier.id, sample_material.id,
            quantity_ordered=100, quantity_received=80,
            quality_status="qabul_qilingan", price_per_unit=500000,
        )
        db_session.refresh(sample_material)
        # Qabul qilingan 80 tonna; kamomad 20 tonna * 500k = 10 mln yetkazib beruvchi qarziga
        assert sample_material.current_stock == 80
        assert delivery.deficiency_amount == 10_000_000
        assert supplier.total_debt == 10_000_000

    def test_reject_no_stock_and_full_debt(self, db_session, sample_material):
        supplier = crud.create_supplier(db_session, {"name": "Bad Quality"})
        delivery = crud.create_supplier_delivery(
            db_session, supplier.id, sample_material.id,
            quantity_ordered=50, quantity_received=50,
            quality_status="rad_etilgan", price_per_unit=500000,
        )
        db_session.refresh(sample_material)
        assert sample_material.current_stock == 0  # rad etilgan -> zaxiraga kirmaydi
        assert delivery.deficiency_amount == 25_000_000

    def test_supplier_rating_drops_after_late(self, db_session, sample_material):
        supplier = crud.create_supplier(db_session, {"name": "Late Supplier"})
        crud.create_supplier_delivery(db_session, supplier.id, sample_material.id,
                                      quantity_ordered=10, quantity_received=10,
                                      quality_status="qabul_qilingan")
        crud.create_supplier_delivery(db_session, supplier.id, sample_material.id,
                                      quantity_ordered=10, quantity_received=5,
                                      quality_status="qabul_qilingan")
        db_session.refresh(supplier)
        assert supplier.on_time_count == 1
        assert supplier.late_count == 1
        assert supplier.rating < 5.0


class TestReorderSuggestions:
    def test_suggests_low_stock(self, db_session):
        m = models.RawMaterial(name="Low Stock Mat", unit="kg",
                               current_stock=50, min_stock=200,
                               price_per_unit=100, supplier="Supplier X")
        db_session.add(m)
        db_session.commit()
        suggestions = crud.get_supplier_reorder_suggestions(db_session)
        assert len(suggestions) == 1
        assert suggestions[0]["raw_material_name"] == "Low Stock Mat"
        # tavsiya: min*2 - current = 400 - 50 = 350
        assert suggestions[0]["suggested_order"] == 350

    def test_no_suggestions_when_enough(self, db_session):
        m = models.RawMaterial(name="Enough Stock", unit="kg",
                               current_stock=1000, min_stock=100, price_per_unit=100)
        db_session.add(m)
        db_session.commit()
        assert crud.get_supplier_reorder_suggestions(db_session) == []
