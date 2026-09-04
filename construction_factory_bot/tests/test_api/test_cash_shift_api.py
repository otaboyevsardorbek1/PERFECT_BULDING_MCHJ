"""
KASSIR SMENASI REST API testlari:
- GET /api/cash-shifts, /current
- POST /api/cash-shifts/open
- POST /api/cash-shifts/{id}/close (farq hisoblanadi)
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
def sale_data(session):
    p = models.Product(name="API Shift Sement", category="sement", unit="qop",
                       selling_price=12000, production_cost=7000, is_active=True)
    session.add(p)
    session.commit()
    session.refresh(p)
    customer = crud.create_customer(session, {
        "name": "API Shift Mijoz", "phone": "+998901234566", "credit_limit": 5_000_000,
    })
    return p, customer


class TestCashShiftAPI:
    def test_open_list_current_close_flow(self, client, session, sale_data):
        p, customer = sale_data
        # Joriy ochiq smena yo'q
        cur = client.get("/api/cash-shifts/current")
        assert cur.status_code == 200
        assert cur.json()["shift"] is None

        # Smena ochish
        opened = client.post("/api/cash-shifts/open", json={"opening_balance": 300_000})
        assert opened.status_code == 200
        shift = opened.json()["shift"]
        assert shift["status"] == "ochiq"
        assert shift["opening_balance"] == 300_000

        # Ikkinchi smena ochib bo'lmaydi
        second = client.post("/api/cash-shifts/open", json={"opening_balance": 0})
        assert second.status_code == 400

        # Naqd sotuv -> kutilgan 300k + 1.2M
        crud.create_sale_record(
            session, product_id=p.id, quantity=100, unit_price=12000,
            total_amount=1_200_000, payment_method="cash",
            customer=customer, customer_name=customer.name,
            user_id=7, user_name="Kassir",
        )

        cur2 = client.get("/api/cash-shifts/current")
        assert cur2.status_code == 200
        assert cur2.json()["summary"]["expected_cash"] == 1_500_000

        # Yopish: 1.5M sanalgan -> farq 0
        closed = client.post(f"/api/cash-shifts/{shift['id']}/close",
                             json={"actual_cash": 1_500_000})
        assert closed.status_code == 200
        data = closed.json()["shift"]
        assert data["status"] == "yopilgan"
        assert data["difference"] == 0

        # Qayta yopish -> 400
        again = client.post(f"/api/cash-shifts/{shift['id']}/close",
                            json={"actual_cash": 1_500_000})
        assert again.status_code == 400

        # Ro'yxatda bitta yopilgan smena
        lst = client.get("/api/cash-shifts?status=yopilgan")
        assert lst.status_code == 200
        assert len(lst.json()["shifts"]) == 1
