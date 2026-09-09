"""
v5.3 testlari — construction_factory_bot.md "TIZIM MUKAMMALLIGI" qoldiq
funksiyalari:

- 🚗 Transport vositalari (ERD: vehicles) — CRUD + takroriy raqam himoyasi
- 📉 Ortiqcha zaxira (ERD: max_stock) — over-stock hisoboti
- 🗺️ Rangli ombor xaritasi (B-bo'lim) — fill-levels
- ⏳ Amal muddati eslatmasi (3.1/3.2) — expiring
- 📅 Xodim smenasi kalendari (E-bo'lim) — work-schedule
- 📤 Xodim ochiq operatsiyalari (H-bo'lim) — open-operations
- 🤔 "Nima bo'lsa?" tahlili (E-bo'lim) — what-if
- 🔐 Rol chegarasi — sotuvchi analytics/vehicles ko'ra olmaydi
"""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import models
from database.session import get_db
from dashboard.auth import get_current_user, set_employee_password


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

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides[get_db] = _override_get_db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _make_employee(session, name="Direktor Test", phone="+998901234567",
                   role="direktor", is_admin=True, password="parol12345"):
    emp = models.Employee(
        full_name=name, phone_number=phone, position=name.split()[0],
        department="admin", hire_date=datetime.utcnow(),
        role=role, is_admin=is_admin,
    )
    session.add(emp)
    session.commit()
    session.refresh(emp)
    if password:
        set_employee_password(session, emp, password)
    return emp


def _auth_headers(client, phone="+998901234567", password="parol12345"):
    r = client.post("/api/login", json={"phone": phone, "password": password})
    assert r.status_code == 200, r.text
    data = r.json()
    return {"Authorization": f"Bearer {data['token']}"}


def _make_product(session, name="Sement", price=60000, category="Sement",
                  min_stock=10, max_stock=100):
    p = models.Product(name=name, category=category, unit="qop",
                       selling_price=price, production_cost=40000,
                       is_active=True, min_stock=min_stock, max_stock=max_stock)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def _add_income(session, product, qty, user_id=1):
    session.add(models.WarehouseTransaction(
        product_id=product.id, quantity=qty,
        transaction_type=models.TransactionType.INCOME,
        user_id=user_id, user_name="test",
    ))
    session.commit()


# ================= 🚗 TRANSPORT VOSITALARI =================

def test_vehicle_crud(client, session):
    _make_employee(session)
    h = _auth_headers(client)

    r = client.post("/api/vehicles", headers=h, json={
        "number": "01 A 123 BB", "brand": "MAN TGS",
        "capacity": 20000, "fuel_type": "dizel", "fuel_norm_per_km": 0.35,
    })
    assert r.status_code == 200, r.text
    vid = r.json()["vehicle"]["id"]

    r = client.get("/api/vehicles", headers=h)
    assert r.status_code == 200
    assert len(r.json()["vehicles"]) == 1
    assert r.json()["vehicles"][0]["number"] == "01 A 123 BB"

    r = client.put(f"/api/vehicles/{vid}", headers=h, json={"capacity": 25000})
    assert r.status_code == 200
    assert r.json()["vehicle"]["capacity"] == 25000.0

    r = client.delete(f"/api/vehicles/{vid}", headers=h)
    assert r.status_code == 200

    r = client.get("/api/vehicles", headers=h)
    assert len(r.json()["vehicles"]) == 0


