"""
ISHLAB CHIQARISH SIFAT NAZORATI (QC) testlari — tayyor mahsulot chiqishida

TZ: "Chiqishda mahsulot sinovdan o'tkaziladi, natija raqamli dalolatnomaga yoziladi"
- qabul_qilingan: hammasi qabul -> omborga +quantity
- qisman: rejected_qty rad -> omborga faqat qabul qilingani
- rad_etilgan: hammasi brak -> omborga hech narsa kirmaydi
Har bir akt: ProductionQC + buyurtma qc holati + WarehouseTransaction qatorlari.
"""
from datetime import datetime

import pytest

from database import models, crud


@pytest.fixture
def product(db_session):
    p = models.Product(name="QC G'isht", category="g'isht", unit="dona",
                       selling_price=3000, production_cost=1500, is_active=True)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


def _completed_order(db_session, product, quantity=100, order_number="PO-QC-0001"):
    o = models.ProductionOrder(
        order_number=order_number,
        product_id=product.id,
        quantity=quantity,
        total_cost=quantity * 1500,
        status=models.OrderStatus.COMPLETED,
        actual_end=datetime.utcnow(),
    )
    db_session.add(o)
    db_session.commit()
    db_session.refresh(o)
    return o


def _ledger_rows(db_session, order, act_number):
    """QC akti yozgan ombor qatorlari"""
    return db_session.query(models.WarehouseTransaction).filter(
        models.WarehouseTransaction.product_id == order.product_id,
        models.WarehouseTransaction.document_number == act_number,
    ).all()


class TestCreateProductionQC:
    def test_qabul_all_accepted(self, db_session, product):
        order = _completed_order(db_session, product, quantity=100)
        qc = crud.create_production_qc(db_session, order_id=order.id,
                                       quality_status="qabul_qilingan",
                                       created_by="Tekshiruvchi")

        assert qc.act_number.startswith("SQC-")
        assert qc.quantity_checked == 100
        assert qc.accepted_qty == 100
        assert qc.rejected_qty == 0
        assert qc.quality_status == "qabul_qilingan"

        db_session.refresh(order)
        assert order.qc_status == "qabul_qilingan"
        assert order.accepted_qty == 100
        assert order.rejected_qty == 0
        assert order.qc_at is not None

        rows = _ledger_rows(db_session, order, qc.act_number)
        assert len(rows) == 1  # faqat +kirim, brak qatori yo'q
        assert rows[0].quantity == 100
        assert rows[0].target_warehouse == "tayyor"
        # Sotiladigan qoldiqqa 100 kirdi
        assert crud.get_available_product_qty(db_session, product.id) == 100

    def test_rejected_all_goes_to_brak(self, db_session, product):
        order = _completed_order(db_session, product, quantity=100)
        qc = crud.create_production_qc(db_session, order_id=order.id,
                                       quality_status="rad_etilgan",
                                       created_by="Tekshiruvchi")

        assert qc.accepted_qty == 0
        assert qc.rejected_qty == 100
        db_session.refresh(order)
        assert order.qc_status == "rad_etilgan"

        rows = _ledger_rows(db_session, order, qc.act_number)
        assert len(rows) == 2
        kirim = [r for r in rows if r.quantity > 0][0]
        brak = [r for r in rows if r.quantity < 0][0]
        assert kirim.quantity == 100 and kirim.target_warehouse == "tayyor"
        assert brak.quantity == -100 and brak.target_warehouse == "brak"
        # Hammasi brak -> sotiladigan qoldiqqa hech narsa kirmaydi
        assert crud.get_available_product_qty(db_session, product.id) == 0

    def test_partial_accepted_only(self, db_session, product):
        order = _completed_order(db_session, product, quantity=100)
        qc = crud.create_production_qc(db_session, order_id=order.id,
                                       quality_status="qisman",
                                       rejected_qty=30,
                                       notes="Namligi baland",
                                       created_by="Tekshiruvchi")

        assert qc.accepted_qty == 70
        assert qc.rejected_qty == 30
        assert qc.notes == "Namligi baland"
        db_session.refresh(order)
        assert order.accepted_qty == 70
        assert order.rejected_qty == 30
        # Qabul qilingan 70 omborga kirdi
        assert crud.get_available_product_qty(db_session, product.id) == 70

    def test_invalid_partial_bounds(self, db_session, product):
        order = _completed_order(db_session, product, quantity=100)
        with pytest.raises(ValueError):
            crud.create_production_qc(db_session, order_id=order.id,
                                      quality_status="qisman", rejected_qty=0)
        with pytest.raises(ValueError):
            crud.create_production_qc(db_session, order_id=order.id,
                                      quality_status="qisman", rejected_qty=100)
        with pytest.raises(ValueError):
            crud.create_production_qc(db_session, order_id=order.id,
                                      quality_status="qisman", rejected_qty=None)

    def test_unknown_status_rejected(self, db_session, product):
        order = _completed_order(db_session, product, quantity=100)
        with pytest.raises(ValueError):
            crud.create_production_qc(db_session, order_id=order.id,
                                      quality_status="nomalum")

    def test_not_completed_order_rejected(self, db_session, product):
        o = models.ProductionOrder(
            order_number="PO-QC-IP", product_id=product.id, quantity=10,
            status=models.OrderStatus.IN_PROGRESS,
        )
        db_session.add(o)
        db_session.commit()
        db_session.refresh(o)
        with pytest.raises(ValueError):
            crud.create_production_qc(db_session, order_id=o.id,
                                      quality_status="qabul_qilingan")

    def test_double_qc_rejected(self, db_session, product):
        order = _completed_order(db_session, product, quantity=100)
        crud.create_production_qc(db_session, order_id=order.id,
                                  quality_status="qabul_qilingan")
        with pytest.raises(ValueError) as exc:
            crud.create_production_qc(db_session, order_id=order.id,
                                      quality_status="qisman", rejected_qty=5)
        assert "o'tkazilgan" in str(exc.value)

    def test_missing_order_rejected(self, db_session):
        with pytest.raises(ValueError):
            crud.create_production_qc(db_session, order_id=999999,
                                      quality_status="qabul_qilingan")


