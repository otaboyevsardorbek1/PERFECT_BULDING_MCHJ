"""
OMMAVIY WEB-DO'KON REST API testlari (auth talab qilmaydi):
- GET /api/shop/catalog, /categories
- POST /api/shop/orders (naqd, onlayn va aralash Click/Payme + Naqd)
- GET /api/shop/orders/{number}?phone= (holat tekshiruvi)
- POST /api/shop/orders/{number}/cancel
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
def catalog(session):
    p1 = models.Product(name="API Do'kon Sement", category="sement", unit="qop",
                        selling_price=12000, production_cost=7000, is_active=True)
    p2 = models.Product(name="API Do'kon Kafel", category="kafel", unit="dona",
                        selling_price=8000, production_cost=4000, is_active=True)
    session.add_all([p1, p2])
    session.flush()
    for p in (p1, p2):
        session.add(models.WarehouseTransaction(
            product_id=p.id, quantity=100, transaction_type=models.TransactionType.PRODUCTION,
            user_id=1, user_name="Test",
        ))
    session.commit()
    session.refresh(p1)
    session.refresh(p2)
    return p1, p2


class TestCatalog:
    def test_catalog_lists_products_with_stock(self, client, catalog):
        p1, _ = catalog
        r = client.get("/api/shop/catalog")
        assert r.status_code == 200
        products = r.json()["products"]
        assert any(x["name"] == p1.name for x in products)
        top = next(x for x in products if x["id"] == p1.id)
        assert top["available"] == 100
        assert top["price"] == 12000
        assert top["unit"] == "qop"

    def test_catalog_category_filter(self, client, catalog):
        r = client.get("/api/shop/catalog?category=kafel")
        assert r.status_code == 200
        names = [x["name"] for x in r.json()["products"]]
        assert names == ["API Do'kon Kafel"]

    def test_categories(self, client, catalog):
        r = client.get("/api/shop/categories")
        assert r.status_code == 200
        cats = {c["name"]: c["products"] for c in r.json()["categories"]}
        assert cats.get("sement") == 1
        assert cats.get("kafel") == 1


class TestOrders:
    def test_cash_checkout(self, client, catalog):
        p1, p2 = catalog
        r = client.post("/api/shop/orders", json={
            "name": "API Mijoz", "phone": "+998 90 555 66 77",
            "address": "Toshkent", "method": "cash",
            "items": [{"product_id": p1.id, "quantity": 2},
                      {"product_id": p2.id, "quantity": 3}],
        })
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "yakunlangan"
        order = body["order"]
        assert order["order_number"].startswith("SHOP-")
        assert order["total_amount"] == 2 * 12000 + 3 * 8000
        assert len(order["items"]) == 2
        assert "payment_link" not in body

    def test_online_checkout_returns_payment_link(self, client, catalog, monkeypatch):
        p1, _ = catalog
        from dashboard import payments as p_mod
        monkeypatch.setattr(p_mod, "CLICK_MERCHANT_ID", "12345")
        monkeypatch.setattr(p_mod, "CLICK_SERVICE_ID", "67890")
        monkeypatch.setattr(p_mod, "CLICK_SECRET_KEY", "SECRET")

        r = client.post("/api/shop/orders", json={
            "name": "API Onlayn", "phone": "+998901112233",
            "method": "click",
            "items": [{"product_id": p1.id, "quantity": 1}],
        })
        assert r.status_code == 200
        body = r.json()
        assert body["order"]["status"] == "kutilmoqda"
        assert body["invoice_id"].startswith("INV-")
        assert "my.click.uz/services/pay" in body["payment_link"]

    def test_online_without_configured_gateway_503(self, client, catalog):
        p1, _ = catalog
        r = client.post("/api/shop/orders", json={
            "name": "API Onlayn", "phone": "+998901112233",
            "method": "payme",
            "items": [{"product_id": p1.id, "quantity": 1}],
        })
        assert r.status_code == 503

    def test_checkout_over_stock_400(self, client, catalog):
        p1, _ = catalog
        r = client.post("/api/shop/orders", json={
            "name": "M", "phone": "+998901112233", "method": "cash",
            "items": [{"product_id": p1.id, "quantity": 999}],
        })
        assert r.status_code == 400

    def test_order_status_lookup(self, client, catalog):
        p1, _ = catalog
        r = client.post("/api/shop/orders", json={
            "name": "API Holat", "phone": "+998901112244", "method": "cash",
            "items": [{"product_id": p1.id, "quantity": 1}],
        })
        number = r.json()["order"]["order_number"]

        ok = client.get(f"/api/shop/orders/{number}?phone=%2B998901112244")
        assert ok.status_code == 200
        assert ok.json()["order"]["status"] == "yakunlangan"

        # Noto'g'ri telefon -> 403
        bad = client.get(f"/api/shop/orders/{number}?phone=%2B998000000000")
        assert bad.status_code == 403

        missing = client.get("/api/shop/orders/SHOP-XXXX")
        assert missing.status_code == 404

    def test_cancel_pending_order(self, client, catalog, monkeypatch):
        p1, _ = catalog
        from dashboard import payments as p_mod
        monkeypatch.setattr(p_mod, "CLICK_MERCHANT_ID", "12345")
        monkeypatch.setattr(p_mod, "CLICK_SERVICE_ID", "67890")
        monkeypatch.setattr(p_mod, "CLICK_SECRET_KEY", "SECRET")

        created = client.post("/api/shop/orders", json={
            "name": "API Bekor", "phone": "+998901112255", "method": "click",
            "items": [{"product_id": p1.id, "quantity": 1}],
        })
        number = created.json()["order"]["order_number"]

        # Noto'g'ri telefon bilan bekor qilib bo'lmaydi
        bad = client.post(f"/api/shop/orders/{number}/cancel",
                          json={"phone": "+998000000000"})
        assert bad.status_code == 403

        # To'g'ri telefon bilan bekor qilinadi
        ok = client.post(f"/api/shop/orders/{number}/cancel",
                         json={"phone": "+998901112255"})
        assert ok.status_code == 200
        assert ok.json()["order"]["status"] == "bekor_qilingan"


class TestMixedOrderApi:
    def _gateway(self, monkeypatch):
        from dashboard import payments as p_mod
        monkeypatch.setattr(p_mod, "CLICK_MERCHANT_ID", "12345")
        monkeypatch.setattr(p_mod, "CLICK_SERVICE_ID", "67890")
        monkeypatch.setattr(p_mod, "CLICK_SECRET_KEY", "SECRET")

    def test_mixed_checkout_click_plus_cash(self, client, catalog, monkeypatch):
        self._gateway(monkeypatch)
        p1, p2 = catalog
        r = client.post("/api/shop/orders", json={
            "name": "API Aralash", "phone": "+998901112266",
            "method": "mixed", "online_gateway": "click",
            "cash_amount": 20_000,
            "items": [{"product_id": p1.id, "quantity": 2},   # 24 000
                       {"product_id": p2.id, "quantity": 5}],  # 40 000
        })
        assert r.status_code == 200
        body = r.json()
        order = body["order"]
        assert order["method"] == "mixed"
        assert order["method_label"] == "Click + Naqd"
        assert order["status"] == "kutilmoqda"
        assert order["total_amount"] == 64_000
        assert order["cash_amount"] == 20_000
        assert order["online_amount"] == 44_000
        assert order["online_gateway"] == "click"
        # Schyot faqat onlayn qismiga ochilgan
        assert body["invoice_id"].startswith("INV-")
        assert "my.click.uz/services/pay" in body["payment_link"]

        # To'lov holatini mijoz raqami bilan ko'rish mumkin
        num = order["order_number"]
        st = client.get(f"/api/shop/orders/{num}?phone=%2B998901112266")
        assert st.status_code == 200
        assert st.json()["order"]["cash_amount"] == 20_000

    def test_mixed_without_gateway_config_503(self, client, catalog):
        p1, _ = catalog
        r = client.post("/api/shop/orders", json={
            "name": "API Payme Mix", "phone": "+998901112267",
            "method": "mixed", "online_gateway": "payme", "cash_amount": 5_000,
            "items": [{"product_id": p1.id, "quantity": 1}],
        })
        assert r.status_code == 503

    def test_mixed_validation_400(self, client, catalog):
        p1, _ = catalog
        # Naqd qismi jami summani to'liq qoplaydi
        r = client.post("/api/shop/orders", json={
            "name": "X", "phone": "+998901112268",
            "method": "mixed", "online_gateway": "click", "cash_amount": 12_000,
            "items": [{"product_id": p1.id, "quantity": 1}],
        })
        assert r.status_code == 400
        # Gateway ko'rsatilmagan
        r = client.post("/api/shop/orders", json={
            "name": "X", "phone": "+998901112268",
            "method": "mixed", "cash_amount": 5_000,
            "items": [{"product_id": p1.id, "quantity": 1}],
        })
        assert r.status_code == 400
    