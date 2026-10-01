"""
v5.1 testlari — TZ'dagi qolgan bo'shliqlar:

- 🔖 Tranzaksiya kodi (TZ A-bo'lim): har bir operatsiyaga unikal 16 xonali kod,
  `/api/documents/lookup` orqali hujjatni topish
- 📎 Avans hisoboti fotosurati (TZ A-bo'lim): `photo_path` saqlash
- 🔒 Mijozlar ma'lumotlari rol bo'yicha yashirish (TZ F-bo'lim):
  sotuvchi telefon/manzilni ko'rmaydi, direktor/haydovchi to'liq ko'radi
"""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import models, crud
from database.session import get_db
from dashboard.auth import get_current_user, set_employee_password
from utils.transaction_codes import make_transaction_code, is_valid_transaction_code


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


def _create_sale(client, session, headers=None, product=None, customer=None):
    headers = headers or _auth_headers(client)
    product = product or _make_product(session)
    payload = {
        "product_id": product.id, "quantity": 10, "payment_method": "cash",
    }
    if customer:
        payload["customer_id"] = customer.id
    else:
        payload["customer_name"] = "Mijoz A"
    r = client.post("/api/orders", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["order"]


# ================= 🔖 TRANZAKSIYA KODI =================

def test_make_transaction_code_format():
    for _ in range(5):
        code = make_transaction_code()
        assert is_valid_transaction_code(code)
        assert len(code) == 16 and code.isdigit()
    # ikki xil kod takrorlanmasligi kerak
    codes = {make_transaction_code() for _ in range(50)}
    assert len(codes) == 50


def test_sale_gets_transaction_code(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    order = _create_sale(client, session)
    assert order["transaction_code"] and len(order["transaction_code"]) == 16
    assert order["transaction_code"].isdigit()


def test_document_lookup_finds_sale(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    order = _create_sale(client, session)
    r = client.get(f"/api/documents/lookup?code={order['transaction_code']}", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["found"] is True
    assert data["type"] == "sale"
    assert data["document"]["invoice_number"] == order["invoice_number"]
    assert data["document"]["transaction_code"] == order["transaction_code"]


def test_document_lookup_finds_return_act(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    order = _create_sale(client, session)
    sale = session.query(models.Sale).first()
    act = crud.create_return_act(
        session, sale_id=sale.id, quantity=2, reason="brak",
        refund_type="cash", user_id=0, user_name="Direktor Test",
    )
    r = client.get(f"/api/documents/lookup?code={act.transaction_code}", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["type"] == "return_act"
    assert data["document"]["act_number"] == act.act_number


def test_document_lookup_finds_warehouse_transaction(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    product = _make_product(session)
    txn = models.WarehouseTransaction(
        product_id=product.id, quantity=500,
        transaction_type=models.TransactionType.INCOME,
        user_id=0, user_name="Test", document_number="QAB-001",
    )
    session.add(txn)
    session.commit()
    session.refresh(txn)
    r = client.get(f"/api/documents/lookup?code={txn.transaction_code}", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["type"] == "warehouse_transaction"


def test_document_lookup_validation(client, session):
    _make_employee(session)
    h = _auth_headers(client)
    r = client.get("/api/documents/lookup?code=123", headers=h)
    assert r.status_code == 400
    r = client.get("/api/documents/lookup?code=9999999999999999", headers=h)
    assert r.status_code == 404


# ================= 📎 AVANS FOTOSURATI =================

def test_expense_photo_path(session):
    """Avans hisobotiga foto crud qatlamida saqlanadi (bot yo'nalishi)."""
    report = crud.create_expense_report(session, {
        "employee_name": "Haydovchi",
        "category": "yoqilgi",
        "amount": 150000,
        "description": "Toshkent yo'li",
        "photo_path": "uploads/expenses/exp_abc123.jpg",
    })
    assert report.photo_path == "uploads/expenses/exp_abc123.jpg"
    got = session.query(models.ExpenseReport).first()
    assert got.photo_path == "uploads/expenses/exp_abc123.jpg"
    assert got.amount == 150000


# ================= 🔒 MIJOZ MA'LUMOTLARINI YASHIRISH =================

def test_customer_phone_masked_for_seller(client, session):
    _make_employee(session, name="Sotuvchi A", phone="+998900000002",
                   role="sotuvchi", is_admin=False)
    _make_customer(session, name="Mijoz A", phone="+998900000001")
    h = _auth_headers(client, phone="+998900000002")
    r = client.get("/api/customers", headers=h)
    assert r.status_code == 200, r.text
    customer = r.json()["customers"][0]
    assert customer["phone"] != "+998900000001"
    assert "***" in customer["phone"]
    assert customer["address"] is None
    assert customer["notes"] is None
    assert customer["phone_masked"] is True
    # ism va qarz ko'rinadi
    assert customer["name"] == "Mijoz A"
    assert "total_debt" in customer


def test_customer_phone_full_for_director(client, session):
    _make_employee(session)
    _make_customer(session, name="Mijoz A", phone="+998900000001")
    h = _auth_headers(client)
    r = client.get("/api/customers", headers=h)
    assert r.status_code == 200, r.text
    customer = r.json()["customers"][0]
    assert customer["phone"] == "+998900000001"
    assert "phone_masked" not in customer


def test_customer_phone_masked_in_debtors(client, session):
    _make_employee(session, name="Sotuvchi B", phone="+998900000003",
                   role="sotuvchi", is_admin=False)
    _make_customer(session, name="Qarzdor", phone="+998900000001", debt=500000)
    h = _auth_headers(client, phone="+998900000003")
    r = client.get("/api/customers/debtors", headers=h)
    assert r.status_code == 200, r.text
    d = r.json()["debtors"][0]
    assert "***" in d["phone"]
    assert d["total_debt"] == 500000