def test_vehicle_duplicate_number(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    client.post("/api/vehicles", headers=h, json={"number": "01 A 123 BB"})
    r = client.post("/api/vehicles", headers=h, json={"number": "01 A 123 BB"})
    assert r.status_code == 400


def test_vehicle_requires_number(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    r = client.post("/api/vehicles", headers=h, json={"brand": "MAN"})
    assert r.status_code == 400


# ================= 📉 ORTIQCHA ZAXIRA (max_stock) =================

def test_products_over_stock(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    p = _make_product(session, max_stock=100)
    _add_income(session, p, 500)
    r = client.get("/api/products/over-stock", headers=h)
    assert r.status_code == 200
    assert len(r.json()["products"]) == 1
    assert r.json()["products"][0]["name"] == "Sement"
    assert r.json()["products"][0]["available_qty"] == 500.0
    assert r.json()["products"][0]["max_stock"] == 100.0


def test_products_over_stock_empty(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    p = _make_product(session, max_stock=100)
    _add_income(session, p, 50)
    r = client.get("/api/products/over-stock", headers=h)
    assert r.json()["products"] == []


# ================= 🗺️ RANGLI OMBOR XARITASI =================

def test_warehouses_fill_levels(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    p = _make_product(session, max_stock=100)
    _add_income(session, p, 90)  # 90% -> sariq
    r = client.get("/api/warehouses/fill-levels", headers=h)
    assert r.status_code == 200
    levels = r.json()["warehouses"]
    assert isinstance(levels, list)
    assert any(w["level"] in ("yashil", "sariq", "qizil") for w in levels)
    assert all("fill_percent" in w for w in levels)


# ================= ⏳ AMAL MUDDATI ESLATMASI =================

def test_inventory_expiring(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    session.add(models.RawMaterial(
        name="Sement xom", category="Sement", unit="tonna",
        current_stock=10, batch_number="B-2026",
        expiry_date=datetime.utcnow() + timedelta(days=5),
    ))
    session.add(models.RawMaterial(
        name="Qum", category="Qum", unit="tonna",
        current_stock=50, expiry_date=datetime.utcnow() + timedelta(days=200),
    ))
    session.commit()
    r = client.get("/api/inventory/expiring?days=30", headers=h)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "Sement xom"
    assert items[0]["status"] == "yaqinlashmoqda"
    assert 0 <= items[0]["days_left"] <= 5


# ================= 📅 XODIM SMENASI KALENDARI =================

def test_work_schedule(client, session):
    emp = _make_employee(session)
    h = _auth_headers(client)
    session.add(models.WorkHours(
        employee_id=emp.id, start_time=datetime.utcnow() - timedelta(hours=8),
        end_time=datetime.utcnow(), hours_worked=8.0, shift_type="day",
    ))
    session.commit()
    r = client.get("/api/work-schedule", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert "month" in data
    assert len(data["employees"]) == 1
    assert data["employees"][0]["total_hours"] >= 8.0


def test_work_schedule_month_param(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    r = client.get("/api/work-schedule?month=2026-01", headers=h)
    assert r.status_code == 200
    assert r.json()["month"] == "2026-01"


# ================= 📤 XODIM OCHIQ OPERATSIYALARI =================

def test_employee_open_operations(client, session):
    emp = _make_employee(session)
    h = _auth_headers(client)
    r = client.get(f"/api/employees/{emp.id}/open-operations", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["employee_id"] == emp.id
    assert "open_sales" in data
    assert "active_deliveries" in data
    assert "open_picking_lists" in data
    assert data["total_open_items"] == 0

    # Nasiya sotuvi qo'shilsa ochiq operatsiyalar oshishi kerak
    from database import crud
    product = _make_product(session)
    customer = models.Customer(name="Mijoz A", phone="+998900000001")
    session.add(customer)
    session.commit()
    sale = models.Sale(
        invoice_number="INV-1001", product_id=product.id, quantity=10,
        unit_price=1000, total_amount=10000, paid_amount=0,
        customer_id=customer.id, customer_name="Mijoz A",
        is_credit=True, credit_status="tolanmagan",
    )
    session.add(sale)
    session.commit()
    r = client.get(f"/api/employees/{emp.id}/open-operations", headers=h)
    assert len(r.json()["open_sales"]) == 1


def test_employee_open_operations_404(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    r = client.get("/api/employees/9999/open-operations", headers=h)
    assert r.status_code == 404


# ================= 🤔 "NIMA BO'LSA?" TAHLILI =================

def test_what_if_price_down(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    r = client.get("/api/analytics/what-if?scenario=price_down&percent=5", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["scenario"] == "price_down"
    assert data["percent"] == 5.0
    assert data["base_revenue"] >= 0
    assert "projected_revenue" in data
    assert "delta" in data


def test_what_if_invalid_scenario(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    r = client.get("/api/analytics/what-if?scenario=foo", headers=h)
    assert r.status_code == 422


# ================= 🔐 ROL CHEGARASI =================

def test_sotuvchi_cannot_analytics_or_vehicles(client, session):
    _make_employee(session)
    sotuvchi = _make_employee(session, name="Sotuvchi Test",
                              phone="+998901234568", role="sotuvchi",
                              is_admin=False)
    h = _auth_headers(client, phone="+998901234568")
    r = client.get("/api/analytics/what-if", headers=h)
    assert r.status_code == 403
    r = client.get("/api/vehicles", headers=h)
    assert r.status_code == 403
    r = client.post("/api/vehicles", headers=h, json={"number": "X 1"})
    assert r.status_code == 403


def test_haydovchi_can_view_vehicles(client, session):
    _make_employee(session)
    _make_employee(session, name="Haydovchi Test",
                   phone="+998901234569", role="haydovchi", is_admin=False)
    client.post("/api/vehicles", headers=_auth_headers(client),
                json={"number": "01 B 456 DD", "fuel_type": "dizel"})
    h = _auth_headers(client, phone="+998901234569")
    r = client.get("/api/vehicles", headers=h)
    assert r.status_code == 200
    assert len(r.json()["vehicles"]) == 1
    # Haydovchi o'zgartira olmaydi
    r = client.post("/api/vehicles", headers=h, json={"number": "X 2"})
    assert r.status_code == 403


# ================= 🚚 YETKAZIB BERISHDA MASHINA (v5.4, TZ ERD) =================

def _make_deliverable_sale(session, product, customer=None, qty=50):
    from database import crud
    if customer is None:
        customer = models.Customer(name="Dlv Mijoz", phone="+998900000009",
                                   address="Toshkent, Chilonzor")
        session.add(customer)
        session.commit()
        session.refresh(customer)
    return crud.create_sale_record(
        session, product_id=product.id, quantity=qty, unit_price=1000,
        total_amount=qty * 1000, payment_method="cash",
        customer=customer, customer_name=customer.name,
        customer_phone=customer.phone, user_id=1, user_name="Sotuvchi",
    )


def test_create_delivery_with_vehicle_api(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    driver = _make_employee(session, name="Haydovchi API",
                            phone="+998901234570", role="haydovchi", is_admin=False)
    p = _make_product(session)
    _add_income(session, p, 200)
    sale = _make_deliverable_sale(session, p)
    r = client.post("/api/vehicles", headers=h,
                    json={"number": "01 C 888 EE", "brand": "GAZ",
                          "capacity": 15000, "fuel_type": "gaz"})
    vid = r.json()["vehicle"]["id"]

    r = client.post("/api/deliveries", headers=h, json={
        "sale_id": sale.id, "driver_id": driver.id, "vehicle_id": vid,
    })
    assert r.status_code == 200, r.text
    delivery = r.json()["delivery"]
    assert delivery["vehicle_id"] == vid
    assert delivery["vehicle_number"] == "01 C 888 EE (GAZ)"

    # Ro'yxatda ham mashina ko'rinadi
    r = client.get("/api/deliveries", headers=h)
    assert r.status_code == 200
    found = [x for x in r.json()["deliveries"] if x["id"] == delivery["id"]]
    assert found and found[0]["vehicle_number"] == "01 C 888 EE (GAZ)"


def test_create_delivery_with_inactive_vehicle_api(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    driver = _make_employee(session, name="Haydovchi API2",
                            phone="+998901234571", role="haydovchi", is_admin=False)
    p = _make_product(session)
    _add_income(session, p, 200)
    sale = _make_deliverable_sale(session, p)
    r = client.post("/api/vehicles", headers=h, json={"number": "01 D 999 FF"})
    vid = r.json()["vehicle"]["id"]
    client.put(f"/api/vehicles/{vid}", headers=h, json={"status": "ta'mirda"})

    r = client.post("/api/deliveries", headers=h, json={
        "sale_id": sale.id, "driver_id": driver.id, "vehicle_id": vid,
    })
    assert r.status_code == 400


def test_create_delivery_without_vehicle_api(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    driver = _make_employee(session, name="Haydovchi API3",
                            phone="+998901234572", role="haydovchi", is_admin=False)
    p = _make_product(session)
    _add_income(session, p, 200)
    sale = _make_deliverable_sale(session, p)
    r = client.post("/api/deliveries", headers=h, json={
        "sale_id": sale.id, "driver_id": driver.id,
    })
    assert r.status_code == 200, r.text
    assert r.json()["delivery"]["vehicle_id"] is None