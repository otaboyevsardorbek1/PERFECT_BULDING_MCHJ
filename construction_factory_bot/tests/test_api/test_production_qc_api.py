"""
ISHLAB CHIQARISH SIFAT NAZORATI REST API testlari:
- GET  /api/production/quality          (pending + acts)
- POST /api/production/{order_id}/quality  (akt yozish)
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
def completed_order(session):
    p = models.Product(name="API QC Sement", category="sement", unit="qop",
                       selling_price=95000, production_cost=60000, is_active=True)
    session.add(p)
    session.commit()
    session.refresh(p)
    order = models.ProductionOrder(
        order_number="PO-API-QC-001",
        product_id=p.id,
        quantity=80,
        total_cost=4_800_000,
        status=models.OrderStatus.COMPLETED,
        actual_end=datetime.utcnow(),
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    return {"product": p, "order": order}


class TestProductionQCApi:
    def test_qc_list_pending_and_empty_acts(self, client, completed_order):
        r = client.get("/api/production/quality")
        assert r.status_code == 200
        body = r.json()
        assert len(body["pending"]) == 1
        assert body["pending"][0]["order_number"] == "PO-API-QC-001"
        assert body["acts"] == []

    def test_post_qc_qabul(self, client, completed_order):
        order_id = completed_order["order"].id
        r = client.post(f"/api/production/{order_id}/quality",
                        json={"quality_status": "qabul_qilingan"})
        assert r.status_code == 200
        qc = r.json()["qc"]
        assert qc["accepted_qty"] == 80
        assert qc["rejected_qty"] == 0
        assert qc["product_name"] == "API QC Sement"
        assert qc["created_by"] == "Test Admin"  # AuthUser.full_name

        # Endi pending bo'sh, aktlar ro'yxatda
        r2 = client.get("/api/production/quality")
        assert r2.status_code == 200
        assert r2.json()["pending"] == []
        assert len(r2.json()["acts"]) == 1

    def test_post_qc_partial(self, client, completed_order):
        order_id = completed_order["order"].id
        r = client.post(f"/api/production/{order_id}/quality",
                        json={"quality_status": "qisman", "rejected_qty": 12,
                              "notes": "30 kg lik xaltalar yirtiq"})
        assert r.status_code == 200
        qc = r.json()["qc"]
        assert qc["accepted_qty"] == 68
        assert qc["rejected_qty"] == 12
        assert qc["notes"] == "30 kg lik xaltalar yirtiq"

    def test_post_qc_errors(self, client, completed_order):
        order_id = completed_order["order"].id
        # Noma'lum holat
        r = client.post(f"/api/production/{order_id}/quality",
                        json={"quality_status": "noma'lum"})
        assert r.status_code == 400
        # Noto'g'ri qisman chegara
        r = client.post(f"/api/production/{order_id}/quality",
                        json={"quality_status": "qisman", "rejected_qty": 0})
        assert r.status_code == 400
        # Ikki marta QC
        ok = client.post(f"/api/production/{order_id}/quality",
                         json={"quality_status": "qabul_qilingan"})
        assert ok.status_code == 200
        r = client.post(f"/api/production/{order_id}/quality",
                        json={"quality_status": "rad_etilgan"})
        assert r.status_code == 400
        # Topilmaydigan buyurtma
        r = client.post("/api/production/999999/quality",
                        json={"quality_status": "qabul_qilingan"})
        assert r.status_code == 400
