"""
Ombor operatsiyalari (v3): konvertatsiya, rezervatsiya, ko'chirish, inventarizatsiya
"""
from datetime import datetime, timedelta
import pytest

from database import models, crud


@pytest.fixture
def finished_product(db_session):
    """Ishlab chiqarilgan va sotilgan mahsulot (qoldiq = 70)"""
    p = models.Product(name="Ops Sement", category="sement", unit="qop",
                       selling_price=12000, production_cost=7000, is_active=True)
    db_session.add(p)
    db_session.flush()
    db_session.add(models.WarehouseTransaction(product_id=p.id, quantity=100,
                                               transaction_type=models.TransactionType.PRODUCTION,
                                               user_id=1))
    db_session.add(models.WarehouseTransaction(product_id=p.id, quantity=30,
                                               transaction_type=models.TransactionType.SALE,
                                               user_id=1))
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def raw_material(db_session):
    m = models.RawMaterial(name="Ops Clay", unit="kg", current_stock=5000,
                           min_stock=500, price_per_unit=100)
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    return m


class TestUnitConversion:
    def test_add_units(self, db_session, finished_product):
        crud.add_product_unit(db_session, finished_product.id, "qop", 50, "kg")
        crud.add_product_unit(db_session, finished_product.id, "pallet", 2000, "kg")
        units = crud.get_product_units(db_session, finished_product.id)
        assert len(units) == 2

    def test_convert_pallet_to_qop(self, db_session, finished_product):
        crud.add_product_unit(db_session, finished_product.id, "qop", 50, "kg")
        crud.add_product_unit(db_session, finished_product.id, "pallet", 2000, "kg")
        result = crud.convert_quantity(db_session, finished_product.id, "pallet", 2, "qop")
        assert result["result"] == 80  # 2 pallet = 4000 kg = 80 qop

    def test_convert_unknown_unit(self, db_session, finished_product):
        result = crud.convert_quantity(db_session, finished_product.id, "kg", 10, "qop")
        assert "error" in result

    def test_double_add_updates_factor(self, db_session, finished_product):
        crud.add_product_unit(db_session, finished_product.id, "qop", 50, "kg")
        crud.add_product_unit(db_session, finished_product.id, "qop", 25, "kg")
        units = crud.get_product_units(db_session, finished_product.id)
        assert len(units) == 1
        assert units[0].factor == 25


class TestReservations:
    def test_create_reservation_ok(self, db_session, finished_product):
        result = crud.create_reservation(db_session, finished_product.id, 20,
                                         expires_in_hours=2, customer_name="Ali")
        assert "error" not in result
        assert result["reservation"].status == "faol"

    def test_create_reservation_not_enough(self, db_session, finished_product):
        # Qoldiq 70 ta, 100 ta rezerv qilib bo'lmaydi
        result = crud.create_reservation(db_session, finished_product.id, 100)
        assert "error" in result

    def test_available_qty_excludes_active(self, db_session, finished_product):
        available_before = crud.get_available_product_qty(db_session, finished_product.id)
        assert available_before == 70
        crud.create_reservation(db_session, finished_product.id, 20)
        available_after = crud.get_available_product_qty(db_session, finished_product.id)
        assert available_after == 50

    def test_expired_released(self, db_session, finished_product):
        r = crud.create_reservation(db_session, finished_product.id, 20,
                                    expires_in_hours=1)["reservation"]
        # Muddati o'tgan qilib qo'yamiz
        r.expires_at = datetime.utcnow() - timedelta(hours=1)
        db_session.commit()
        released = crud.release_expired_reservations(db_session)
        assert released == 1
        db_session.refresh(r)
        assert r.status == "yechilgan"
        # Zaxira yana ochiladi
        assert crud.get_available_product_qty(db_session, finished_product.id) == 70

    def test_cancel_reservation(self, db_session, finished_product):
        r = crud.create_reservation(db_session, finished_product.id, 10)["reservation"]
        assert crud.cancel_reservation(db_session, r.id) is True
        db_session.refresh(r)
        assert r.status == "bekor_qilingan"


class TestTransfers:
    def test_transfer_raw_material(self, db_session, raw_material):
        result = crud.create_transfer(db_session, "raw", raw_material.id, 500,
                                      "xomashyo", "tayyor", user_name="Tester")
        assert "error" not in result
        transfers = crud.list_transfers(db_session)
        assert len(transfers) == 1
        assert transfers[0].source_warehouse == "xomashyo"
        assert transfers[0].target_warehouse == "tayyor"
        db_session.refresh(raw_material)
        assert raw_material.warehouse == "tayyor"

    def test_transfer_not_enough_raw(self, db_session, raw_material):
        result = crud.create_transfer(db_session, "raw", raw_material.id, 999999,
                                      "asosiy", "brak")
        assert "error" in result

    def test_transfer_product(self, db_session, finished_product):
        result = crud.create_transfer(db_session, "product", finished_product.id, 10,
                                      "tayyor", "asosiy", user_name="T")
        assert "error" not in result
        db_session.refresh(finished_product)
        assert finished_product.warehouse == "asosiy"

    def test_transfer_product_not_enough(self, db_session, finished_product):
        """Tayyor mahsulotni mavjud qoldiqdan ortiq ko'chirib bo'lmaydi (qoldiq = 70)"""
        result = crud.create_transfer(db_session, "product", finished_product.id, 99999,
                                      "tayyor", "asosiy")
        assert "error" in result
        assert "yetarli emas" in result["error"]

    def test_transfer_zero_qty_rejected(self, db_session, finished_product):
        result = crud.create_transfer(db_session, "product", finished_product.id, 0,
                                      "tayyor", "asosiy")
        assert "error" in result

    def test_transfer_product_available_boundary(self, db_session, finished_product):
        """Aynan qoldiqqa teng miqdorni ko'chirish mumkin"""
        result = crud.create_transfer(db_session, "product", finished_product.id, 70,
                                      "tayyor", "asosiy")
        assert "error" not in result

    def test_reservation_zero_qty_rejected(self, db_session, finished_product):
        result = crud.create_reservation(db_session, finished_product.id, 0,
                                         expires_in_hours=2)
        assert "error" in result


class TestInventoryCheck:
    def test_check_match_no_act(self, db_session, raw_material):
        check = crud.create_inventory_check(db_session, "asosiy", "raw", raw_material.id,
                                            actual_quantity=5000, created_by="T")
        assert check.system_quantity == 5000
        assert check.difference == 0
        assert check.act_created is False

    def test_shortage_creates_act(self, db_session, raw_material):
        check = crud.create_inventory_check(db_session, "asosiy", "raw", raw_material.id,
                                            actual_quantity=4800, reason="O'girlik gumoni",
                                            created_by="T")
        assert check.difference == -200
        assert check.act_created is True

    def test_product_check(self, db_session, finished_product):
        check = crud.create_inventory_check(db_session, "tayyor", "product", finished_product.id,
                                            actual_quantity=65, created_by="T")
        assert check.system_quantity == 70
        assert check.difference == -5
        assert check.act_created is True
