"""
YETKAZIB BERISH (DELIVERY + GPS) moduli testlari

Qamrov:
- Topshiriq yaratish (haydovchi tayinlash, qoldiq tekshiruvi)
- Validatsiya: haydovchi emas / faol emas / qoldiq yo'q / dublikat topshiriq
- Haydovchi topshiriqlarini ro'yxatlash
- Boshlash ('yo'lda') va GPS nuqta qayd qilish (auto-start)
- Yakunlash -> sotuv 'yetkazib_berildi'
- Bekor qilish
"""
from datetime import datetime

import pytest

from database import models, crud


@pytest.fixture
def product(db_session):
    p = models.Product(name="Dlv Sement", category="sement", unit="qop",
                       selling_price=12000, production_cost=7000, is_active=True)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def driver(db_session):
    emp = models.Employee(
        telegram_id=9001, full_name="Haydovchi Ali", phone_number="+998901234500",
        position="Haydovchi", department="logistics",
        status=models.EmployeeStatus.ACTIVE, hire_date=datetime.utcnow(),
        role="haydovchi",
    )
    db_session.add(emp)
    db_session.commit()
    db_session.refresh(emp)
    return emp


@pytest.fixture
def customer(db_session):
    return crud.create_customer(db_session, {
        "name": "Dlv Mijoz", "phone": "+998907771100", "credit_limit": 5_000_000,
        "address": "Toshkent sh. Chilonzor 5-mavze",
    })


def _sale(db_session, product, customer, qty=50):
    return crud.create_sale_record(
        db_session, product_id=product.id, quantity=qty, unit_price=12000,
        total_amount=qty * 12000, payment_method="cash",
        customer=customer, customer_name=customer.name,
        customer_phone=customer.phone,
        user_id=7, user_name="Sotuvchi",
    )


def _active_employee(db_session, role="ishchi", name="Oddiy Xodim"):
    emp = models.Employee(
        full_name=name, phone_number=f"+9989099900{db_session.query(models.Employee).count()}",
        position=name, department="sales",
        status=models.EmployeeStatus.ACTIVE, hire_date=datetime.utcnow(), role=role,
    )
    db_session.add(emp)
    db_session.commit()
    db_session.refresh(emp)
    return emp


class TestCreateDelivery:
    def test_create_delivery_assigns_driver(self, db_session, product, driver, customer):
        sale = _sale(db_session, product, customer)
        d = crud.create_delivery(
            db_session, sale_id=sale.id, driver_id=driver.id,
            created_by="Direktor",
        )
        assert d.delivery_number.startswith("DLV-")
        assert d.status == "tayinlangan"
        assert d.driver_id == driver.id
        assert d.driver_name == driver.full_name
        assert d.quantity == 50
        assert d.customer_name == customer.name
        assert d.customer_phone == customer.phone
        assert d.customer_address == customer.address  # mijoz manzili avtomatik
        assert d.product_name == product.name
        assert d.sale_id == sale.id

    def test_create_delivery_with_custom_quantity(self, db_session, product, driver, customer):
        sale = _sale(db_session, product, customer, qty=100)
        d = crud.create_delivery(db_session, sale_id=sale.id, driver_id=driver.id, quantity=40)
        assert d.quantity == 40

    def test_duplicate_active_delivery_rejected(self, db_session, product, driver, customer):
        sale = _sale(db_session, product, customer)
        crud.create_delivery(db_session, sale_id=sale.id, driver_id=driver.id)
        with pytest.raises(ValueError):
            crud.create_delivery(db_session, sale_id=sale.id, driver_id=driver.id)

    def test_delivery_after_full_return_rejected(self, db_session, product, driver, customer):
        sale = _sale(db_session, product, customer, qty=10)
        crud.create_return_act(db_session, sale_id=sale.id, quantity=10, refund_type="cash")
        with pytest.raises(ValueError):
            crud.create_delivery(db_session, sale_id=sale.id, driver_id=driver.id)

    def test_non_driver_rejected(self, db_session, product, customer):
        sale = _sale(db_session, product, customer)
        seller = _active_employee(db_session, role="sotuvchi", name="Sotuvchi X")
        with pytest.raises(ValueError):
            crud.create_delivery(db_session, sale_id=sale.id, driver_id=seller.id)

    def test_inactive_driver_rejected(self, db_session, product, customer):
        sale = _sale(db_session, product, customer)
        fired = _active_employee(db_session, role="haydovchi", name="Ishdan Ketgan")
        fired.status = models.EmployeeStatus.FIRED
        db_session.commit()
        with pytest.raises(ValueError):
            crud.create_delivery(db_session, sale_id=sale.id, driver_id=fired.id)

    def test_unknown_sale_rejected(self, db_session, driver):
        with pytest.raises(ValueError):
            crud.create_delivery(db_session, sale_id=999999, driver_id=driver.id)

    def test_list_deliverable_sales(self, db_session, product, customer):
        sale = _sale(db_session, product, customer)
        candidates = crud.list_deliverable_sales(db_session)
        assert any(s.id == sale.id for s in candidates)


