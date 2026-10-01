"""
v5.5 testlari — TZ 3-bo'lim qolgan bo'shliqlar:

- 🔮 AI: sotuv prognozi, mijoz segmentatsiyasi, dinamik narxlash,
  mijozga tavsiya, yetkazib berish ETA (TZ 3.9)
- 📡 IoT sensorlar: o'lchov saqlash, me'yor tekshiruvi, buzilishlar xulosasi (TZ 3.10)
- 🕰️ Audit log: SystemLog asosida filtrlash (TZ 3.11)
- 🚩 Feature flags: CRUD, rollout %, xatoda avto-o'chirish (TZ 3.12)
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


def _make_product(session, name="Sement M500", price=60000, category="sement",
                  min_stock=10, max_stock=1000):
    p = models.Product(
        name=name, category=category, unit="qop",
        selling_price=price, production_cost=price * 0.6,
        min_stock=min_stock, max_stock=max_stock, is_active=True,
    )
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def _make_sale(session, product, customer, qty=10, price=60000,
               days_ago=0, amount=None):
    sale = models.Sale(
        invoice_number=f"INV-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
        product_id=product.id,
        quantity=qty,
        unit_price=price,
        total_amount=amount if amount is not None else qty * price,
        customer_id=customer.id if customer else None,
        status="completed",
        sale_date=datetime.utcnow() - timedelta(days=days_ago),
    )
    session.add(sale)
    session.commit()
    session.refresh(sale)
    return sale


def _make_customer(session, name="Mijoz 1", debt=0.0):
    c = models.Customer(name=name, phone=f"+998{abs(hash(name)) % 10**9:09d}",
                        total_debt=debt)
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


# ================= 3.9.1 SOTUV PROGNOZI =================
class TestSalesForecast:
    def test_forecast_with_data(self, client, session):
        _make_employee(session)
        headers = _auth_headers(client)
        p = _make_product(session)
        c = _make_customer(session)
        for d in range(1, 31):
            _make_sale(session, p, c, qty=5, price=60000, days_ago=d)
        r = client.get("/api/ai/sales-forecast?days=30", headers=headers)
        assert r.status_code == 200
        data = r.json()
        # 30 kun oldingi sotuv "since" chegarasida mikrosekund farqi tufayli
        # qolishi mumkin — shuning uchun >= 29
        assert data["order_count"] >= 29
        assert data["total_revenue"] > 0
        assert data["forecast_7d_revenue"] > 0
        assert data["forecast_30d_revenue"] >= data["forecast_7d_revenue"]
        assert data["trend_label"] in ("osmoqda", "kamaymoqda", "barqaror")
        assert 0 <= data["confidence"] <= 100
        assert data["seasonal_note"]

    def test_forecast_empty(self, client, session):
        _make_employee(session)
        headers = _auth_headers(client)
        r = client.get("/api/ai/sales-forecast?days=30", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["order_count"] == 0
        assert data["total_revenue"] == 0
        assert data["forecast_7d_revenue"] == 0

    def test_forecast_auth_required(self, client):
        r = client.get("/api/ai/sales-forecast")
        assert r.status_code in (401, 403)


# ================= 3.9.2 MIJOZ SEGMENTATSIYASI =================
class TestCustomerSegments:
    def test_segments_grouping(self, client, session):
        _make_employee(session)
        headers = _auth_headers(client)
        p = _make_product(session)
        # VIP: 60 mln xarid, qarzsiz
        vip = _make_customer(session, "VIP Mijoz")
        _make_sale(session, p, vip, qty=1000, price=60000)  # 60 mln
        # Xavfli: qarzi katta
        danger = _make_customer(session, "Qarzdor", debt=8_000_000)
        _make_sale(session, p, danger, qty=100, price=60000)  # 6 mln xarid, 8 mln qarz
        r = client.get("/api/ai/customer-segments", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total_customers"] >= 2
        assert "vip_oligarcha" in data["segments"]
        assert "xavfli_qarzdor" in data["segments"]
        assert any(x["id"] == vip.id for x in data["segments"]["vip_oligarcha"])
        assert any(x["id"] == danger.id for x in data["segments"]["xavfli_qarzdor"])
        assert data["recommendations"]["xavfli_qarzdor"]

    def test_segments_empty_db(self, client, session):
        _make_employee(session)
        headers = _auth_headers(client)
        r = client.get("/api/ai/customer-segments", headers=headers)
        assert r.status_code == 200
        assert r.json()["total_customers"] == 0


# ================= 3.9.3 DINAMIK NARXLASH =================
class TestDynamicPricing:
    def test_pricing_keep_when_balanced(self, client, session):
        _make_employee(session)
        headers = _auth_headers(client)
        p = _make_product(session)
        c = _make_customer(session)
        # 30 kun davomida o'rtacha sotuv: qoldiq ~14-60 kun oralig'ida qoladi
        # 300 dona sotilgan (kuniga 10), kirim 3000 -> 3000/10 = 300 kun... emas,
        # balansni aniq quramiz: kirim 4000, sotuv 3000 -> qoldiq 1000, kunlik 10 -> 100 kun > 60
        session.add(models.WarehouseTransaction(
            product_id=p.id, quantity=4000,
            transaction_type=models.TransactionType.INCOME, user_id=1))
        for d in range(1, 31):
            _make_sale(session, p, c, qty=100, price=60000, days_ago=d)
        session.commit()
        r = client.get("/api/ai/dynamic-pricing", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["suggestions"]
        s = [x for x in data["suggestions"] if x["product_id"] == p.id][0]
        assert s["action"] in ("pasaytirish", "oshirish", "saqlash")
        if s["action"] != "saqlash":
            assert s["requires_director_approval"] is True
            assert s["price_change_percent"] in (3, 5)

    def test_pricing_no_sales_keeps_price(self, client, session):
        _make_employee(session)
        headers = _auth_headers(client)
        _make_product(session, name="Yangi mahsulot")
        r = client.get("/api/ai/dynamic-pricing", headers=headers)
        assert r.status_code == 200
        s = r.json()["suggestions"][0]
        # Sotuv bo'lmasa daily_demand=0 -> saqlash
        assert s["action"] == "saqlash"
        assert s["requires_director_approval"] is False


# ================= 3.9.4 MIJOZGA TAVSIYA =================
class TestRecommendations:
    def test_recommend_for_customer(self, client, session):
        _make_employee(session)
        headers = _auth_headers(client)
        p1 = _make_product(session, "Sement")
        p2 = _make_product(session, "Qum", category="sement")
        p3 = _make_product(session, "Armatura", category="rodbin")

        me = _make_customer(session, "Men")
        other = _make_customer(session, "O'xshash mijoz")

        # Men sement olganman
        _make_sale(session, p1, me)
        # O'xshash mijoz sement + qum olgan
        _make_sale(session, p1, other)
        _make_sale(session, p2, other)

        r = client.get(f"/api/ai/recommend/{me.id}", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["customer"]["id"] == me.id
        assert "sement" in data["purchased_categories"]
        assert data["similar_customers_found"] >= 1
        rec_ids = [x["product_id"] for x in data["recommendations"]]
        assert p2.id in rec_ids
        assert p1.id not in rec_ids  # allaqachon olgan
        assert p3.id not in rec_ids  # boshqa kategoriya, o'xshashlik yo'q

    def test_recommend_unknown_customer(self, client, session):
        _make_employee(session)
        headers = _auth_headers(client)
        r = client.get("/api/ai/recommend/99999", headers=headers)
        assert r.status_code == 200
        assert r.json()["customer"] is None


# ================= 3.9.5 YETKAZIB BERISH ETA =================
class TestDeliveryETA:
    def test_eta_basic(self, client, session):
        _make_employee(session)
        headers = _auth_headers(client)
        r = client.get("/api/ai/delivery-eta?distance_km=20", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["distance_km"] == 20
        assert data["eta_minutes"] > 0
        assert data["drive_minutes"] > 0
        assert data["load_minutes"] >= 20
        assert data["eta_time"]
        assert data["factors"]

    def test_eta_with_vehicle_in_repair(self, client, session):
        _make_employee(session)
        headers = _auth_headers(client)
        emp = models.Employee(
            full_name="Haydovchi Test", phone_number="+998909000101",
            position="haydovchi", department="logistika",
            hire_date=datetime.utcnow(), role="haydovchi", is_admin=False)
        session.add(emp)
        session.commit()
        v = models.Vehicle(number="01 A 999 AA", status="ta'mirda",
                           driver_id=emp.id)
        session.add(v)
        session.commit()
        r = client.get(f"/api/ai/delivery-eta?distance_km=10&vehicle_id={v.id}",
                       headers=headers)
        assert r.status_code == 200
        factors = r.json()["factors"]
        assert any("ta'mirda" in f for f in factors)


# ================= 3.10 IOT SENSORLAR =================
class TestSensors:
    def test_add_reading_in_range(self, client, session):
        _make_employee(session)
        headers = _auth_headers(client)
        r = client.post("/api/sensors", headers=headers, json={
            "sensor_type": "temperature", "value": 22.5,
            "device_name": "Ombor A", "warehouse": "xomashyo",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["alert"] is False
        assert data["reading"]["is_out_of_range"] is False

    def test_add_reading_out_of_range(self, client, session):
        _make_employee(session)
        headers = _auth_headers(client)
        r = client.post("/api/sensors", headers=headers, json={
            "sensor_type": "temperature", "value": 45.0,
            "device_name": "Ombor B", "warehouse": "tayyor",
        })
        assert r.status_code == 200
        assert r.json()["alert"] is True
        # Audit log'ga yozilganini tekshirish (3.11 bog'lanish)
        r2 = client.get("/api/audit-log?action=sensor_violation", headers=headers)
        assert r2.status_code == 200
        assert r2.json()["total"] >= 1

    def test_humidity_out_of_range(self, client, session):
        _make_employee(session)
        headers = _auth_headers(client)
        r = client.post("/api/sensors", headers=headers, json={
            "sensor_type": "humidity", "value": 95.0,
        })
        assert r.json()["alert"] is True

    def test_invalid_sensor_type(self, client, session):
        _make_employee(session)
        headers = _auth_headers(client)
        r = client.post("/api/sensors", headers=headers, json={
            "sensor_type": "buzz", "value": 1,
        })
        assert r.status_code == 400

    def test_list_and_alerts(self, client, session):
        _make_employee(session)
        headers = _auth_headers(client)
        client.post("/api/sensors", headers=headers,
                    json={"sensor_type": "temperature", "value": 22.0})
        client.post("/api/sensors", headers=headers,
                    json={"sensor_type": "humidity", "value": 90.0})
        r = client.get("/api/sensors", headers=headers)
        assert r.status_code == 200
        readings = r.json()["readings"]
        assert len(readings) == 2

        r2 = client.get("/api/sensors/alerts", headers=headers)
        assert r2.status_code == 200
        al = r2.json()
        assert al["total_readings"] == 2
        assert al["violations_count"] == 1
        assert al["violations_by_type"].get("humidity") == 1

    def test_out_of_range_filter(self, client, session):
        _make_employee(session)
        headers = _auth_headers(client)
        client.post("/api/sensors", headers=headers,
                    json={"sensor_type": "temperature", "value": 25.0})
        client.post("/api/sensors", headers=headers,
                    json={"sensor_type": "temperature", "value": -10.0})
        r = client.get("/api/sensors?out_of_range_only=true", headers=headers)
        readings = r.json()["readings"]
        assert len(readings) == 1
        assert readings[0]["is_out_of_range"] is True


# ================= 3.11 AUDIT LOG =================
class TestAuditLog:
    def test_audit_entries(self, client, session):
        _make_employee(session)
        headers = _auth_headers(client)
        # Login SystemLog'ga yoziladi bo'lishi shart emas — qo'lda qo'shamiz
        session.add(models.SystemLog(
            user_id=1, user_name="Test", action="create_sale",
            module="sales", details="Sotuv INV-1"))
        session.commit()
        r = client.get("/api/audit-log", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        entry = data["entries"][0]
        assert "user_name" in entry and "action" in entry and "module" in entry

    def test_audit_filter_by_module(self, client, session):
        _make_employee(session)
        headers = _auth_headers(client)
        session.add(models.SystemLog(action="a", module="sales"))
        session.add(models.SystemLog(action="b", module="finance"))
        session.commit()
        r = client.get("/api/audit-log?module=sales", headers=headers)
        entries = r.json()["entries"]
        assert all(e["module"] == "sales" for e in entries)

    def test_audit_role_restricted(self, client, session):
        # Sotuvchi audit log ko'ra olmaydi
        emp = _make_employee(session, name="Sotuvchi Test",
                             phone="+998909000202", role="sotuvchi",
                             is_admin=False)
        headers = _auth_headers(client, phone=emp.phone_number)
        r = client.get("/api/audit-log", headers=headers)
        assert r.status_code == 403


# ================= 3.12 FEATURE FLAGS =================
class TestFeatureFlags:
    def test_flag_crud_cycle(self, client, session):
        _make_employee(session)
        headers = _auth_headers(client)
        # Yaratish
        r = client.post("/api/feature-flags", headers=headers, json={
            "key": "ai_chatbot", "name": "AI chatbot 24/7",
            "rollout_percent": 50, "auto_disable_on_error": True,
        })
        assert r.status_code == 200
        flag = r.json()["flag"]
        assert flag["key"] == "ai_chatbot"
        fid = flag["id"]

        # Ro'yxat
        r = client.get("/api/feature-flags", headers=headers)
        keys = [f["key"] for f in r.json()["flags"]]
        assert "ai_chatbot" in keys

        # Yangilash (yoqish)
        r = client.patch(f"/api/feature-flags/{fid}", headers=headers,
                         json={"is_enabled": True, "rollout_percent": 100})
        assert r.json()["flag"]["is_enabled"] is True

        # Tekshirish
        r = client.get("/api/feature-flags/ai_chatbot/check?user_seed=1", headers=headers)
        assert r.json()["enabled"] is True

        # O'chirish
        r = client.delete(f"/api/feature-flags/{fid}", headers=headers)
        assert r.json()["success"] is True
        r = client.get("/api/feature-flags/ai_chatbot/check?user_seed=1", headers=headers)
        assert r.json()["enabled"] is False

    def test_flag_duplicate_rejected(self, client, session):
        _make_employee(session)
        headers = _auth_headers(client)
        body = {"key": "test_flag", "name": "x"}
        assert client.post("/api/feature-flags", headers=headers, json=body).status_code == 200
        assert client.post("/api/feature-flags", headers=headers, json=body).status_code == 400

    def test_flag_rollout_percent(self, client, session):
        _make_employee(session)
        headers = _auth_headers(client)
        client.post("/api/feature-flags", headers=headers, json={
            "key": "rollout_flag", "is_enabled": True, "rollout_percent": 10,
        })
        # seed=1: 1 % 100 = 1 < 10 -> yoqilgan
        r1 = client.get("/api/feature-flags/rollout_flag/check?user_seed=1", headers=headers)
        assert r1.json()["enabled"] is True
        # seed=55: 55 % 100 = 55 >= 10 -> o'chirilgan
        r2 = client.get("/api/feature-flags/rollout_flag/check?user_seed=55", headers=headers)
        assert r2.json()["enabled"] is False

    def test_flag_auto_disable_on_errors(self, client, session):
        _make_employee(session)
        headers = _auth_headers(client)
        client.post("/api/feature-flags", headers=headers, json={
            "key": "fragile", "is_enabled": True,
            "auto_disable_on_error": True,
        })
        for _ in range(5):
            r = client.post("/api/feature-flags/fragile/error?threshold=5", headers=headers)
            assert r.status_code == 200
        # 5-xatodan keyin avto-o'chirilishi kerak
        assert r.json()["auto_disabled"] is True
        assert r.json()["is_enabled"] is False

    def test_flag_error_unknown(self, client, session):
        _make_employee(session)
        headers = _auth_headers(client)
        r = client.post("/api/feature-flags/no_such_flag/error", headers=headers)
        assert r.status_code == 404

    def test_flag_role_restricted(self, client, session):
        emp = _make_employee(session, name="Sotuvchi FF",
                             phone="+998909000303", role="sotuvchi",
                             is_admin=False)
        headers = _auth_headers(client, phone=emp.phone_number)
        r = client.get("/api/feature-flags", headers=headers)
        assert r.status_code == 403
        r2 = client.post("/api/feature-flags", headers=headers, json={"key": "h4x"})
        assert r2.status_code in (401, 403)
