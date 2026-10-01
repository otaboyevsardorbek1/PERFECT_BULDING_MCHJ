"""
v5.2 testlari — spec (v.3.0 yangi 3-bo'lim FUNKSIONAL MODULLAR) bo'yicha:

- 💰 Mijoz maxsus narxlari (3.1: "maxsus mijoz narxlari") — CRUD + sotuvda qo'llanishi
- 📉 Mahsulot minimal zaxirasi (3.1: "Minimal zaxira") — `min_stock`, low-stock
- 🔖 Partiya va sertifikat (3.2: "Partiya va seriya raqamlari") — qabul aktida
"""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import models, crud
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
        full_name=name, phone_number=phone, position="Direktor",
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


def _make_product(session, name="G'isht", price=1200, category="G'isht", min_stock=0):
    p = models.Product(name=name, category=category, unit="dona",
                       selling_price=price, wholesale_price=price * 0.9,
                       production_cost=800, is_active=True, min_stock=min_stock)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def _make_customer(session, name="Mijoz A", phone="+998900000001", debt=0):
    c = models.Customer(name=name, phone=phone, total_debt=debt)
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


# ================= 💰 MIJOZ MAXSUS NARXLARI =================

def test_customer_price_set_get_update(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    customer = _make_customer(session)
    product = _make_product(session, price=1200)

    r = client.put(f"/api/customers/{customer.id}/prices", headers=h,
                   json={"product_id": product.id, "price": 950})
    assert r.status_code == 200, r.text
    assert r.json()["price"]["price"] == 950

    r = client.get(f"/api/customers/{customer.id}/prices", headers=h)
    assert r.status_code == 200, r.text
    prices = r.json()["prices"]
    assert len(prices) == 1
    assert prices[0]["product_id"] == product.id
    assert prices[0]["product_name"] == "G'isht"
    assert prices[0]["price"] == 950

    # yangilash (bir xil juftlik)
    r = client.put(f"/api/customers/{customer.id}/prices", headers=h,
                   json={"product_id": product.id, "price": 900})
    assert r.status_code == 200
    assert r.json()["price"]["price"] == 900
    assert len(client.get(f"/api/customers/{customer.id}/prices", headers=h).json()["prices"]) == 1


def test_customer_price_validation(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    customer = _make_customer(session)
    r = client.put(f"/api/customers/{customer.id}/prices", headers=h,
                   json={"product_id": 99999, "price": 950})
    assert r.status_code == 400
    product = _make_product(session)
    r = client.put(f"/api/customers/{customer.id}/prices", headers=h,
                   json={"product_id": product.id, "price": -5})
    assert r.status_code == 400


def test_customer_price_used_in_order(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    customer = _make_customer(session)
    product = _make_product(session, price=1200)
    client.put(f"/api/customers/{customer.id}/prices", headers=h,
               json={"product_id": product.id, "price": 950})
    r = client.post("/api/orders", headers=h, json={
        "product_id": product.id, "quantity": 10,
        "customer_id": customer.id, "payment_method": "cash",
    })
    assert r.status_code == 200, r.text
    order = r.json()["order"]
    assert order["total_amount"] == 9500  # 10 x 950 maxsus narx


def test_customer_price_delete(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    customer = _make_customer(session)
    product = _make_product(session)
    client.put(f"/api/customers/{customer.id}/prices", headers=h,
               json={"product_id": product.id, "price": 900})
    r = client.delete(f"/api/customers/{customer.id}/prices/{product.id}", headers=h)
    assert r.status_code == 200
    assert client.get(f"/api/customers/{customer.id}/prices", headers=h).json()["prices"] == []
    r = client.delete(f"/api/customers/{customer.id}/prices/{product.id}", headers=h)
    assert r.status_code == 404


# ================= 📉 MINIMAL ZAXIRA (min_stock) =================

def test_product_min_stock_in_dict(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    _make_product(session, min_stock=150)
    r = client.get("/api/products", headers=h)
    assert r.status_code == 200, r.text
    prod = r.json()["products"][0]
    assert prod["min_stock"] == 150


def test_low_stock_uses_min_stock_threshold(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    product = _make_product(session, min_stock=100)
    # 50 dona ishlab chiqarilgan -> qoldiq 50 < min_stock 100
    session.add(models.WarehouseTransaction(
        product_id=product.id, quantity=50,
        transaction_type=models.TransactionType.PRODUCTION,
        user_id=0, user_name="Test"))
    session.commit()
    r = client.get("/api/products/low-stock", headers=h)
    assert r.status_code == 200, r.text
    products = r.json()["products"]
    assert any(p["id"] == product.id for p in products)


# ================= 🔖 PARTIYA VA SERTIFIKAT =================

def test_supplier_delivery_sets_batch_fields(session):
    supplier = models.Supplier(name="Yetkazib A", phone="+998900000010")
    session.add(supplier)
    session.commit()
    session.refresh(supplier)
    material = models.RawMaterial(
        name="Sement", category="Bog'lovchi", unit="kg",
        current_stock=0, min_stock=1000,
    )
    session.add(material)
    session.commit()
    session.refresh(material)

    delivery = crud.create_supplier_delivery(
        session,
        supplier_id=supplier.id, raw_material_id=material.id,
        quantity_ordered=5000, quantity_received=5000,
        quality_status="qabul_qilingan", price_per_unit=850,
        created_by="Direktor Test",
        batch_number="B-2026-001", certificate_number="SER-778899",
        expiry_date=(datetime.utcnow() + timedelta(days=365)).isoformat(),
    )
    assert delivery.act_number
    session.refresh(material)
    assert material.batch_number == "B-2026-001"
    assert material.certificate_number == "SER-778899"
    assert material.expiry_date is not None
    assert material.current_stock == 5000
    assert material.supplier_id == supplier.id


def test_receipt_api_returns_batch_fields(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    supplier = models.Supplier(name="Yetkazib B", phone="+998900000011")
    session.add(supplier)
    session.commit()
    session.refresh(supplier)
    material = models.RawMaterial(
        name="Armatura", category="Metall", unit="t",
        current_stock=0, min_stock=5,
    )
    session.add(material)
    session.commit()
    session.refresh(material)
    r = client.post("/api/receipts", headers=h, json={
        "supplier_id": supplier.id, "raw_material_id": material.id,
        "quantity_ordered": 10, "quantity_received": 10,
        "price_per_unit": 6000000, "batch_number": "B-2026-ARM-1",
    })
    assert r.status_code == 200, r.text
    r = client.get("/api/receipts", headers=h)
    assert r.status_code == 200, r.text
    receipt = r.json()["receipts"][0]
    assert receipt["batch_number"] == "B-2026-ARM-1"