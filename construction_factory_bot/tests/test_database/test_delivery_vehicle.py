"""
v5.4 — Yetkazib berishda transport vositasi (TZ ERD: deliveries.vehicle_id)

- create_delivery_with_vehicle: topshiriq + faol mashina bog'lash
- Noto'g'ri/faol bo'lmagan mashina -> ValueError
- set_delivery_vehicle: haydovchi mashina tanlashi (GPS boshlashda)
- delivery_with_vehicle_dict: API javobida vehicle_id/vehicle_number
"""
from datetime import datetime

import pytest

from database import models, crud, crud_v54


@pytest.fixture
def product(db_session):
    p = models.Product(name="DlvV Sement", category="sement", unit="qop",
                       selling_price=12000, production_cost=7000, is_active=True)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def driver(db_session):
    emp = models.Employee(
        telegram_id=9101, full_name="Haydovchi Vali", phone_number="+998901234510",
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
        "name": "DlvV Mijoz", "phone": "+998907771200", "credit_limit": 5_000_000,
        "address": "Toshkent sh. Chilonzor 7-mavze",
    })


@pytest.fixture
def vehicle(db_session):
    v = models.Vehicle(number="01 A 777 BB", brand="MAN TGS", capacity=20000,
                       fuel_type="dizel", fuel_norm_per_km=0.35, status="faol")
    db_session.add(v)
    db_session.commit()
    db_session.refresh(v)
    return v


def _sale(db_session, product, customer, qty=50):
    return crud.create_sale_record(
        db_session, product_id=product.id, quantity=qty, unit_price=12000,
        total_amount=qty * 12000, payment_method="cash",
        customer=customer, customer_name=customer.name,
        customer_phone=customer.phone,
        user_id=7, user_name="Sotuvchi",
    )


class TestCreateDeliveryWithVehicle:
    def test_create_with_vehicle(self, db_session, product, driver, customer, vehicle):
        sale = _sale(db_session, product, customer)
        d = crud_v54.create_delivery_with_vehicle(
            db_session, sale_id=sale.id, driver_id=driver.id,
            created_by="Direktor", vehicle_id=vehicle.id,
        )
        assert d.vehicle_id == vehicle.id
        assert d.delivery_number.startswith("DLV-")

    def test_create_without_vehicle(self, db_session, product, driver, customer):
        sale = _sale(db_session, product, customer)
        d = crud_v54.create_delivery_with_vehicle(
            db_session, sale_id=sale.id, driver_id=driver.id, created_by="Direktor",
        )
        assert d.vehicle_id is None

    def test_unknown_vehicle_rejected(self, db_session, product, driver, customer):
        sale = _sale(db_session, product, customer)
        with pytest.raises(ValueError):
            crud_v54.create_delivery_with_vehicle(
                db_session, sale_id=sale.id, driver_id=driver.id, vehicle_id=99999,
            )

    def test_inactive_vehicle_rejected(self, db_session, product, driver, customer, vehicle):
        sale = _sale(db_session, product, customer)
        vehicle.status = "ta'mirda"
        db_session.commit()
        with pytest.raises(ValueError):
            crud_v54.create_delivery_with_vehicle(
                db_session, sale_id=sale.id, driver_id=driver.id, vehicle_id=vehicle.id,
            )


class TestSetDeliveryVehicle:
    def test_set_vehicle_on_existing(self, db_session, product, driver, customer, vehicle):
        sale = _sale(db_session, product, customer)
        d = crud.create_delivery(db_session, sale_id=sale.id, driver_id=driver.id)
        assert d.vehicle_id is None
        crud_v54.set_delivery_vehicle(db_session, d.id, vehicle.id)
        db_session.refresh(d)
        assert d.vehicle_id == vehicle.id

    def test_set_vehicle_completed_rejected(self, db_session, product, driver, customer, vehicle):
        sale = _sale(db_session, product, customer)
        d = crud.create_delivery(db_session, sale_id=sale.id, driver_id=driver.id)
        crud.complete_delivery(db_session, d.id)
        with pytest.raises(ValueError):
            crud_v54.set_delivery_vehicle(db_session, d.id, vehicle.id)

    def test_set_unknown_vehicle_rejected(self, db_session, product, driver, customer):
        sale = _sale(db_session, product, customer)
        d = crud.create_delivery(db_session, sale_id=sale.id, driver_id=driver.id)
        with pytest.raises(ValueError):
            crud_v54.set_delivery_vehicle(db_session, d.id, 99999)


class TestDeliveryWithVehicleDict:
    def test_dict_includes_vehicle(self, db_session, product, driver, customer, vehicle):
        sale = _sale(db_session, product, customer)
        d = crud_v54.create_delivery_with_vehicle(
            db_session, sale_id=sale.id, driver_id=driver.id, vehicle_id=vehicle.id,
        )
        data = crud_v54.delivery_with_vehicle_dict(db_session, d)
        assert data["vehicle_id"] == vehicle.id
        assert data["vehicle_number"] == "01 A 777 BB (MAN TGS)"

    def test_dict_vehicle_none(self, db_session, product, driver, customer):
        sale = _sale(db_session, product, customer)
        d = crud.create_delivery(db_session, sale_id=sale.id, driver_id=driver.id)
        data = crud_v54.delivery_with_vehicle_dict(db_session, d)
        assert data["vehicle_id"] is None
        assert data["vehicle_number"] is None