class TestPendingAndHistory:
    def test_pending_list_only_completed_without_qc(self, db_session, product):
        done = _completed_order(db_session, product, order_number="PO-QC-DONE")
        crud.create_production_qc(db_session, order_id=done.id,
                                  quality_status="qabul_qilingan")

        waiting = _completed_order(db_session, product, quantity=50,
                                   order_number="PO-QC-WAIT")
        in_progress = models.ProductionOrder(
            order_number="PO-QC-IP2", product_id=product.id, quantity=10,
            status=models.OrderStatus.IN_PROGRESS,
        )
        db_session.add(in_progress)
        db_session.commit()

        pending = crud.list_production_orders_pending_qc(db_session)
        pending_ids = {o.id for o in pending}
        assert done.id not in pending_ids       # QC o'tgan
        assert in_progress.id not in pending_ids  # hali tayyor emas
        assert waiting.id in pending_ids         # QC kutilmoqda

    def test_history_and_serialization(self, db_session, product):
        order = _completed_order(db_session, product, quantity=60)
        qc = crud.create_production_qc(db_session, order_id=order.id,
                                       quality_status="qisman", rejected_qty=10,
                                       created_by="Tekshiruvchi")

        acts = crud.list_production_qc_acts(db_session)
        assert len(acts) == 1

        d = crud.production_qc_to_dict(db_session, qc)
        assert d["act_number"] == qc.act_number
        assert d["order_number"] == order.order_number
        assert d["product_name"] == product.name
        assert d["accepted_qty"] == 50
        assert d["rejected_qty"] == 10
        assert d["quality_status_label"] == "⚠️ Qisman qabul"
