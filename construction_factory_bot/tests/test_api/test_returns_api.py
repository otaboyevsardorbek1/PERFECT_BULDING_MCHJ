"""
QAYTARISH AKTI REST API testlari:
- GET /api/returns/candidates — qaytarishga yaroqli sotuvlar
- POST /api/returns — akt yaratish (pul / almashtirish)
- GET /api/returns, GET /api/returns/{id}
- Validatsiya xatolari (qoldiqdan oshsa -> 400)
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import models, crud
from database.session import get_db


@pytest.fixture
def session():
    """Thread-safe in-memory SQLite — TestClient alohida thread'da ishlaydi"""
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
    """In-memory DB ishlatadigan TestClient (rol: direktor — conftest override'i)"""
    from dashboard.app import app

    def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sale_fixture(session):
    """Mahsulot + naqd to'langan sotuv"""
    p = models.Product(name="API Ret Sement", category="sement", unit="qop",
                       selling_price=12000, production_cost=7000, is_active=True)
    session.add(p)
    session.commit()
    session.refresh(p)

    session.add(models.WarehouseTransaction(
        product_id=p.id, quantity=300, transaction_type=models.TransactionType.PRODUCTION,
        user_id=1, user_name="Test",
    ))
    session.commit()

    customer = crud.create_customer(session, {
        "name": "API Mijoz", "phone": "+998908881122", "credit_limit": 5_000_000,
    })
    sale = crud.create_sale_record(
        session, product_id=p.id, quantity=10, unit_price=12000,
        total_amount=120_000, payment_method="cash",
        customer=customer, customer_name=customer.name,
        user_id=7, user_name="Sotuvchi",
    )
    return {"product": p, "customer": customer, "sale": sale}


class TestReturnCandidates:
    def test_candidates_lists_returnable_sale(self, client, sale_fixture):
        r = client.get("/api/returns/candidates")
        assert r.status_code == 200
        cands = r.json()["candidates"]
        assert len(cands) >= 1
        top = cands[0]
        assert top["id"] == sale_fixture["sale"].id
        assert top["invoice_number"] == sale_fixture["sale"].invoice_number
        assert top["remaining"] == 10
        assert top["eligible"] is True


class TestCreateReturn:
    def test_create_cash_return(self, client, sale_fixture):
        sale = sale_fixture["sale"]
        r = client.post("/api/returns", json={
            "sale_id": sale.id, "quantity": 4,
            "reason": "notogri", "refund_type": "cash",
        })
        assert r.status_code == 200
        act = r.json()["return_act"]
        assert act["act_number"].startswith("RTN-")
        assert act["refund_amount"] == 48_000
        assert act["quantity"] == 4
        assert act["reason_label"] == "Noto'g'ri mahsulot"

        # Sotuvda qolgan qism keyingi qaytarishda hisobga olinadi
        r2 = client.post("/api/returns", json={
            "sale_id": sale.id, "quantity": 10, "refund_type": "cash",
        })
        assert r2.status_code == 400  # qoldiq 6 dan oshdi

    def test_create_exchange_return(self, client, sale_fixture, session):
        sale = sale_fixture["sale"]
        other = models.Product(name="API Kafel", category="kafel", unit="dona",
                               selling_price=6000, production_cost=3000, is_active=True)
        session.add(other)
        session.commit()
        session.refresh(other)

        r = client.post("/api/returns", json={
            "sale_id": sale.id, "quantity": 10,
            "reason": "mijoz_istagi", "refund_type": "exchange",
            "exchange_product_id": other.id, "exchange_quantity": 10,
            "refund_method": "cash",
        })
        assert r.status_code == 200
        act = r.json()["return_act"]
        assert act["exchange_product_name"] == other.name
        assert act["refund_amount"] == 60_000  # 120k - 60k farq qaytariladi
        assert act["tradein_amount"] == 60_000

    def test_create_return_invalid_quantity(self, client, sale_fixture):
        r = client.post("/api/returns", json={
            "sale_id": sale_fixture["sale"].id, "quantity": -5,
            "refund_type": "cash",
        })
        assert r.status_code == 400

    def test_create_return_missing_sale(self, client):
        r = client.post("/api/returns", json={
            "sale_id": 999999, "quantity": 1, "refund_type": "cash",
        })
        assert r.status_code == 400


class TestListReturns:
    def test_list_and_detail(self, client, sale_fixture):
        client.post("/api/returns", json={
            "sale_id": sale_fixture["sale"].id, "quantity": 3,
            "refund_type": "bonus",
        })
        r = client.get("/api/returns")
        assert r.status_code == 200
        returns = r.json()["returns"]
        assert len(returns) == 1
        assert returns[0]["refund_type"] == "bonus"

        rid = returns[0]["id"]
        detail = client.get(f"/api/returns/{rid}")
        assert detail.status_code == 200
        assert detail.json()["return_act"]["id"] == rid

        missing = client.get("/api/returns/999999")
        assert missing.status_code == 404