class TestDeliveryLifecycle:
    def test_start_and_record_gps(self, db_session, product, driver, customer):
        sale = _sale(db_session, product, customer)
        d = crud.create_delivery(db_session, sale_id=sale.id, driver_id=driver.id)

        # Joylashuv yuborilganda avtomatik 'yo'lda' boshlanadi
        p1 = crud.record_delivery_location(db_session, d.id, 41.311081, 69.240562,
                                           accuracy=10, source="telegram")
        db_session.refresh(d)
        assert d.status == "yo'lda"
        assert d.started_at is not None
        assert d.start_lat == 41.311081
        assert d.current_lat == 41.311081

        p2 = crud.record_delivery_location(db_session, d.id, 41.320000, 69.250000)
        db_session.refresh(d)
        assert d.current_lat == 41.320000
        # Ikki nuqta saqlangan
        points = crud.list_delivery_locations(db_session, d.id)
        assert len(points) == 2
        assert points[0].source == "telegram"
        assert points[1].source == "api"

        # Driver topshiriqlarida ko'rinadi
        mine = crud.list_deliveries(db_session, driver_id=driver.id)
        assert len(mine) == 1
        assert mine[0].id == d.id

    def test_complete_delivery_marks_sale_delivered(self, db_session, product, driver, customer):
        sale = _sale(db_session, product, customer)
        d = crud.create_delivery(db_session, sale_id=sale.id, driver_id=driver.id)
        crud.record_delivery_location(db_session, d.id, 41.311081, 69.240562)

        d2 = crud.complete_delivery(db_session, d.id)
        assert d2.status == "yetkazildi"
        assert d2.delivered_at is not None
        db_session.refresh(sale)
        assert sale.status == "yetkazib_berildi"

        # Yakunlangan topshiriqqa GPS qayd etilmaydi
        with pytest.raises(ValueError):
            crud.record_delivery_location(db_session, d.id, 41.0, 69.0)

        # Endi bu sotuv yetkazilgan — yangi topshiriq yaratib bo'lmaydi
        candidates = crud.list_deliverable_sales(db_session)
        assert all(s.id != sale.id for s in candidates)

    def test_cancel_delivery(self, db_session, product, driver, customer):
        sale = _sale(db_session, product, customer)
        d = crud.create_delivery(db_session, sale_id=sale.id, driver_id=driver.id)
        d2 = crud.cancel_delivery(db_session, d.id, note="Mijoz kechiktirdi")
        assert d2.status == "bekor"
        assert d2.cancelled_at is not None

        # Bekor qilingan topshiriqdan keyin qayta yaratish mumkin
        d3 = crud.create_delivery(db_session, sale_id=sale.id, driver_id=driver.id)
        assert d3.id != d.id

    def test_delivery_serialization(self, db_session, product, driver, customer):
        sale = _sale(db_session, product, customer)
        d = crud.create_delivery(db_session, sale_id=sale.id, driver_id=driver.id)
        dct = crud.delivery_to_dict(d)
        assert dct["delivery_number"].startswith("DLV-")
        assert dct["status_label"] == "📋 Tayinlangan"
        assert dct["driver_name"] == driver.full_name
        assert dct["customer_address"] == customer.address
        assert crud.get_delivery(db_session, d.id).id == d.id
        assert crud.get_delivery(db_session, 999999) is None
