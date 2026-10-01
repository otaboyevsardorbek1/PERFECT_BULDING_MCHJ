"""
YETKAZIB BERISH REST API testlari:
- GET /api/deliveries/deliverable-sales
- POST /api/deliveries (haydovchi tayinlash)
- POST /api/deliveries/{id}/location (GPS)
- POST /api/deliveries/{id}/complete
- GET /api/deliveries, GET /api/deliveries/{id} (+tracking)
"""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import models, crud
from database.session import get_db


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    s = Session()
    yield s
    s.close()
    models.Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(session):
    from dashboard.app import app

    def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def data_fixture(session):
    """Mahsulot + mijoz + sotuv + haydovchi"""
    p = models.Product(name="API Dlv Sement", category="sement", unit="qop",
                       selling_price=12000, production_cost=7000, is_active=True)
    session.add(p)
    session.commit()
    session.refresh(p)

    customer = crud.create_customer(session, {
        "name": "API Dlv Mijoz", "phone": "+998908881100",
        "address": "Toshkent, Yunusobod 12",
    })
    sale = crud.create_sale_record(
        session, product_id=p.id, quantity=30, unit_price=12000,
        total_amount=360_000, payment_method="cash",
        customer=customer, customer_name=customer.name,
        user_id=7, user_name="Sotuvchi",
    )
    driver = models.Employee(
        telegram_id=9002, full_name="API Haydovchi", phone_number="+998901234501",
        position="Haydovchi", department="logistics",
        status=models.EmployeeStatus.ACTIVE, hire_date=datetime.utcnow(),
        role="haydovchi",
    )
    session.add(driver)
    session.commit()
    session.refresh(driver)
    return {"product": p, "customer": customer, "sale": sale, "driver": driver}


class TestDeliveryAPI:
    def test_deliverable_sales(self, client, data_fixture):
        r = client.get("/api/deliveries/deliverable-sales")
        assert r.status_code == 200
        sales = r.json()["sales"]
        assert any(s["id"] == data_fixture["sale"].id for s in sales)

    def test_create_and_gps_flow(self, client, data_fixture):
        sale = data_fixture["sale"]
        driver = data_fixture["driver"]

        r = client.post("/api/deliveries", json={
            "sale_id": sale.id, "driver_id": driver.id,
        })
        assert r.status_code == 200
        d = r.json()["delivery"]
        assert d["delivery_number"].startswith("DLV-")
        assert d["status"] == "tayinlangan"
        assert d["driver_name"] == driver.full_name
        assert d["customer_address"] == data_fixture["customer"].address

        did = d["id"]

        # GPS nuqtasi -> avtomatik 'yo'lda'
        gps = client.post(f"/api/deliveries/{did}/location", json={
            "latitude": 41.311081, "longitude": 69.240562, "accuracy": 5,
        })
        assert gps.status_code == 200
        assert gps.json()["ok"] is True

        detail = client.get(f"/api/deliveries/{did}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["delivery"]["status"] == "yo'lda"
        assert body["delivery"]["current_lat"] == 41.311081
        assert len(body["tracking"]) == 1

        # Yakunlash
        done = client.post(f"/api/deliveries/{did}/complete")
        assert done.status_code == 200
        assert done.json()["delivery"]["status"] == "yetkazildi"

    def test_list_and_duplicate_rejected(self, client, data_fixture):
        sale = data_fixture["sale"]
        driver = data_fixture["driver"]
        client.post("/api/deliveries", json={"sale_id": sale.id, "driver_id": driver.id})

        # Dublikat topshiriq -> 400
        r2 = client.post("/api/deliveries", json={"sale_id": sale.id, "driver_id": driver.id})
        assert r2.status_code == 400

        lst = client.get("/api/deliveries")
        assert lst.status_code == 200
        assert len(lst.json()["deliveries"]) == 1

        lst2 = client.get(f"/api/deliveries?driver_id={driver.id}&status=tayinlangan")
        assert len(lst2.json()["deliveries"]) == 1

    def test_non_driver_rejected(self, client, data_fixture, session):
        sale = data_fixture["sale"]
        seller = models.Employee(
            full_name="Oddiy Sotuvchi", phone_number="+998909990001",
            position="Sotuvchi", department="sales",
            status=models.EmployeeStatus.ACTIVE, hire_date=datetime.utcnow(),
            role="sotuvchi",
        )
        session.add(seller)
        session.commit()
        session.refresh(seller)

        r = client.post("/api/deliveries", json={"sale_id": sale.id, "driver_id": seller.id})
        assert r.status_code == 400
