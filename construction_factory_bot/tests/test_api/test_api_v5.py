"""
REST API v5 testlari (construction_factory_bot.md "API METODLARI RO'YXATI" asosida):

- /api/auth/* aliaslar (login/logout/refresh/profile/verify-2fa)
- /api/users CRUD
- /api/products CRUD + search + low-stock + top-selling + import + narx tarixi
- /api/categories CRUD
- /api/customers (update/credit/debtors/orders)
- /api/orders (sotuv yaratish, status, reserve)
- /api/payments (list/create/daily)
- /api/inventory (adjust/history)
- /api/reports (daily/weekly/monthly/yearly/top-customers/category/export)
- /api/production (list/create/status), /api/warehouses CRUD
"""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import models, crud, crud_v5
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


def _make_product(session, name="G'isht", price=1200, category="G'isht"):
    p = models.Product(name=name, category=category, unit="dona",
                       selling_price=price, wholesale_price=price * 0.9,
                       production_cost=800, is_active=True)
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


# ================= /api/auth/* =================
def test_auth_profile_get_put(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    r = client.get("/api/auth/profile", headers=h)
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "direktor"
    r = client.put("/api/auth/profile", headers=h,
                   json={"full_name": "Direktor Yangilangan"})
    assert r.status_code == 200
    assert r.json()["user"]["full_name"] == "Direktor Yangilangan"


def test_auth_aliases_login_refresh_logout(client, session):
    _make_employee(session)
    r = client.post("/api/auth/login", json={"phone": "+998901234567",
                                             "password": "parol12345"})
    assert r.status_code == 200
    data = r.json()
    assert data["token"] and data["refresh_token"]
    r = client.post("/api/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert r.status_code == 200
    r = client.post("/api/auth/logout", json={"refresh_token": data["refresh_token"]})
    assert r.status_code == 200
    r = client.post("/api/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert r.status_code == 401


def test_auth_verify_2fa_off(client, session):
    _make_employee(session)
    r = client.post("/api/auth/verify-2fa", json={"phone": "+998901234567",
                                                  "otp_code": "123456"})
    assert r.status_code == 200
    assert r.json()["verified"] is False


# ================= /api/users =================
def test_users_crud(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    # ro'yxat
    r = client.get("/api/users", headers=h)
    assert r.status_code == 200
    assert len(r.json()["users"]) == 1
    # yaratish
    r = client.post("/api/users", headers=h, json={
        "full_name": "Yangi Sotuvchi", "phone_number": "+998901111222",
        "role": "sotuvchi", "salary": 3000000, "password": "parol12345",
    })
    assert r.status_code == 200, r.text
    uid = r.json()["user"]["id"]
    assert r.json()["user"]["role"] == "sotuvchi"
    # tahrirlash
    r = client.put(f"/api/users/{uid}", headers=h, json={"salary": 3500000})
    assert r.status_code == 200
    assert r.json()["user"]["salary"] == 3500000
    # status
    r = client.put(f"/api/users/{uid}/status", headers=h, json={"status": "bloklangan"})
    assert r.status_code == 200
    # parol
    r = client.put(f"/api/users/{uid}/password", headers=h, json={"password": "yangiParol99"})
    assert r.status_code == 200
    # o'chirish
    r = client.delete(f"/api/users/{uid}", headers=h)
    assert r.status_code == 200
    r = client.get(f"/api/users/{uid}", headers=h)
    assert r.status_code == 404


def test_users_create_duplicate_phone(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    r = client.post("/api/users", headers=h, json={
        "full_name": "Takror", "phone_number": "+998901234567", "role": "sotuvchi"})
    assert r.status_code == 400


def test_users_invalid_role(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    r = client.post("/api/users", headers=h, json={
        "full_name": "X", "phone_number": "+998902222333", "role": "yoqdir"})
    assert r.status_code == 400


# ================= /api/products =================
def test_products_crud_and_search(client, session):
    _make_employee(session)
    p = _make_product(session)
    h = _auth_headers(client)
    r = client.get("/api/products", headers=h)
    assert r.status_code == 200
    assert any(x["id"] == p.id for x in r.json()["products"])
    r = client.get("/api/products/search", params={"q": "G'ish"}, headers=h)
    assert r.status_code == 200
    assert len(r.json()["products"]) == 1
    # yaratish
    r = client.post("/api/products", headers=h, json={
        "name": "Sement 50kg", "category": "Sement", "unit": "qop",
        "selling_price": 85000, "production_cost": 70000})
    assert r.status_code == 200, r.text
    pid = r.json()["product"]["id"]
    # tahrirlash
    r = client.put(f"/api/products/{pid}", headers=h, json={"description": "M500"})
    assert r.status_code == 200
    assert r.json()["product"]["description"] == "M500"
    # narx tarixi
    r = client.put(f"/api/products/{pid}/price", headers=h,
                   json={"new_price": 90000, "price_type": "selling",
                         "reason": "Test"})
    assert r.status_code == 200
    r = client.get(f"/api/products/{pid}/price-history", headers=h)
    assert r.status_code == 200
    hist = r.json()["price_history"]
    assert len(hist) == 1
    assert hist[0]["old_price"] == 85000
    assert hist[0]["new_price"] == 90000
    # qoldiq tuzatish
    r = client.put(f"/api/products/{pid}/stock", headers=h, json={"delta": 100})
    assert r.status_code == 200
    assert r.json()["available_qty"] == 100


def test_products_import(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    r = client.post("/api/products/import", headers=h, json={"products": [
        {"name": "Armatura 12", "category": "Metall", "unit": "tonna",
         "selling_price": 6000000},
        {"name": "Qum", "category": "Qum", "unit": "m3", "selling_price": 120000},
        {"name": "Armatura 12", "category": "Metall", "unit": "tonna",
         "selling_price": 6100000},
    ]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 2
    assert body["updated"] == 1


def test_products_low_stock_top_selling(client, session):
    _make_employee(session)
    p = _make_product(session)
    h = _auth_headers(client)
    r = client.get("/api/products/low-stock", headers=h)
    assert r.status_code == 200
    assert any(x["id"] == p.id for x in r.json()["products"])
    r = client.get("/api/products/top-selling", headers=h)
    assert r.status_code == 200


# ================= /api/categories =================
def test_categories_crud(client, session):
    _make_employee(session)
    _make_product(session)
    h = _auth_headers(client)
    r = client.get("/api/categories", headers=h)
    assert r.status_code == 200
    assert {"name": "G'isht"} in r.json()["categories"]
    r = client.post("/api/categories", headers=h, json={"name": "Metall"})
    assert r.status_code == 200
    r = client.put("/api/categories/G'isht", headers=h, json={"new_name": "Blok"})
    assert r.status_code == 200
    assert r.json()["renamed"] == 1
    r = client.delete("/api/categories/Blok", headers=h)
    assert r.status_code == 200
    assert r.json()["products"] == 1


# ================= /api/customers =================
def test_customers_update_credit_debtors_orders(client, session):
    _make_employee(session)
    c = _make_customer(session, debt=500000)
    h = _auth_headers(client)
    r = client.put(f"/api/customers/{c.id}", headers=h, json={"company": "OOO Test"})
    assert r.status_code == 200
    r = client.put(f"/api/customers/{c.id}/credit", headers=h,
                   json={"credit_limit": 20000000})
    assert r.status_code == 200
    assert r.json()["customer"]["credit_limit"] == 20000000
    r = client.get("/api/customers/debtors", headers=h)
    assert r.status_code == 200
    assert any(x["id"] == c.id for x in r.json()["debtors"])
    r = client.get(f"/api/customers/{c.id}/orders", headers=h)
    assert r.status_code == 200
    assert r.json()["orders"] == []


# ================= /api/orders (sotuv) =================
def test_orders_create_sale_and_status(client, session):
    _make_employee(session)
    p = _make_product(session)
    c = _make_customer(session)
    h = _auth_headers(client)
    r = client.post("/api/orders", headers=h, json={
        "product_id": p.id, "quantity": 10, "unit_price": 1200,
        "customer_id": c.id, "payment_method": "cash",
    })
    assert r.status_code == 200, r.text
    order = r.json()["order"]
    assert order["total_amount"] == 12000
    assert order["paid_amount"] == 12000
    # status
    r = client.put(f"/api/orders/{order['invoice_number']}/status", headers=h,
                   json={"status": "cancelled"})
    assert r.status_code == 200
    # ro'yxat
    r = client.get("/api/orders/sales", headers=h)
    assert r.status_code == 200
    assert len(r.json()["orders"]) == 1
    # bekor
    r = client.delete(f"/api/orders/{order['invoice_number']}", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


def test_orders_credit_mixed(client, session):
    _make_employee(session)
    p = _make_product(session)
    h = _auth_headers(client)
    r = client.post("/api/orders", headers=h, json={
        "product_id": p.id, "quantity": 5, "unit_price": 1000,
        "payments": [{"method": "cash", "amount": 2000},
                     {"method": "credit", "amount": 3000}],
    })
    assert r.status_code == 200, r.text
    order = r.json()["order"]
    assert order["is_credit"] is True
    assert order["paid_amount"] == 2000


def test_orders_reserve(client, session):
    _make_employee(session)
    p = _make_product(session)
    h = _auth_headers(client)
    # avval zaxira qo'shamiz (sotuvdan keyin qoldiq kamayadi)
    r = client.put("/api/inventory/adjust", headers=h, json={
        "item_type": "product", "item_id": p.id, "delta": 100})
    assert r.status_code == 200
    r = client.post("/api/orders", headers=h, json={
        "product_id": p.id, "quantity": 3, "unit_price": 1000})
    order = r.json()["order"]
    r = client.post(f"/api/orders/{order['invoice_number']}/reserve", headers=h,
                    json={"hours": 5})
    assert r.status_code == 200, r.text
    reservation = r.json()["reservation"]
    assert reservation["quantity"] == 3
    r = client.put(f"/api/orders/{order['invoice_number']}/cancel-reserve", headers=h,
                   json={"reservation_id": reservation["id"]})
    assert r.status_code == 200


# ================= /api/payments =================
def test_payments_list_create_daily(client, session):
    _make_employee(session)
    c = _make_customer(session, debt=1000000)
    p = _make_product(session)
    h = _auth_headers(client)
    r = client.post("/api/orders", headers=h, json={
        "product_id": p.id, "quantity": 2, "unit_price": 5000,
        "customer_id": c.id, "payments": [{"method": "cash", "amount": 3000},
                                          {"method": "credit", "amount": 7000}]})
    sale_id = r.json()["order"]["id"]
    r = client.post("/api/payments", headers=h, json={
        "sale_id": sale_id, "amount": 2000, "method": "card"})
    assert r.status_code == 200, r.text
    r = client.get("/api/payments", headers=h)
    assert r.status_code == 200
    assert len(r.json()["payments"]) >= 1
    r = client.get("/api/payments/daily", headers=h)
    assert r.status_code == 200
    assert r.json()["total"] >= 2000


# ================= /api/inventory =================
def test_inventory_adjust_history(client, session):
    _make_employee(session)
    p = _make_product(session)
    h = _auth_headers(client)
    r = client.get("/api/inventory", headers=h)
    assert r.status_code == 200
    assert any(x["id"] == p.id for x in r.json()["products"])
    r = client.get(f"/api/inventory/{p.id}", headers=h)
    assert r.status_code == 200
    r = client.put("/api/inventory/adjust", headers=h, json={
        "item_type": "product", "item_id": p.id, "delta": 50,
        "reason": "Test tuzatish"})
    assert r.status_code == 200
    r = client.get(f"/api/inventory/{p.id}", headers=h)
    assert r.json()["available_qty"] == 50
    r = client.get("/api/inventory/history", headers=h)
    assert r.status_code == 200
    assert any(h["item_type"] == "product" for h in r.json()["history"])


# ================= /api/reports =================
def test_reports_periods(client, session):
    _make_employee(session)
    p = _make_product(session)
    h = _auth_headers(client)
    client.post("/api/orders", headers=h, json={
        "product_id": p.id, "quantity": 10, "unit_price": 1200})
    for path in ["/api/reports/daily", "/api/reports/weekly",
                 "/api/reports/monthly", "/api/reports/yearly",
                 "/api/reports/profit-loss", "/api/reports/debt",
                 "/api/reports/top-customers", "/api/reports/sales-by-category"]:
        r = client.get(path, headers=h)
        assert r.status_code == 200, f"{path}: {r.status_code} {r.text}"
    r = client.get("/api/reports/daily", headers=h)
    assert r.json()["total_amount"] == 12000
    assert r.json()["sales_count"] == 1


def test_reports_export(client, session):
    _make_employee(session)
    p = _make_product(session)
    h = _auth_headers(client)
    client.post("/api/orders", headers=h, json={
        "product_id": p.id, "quantity": 5, "unit_price": 1000})
    r = client.post("/api/reports/export", headers=h, json={"report": "sales"})
    assert r.status_code == 200
    assert "invoice_number" in r.text
    r = client.post("/api/reports/export", headers=h, json={"report": "daily", "format": "json"})
    assert r.status_code == 200
    assert r.json()["success"] is True


# ================= /api/production =================
def test_production_list_create_status(client, session):
    _make_employee(session)
    p = _make_product(session)
    h = _auth_headers(client)
    r = client.post("/api/production", headers=h, json={
        "product_id": p.id, "quantity": 1000, "priority": 2})
    assert r.status_code == 200, r.text
    order_id = r.json()["production_order"]["id"]
    assert r.json()["production_order"]["order_number"].startswith("PO-")
    r = client.put(f"/api/production/{order_id}/status", headers=h,
                   json={"status": "jarayonda"})
    assert r.status_code == 200
    r = client.get("/api/production", headers=h)
    assert r.status_code == 200
    assert len(r.json()["production_orders"]) == 1
    assert r.json()["production_orders"][0]["status"] == "jarayonda"


# ================= /api/warehouses =================
def test_warehouses_crud(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    r = client.get("/api/warehouses", headers=h)
    assert r.status_code == 200
    r = client.post("/api/warehouses", headers=h, json={
        "name": "Xomashyo ombori", "warehouse_type": "xomashyo",
        "address": "Toshkent", "sectors": "A1,B2"})
    assert r.status_code == 200, r.text
    wid = r.json()["warehouse"]["id"]
    r = client.put(f"/api/warehouses/{wid}", headers=h, json={"manager_name": "Ali"})
    assert r.status_code == 200
    assert r.json()["warehouse"]["manager_name"] == "Ali"
    r = client.get("/api/warehouses", headers=h)
    assert any(w["id"] == wid for w in r.json()["warehouses"])


# ================= /api/deliveries imzo =================
def test_delivery_signature(client, session):
    _make_employee(session)
    driver = models.Employee(
        full_name="Haydovchi Test", phone_number="+998903333444",
        position="Haydovchi", department="delivery",
        hire_date=datetime.utcnow(), role="haydovchi", is_admin=False,
    )
    session.add(driver)
    session.commit()
    session.refresh(driver)
    p = _make_product(session)
    c = _make_customer(session)
    h = _auth_headers(client)
    r = client.post("/api/orders", headers=h, json={
        "product_id": p.id, "quantity": 2, "unit_price": 1000, "customer_id": c.id})
    sale_id = r.json()["order"]["id"]
    r = client.post("/api/deliveries", headers=h, json={
        "sale_id": sale_id, "driver_id": driver.id, "quantity": 2})
    assert r.status_code == 200, r.text
    did = r.json()["delivery"]["id"]
    r = client.post(f"/api/deliveries/{did}/signature", headers=h, json={
        "signature_name": "Mijoz A", "signature_type": "pin"})
    assert r.status_code == 200, r.text
    assert r.json()["signature_name"] == "Mijoz A"