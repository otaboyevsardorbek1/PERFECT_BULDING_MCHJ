"""
Web dashboard auth testlari:
- /api/login (telefon + parol) -> token
- Tokensiz / noto'g'ri token -> 401
- Rol matritsasi bo'yicha endpoint cheklovlari (view/edit) -> 403
- /api/me profil va ruxsatlari
"""
from datetime import datetime

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
    """Thread-safe in-memory SQLite (StaticPool) — TestClient alohida thread'da ishlaydi"""
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
def auth_client(session):
    """Haqiqiy auth + in-memory DB ishlatadigan TestClient"""
    from dashboard.app import app

    def _override_get_db():
        yield session

    # conftest'dagi admin override'ini olib tashlab, real auth yoqiladi
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def _make_employee(session, name="Test Xodim", phone="+998901234567",
                   role="ishchi", is_admin=False, password=None):
    emp = models.Employee(
        full_name=name, phone_number=phone, position="Menejer",
        department="sales", hire_date=datetime.utcnow(),
        role=role, is_admin=is_admin,
    )
    session.add(emp)
    session.commit()
    session.refresh(emp)
    if password:
        set_employee_password(session, emp, password)
    return emp


def _login(client, phone, password):
    return client.post("/api/login", json={"phone": phone, "password": password})


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


class TestLogin:
    def test_login_success(self, auth_client, session):
        _make_employee(session, phone="+998901234567", is_admin=True, password="parol1234")
        r = _login(auth_client, "+998901234567", "parol1234")
        assert r.status_code == 200
        body = r.json()
        assert body["token"]
        assert body["refresh_token"]
        assert body["expires_in"] > 0
        assert body["user"]["role"] == "direktor"
        assert body["user"]["role_label"]
        assert "permissions" in body["user"]

    def test_login_creates_session_row(self, auth_client, session):
        _make_employee(session, phone="+998901234567", role="sotuvchi", password="parol1234")
        _login(auth_client, "+998901234567", "parol1234")
        from database import models as db_models
        rows = session.query(db_models.WebSession).all()
        assert len(rows) == 1
        assert rows[0].revoked_at is None
        assert rows[0].refresh_hash

    def test_login_refresh_token_is_opaque_not_access(self, auth_client, session):
        # Refresh token HMAC access token emas — alohida tasodifiy qiymat
        _make_employee(session, phone="+998901234567", role="sotuvchi", password="parol1234")
        body = _login(auth_client, "+998901234567", "parol1234").json()
        assert body["refresh_token"] != body["token"]
        assert "." not in body["refresh_token"]

    def test_login_normalized_phone(self, auth_client, session):
        """998901234567 (plus belgisisiz) ham bir xil xodimga mos keladi"""
        _make_employee(session, phone="+998901234567", role="sotuvchi", password="parol1234")
        r = _login(auth_client, "998901234567", "parol1234")
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "sotuvchi"

    def test_login_wrong_password(self, auth_client, session):
        _make_employee(session, phone="+998901234567", password="parol1234")
        r = _login(auth_client, "+998901234567", "noto'g'ri")
        assert r.status_code == 401

    def test_login_unknown_phone(self, auth_client):
        r = _login(auth_client, "+998999999999", "parol1234")
        assert r.status_code == 401

    def test_login_missing_fields(self, auth_client):
        assert auth_client.post("/api/login", json={"phone": ""}).status_code == 400
        assert auth_client.post("/api/login", json={}).status_code == 400

    def test_login_empty_password_not_allowed(self, auth_client, session):
        # Parol o'rnatilmagan xodim kira olmaydi
        _make_employee(session, phone="+998901234567", role="sotuvchi")
        assert _login(auth_client, "+998901234567", "parol1234").status_code == 401


class TestTokenGate:
    def test_no_token_rejected(self, auth_client):
        assert auth_client.get("/api/customers").status_code == 401

    def test_invalid_token_rejected(self, auth_client):
        r = auth_client.get("/api/customers", headers=_auth_headers("yaroqsiz.token.bu"))
        assert r.status_code == 401

    def test_tampered_token_rejected(self, auth_client, session):
        _make_employee(session, phone="+998901234567", role="direktor", password="parol1234")
        good = _login(auth_client, "+998901234567", "parol1234").json()["token"]
        assert auth_client.get("/api/me", headers=_auth_headers(good + "x")).status_code == 401


class TestMe:
    def test_me_returns_role_and_permissions(self, auth_client, session):
        _make_employee(session, phone="+998901234567", role="omborchi", password="parol1234")
        token = _login(auth_client, "+998901234567", "parol1234").json()["token"]
        r = auth_client.get("/api/me", headers=_auth_headers(token))
        assert r.status_code == 200
        user = r.json()["user"]
        assert user["role"] == "omborchi"
        assert "warehouse" in user["permissions"]["can_view"]
        assert "finance" not in user["permissions"]["can_view"]


class TestRoleEnforcement:
    def test_sotuvchi_crm_view_allowed(self, auth_client, session):
        _make_employee(session, phone="+998901234567", role="sotuvchi", password="parol1234")
        token = _login(auth_client, "+998901234567", "parol1234").json()["token"]
        assert auth_client.get("/api/customers", headers=_auth_headers(token)).status_code == 200

    def test_sotuvchi_finance_forbidden(self, auth_client, session):
        _make_employee(session, phone="+998901234567", role="sotuvchi", password="parol1234")
        token = _login(auth_client, "+998901234567", "parol1234").json()["token"]
        r = auth_client.get("/api/finance/debts", headers=_auth_headers(token))
        assert r.status_code == 403
        assert "error" in r.json()

    def test_sotuvchi_roles_forbidden(self, auth_client, session):
        _make_employee(session, phone="+998901234567", role="sotuvchi", password="parol1234")
        token = _login(auth_client, "+998901234567", "parol1234").json()["token"]
        assert auth_client.get("/api/roles", headers=_auth_headers(token)).status_code == 403

    def test_omborchi_cannot_see_crm(self, auth_client, session):
        _make_employee(session, phone="+998901234567", role="omborchi", password="parol1234")
        token = _login(auth_client, "+998901234567", "parol1234").json()["token"]
        assert auth_client.get("/api/customers", headers=_auth_headers(token)).status_code == 403
        assert auth_client.get("/api/warehouse", headers=_auth_headers(token)).status_code == 200

    def test_buxgalter_cannot_create_customer(self, auth_client, session):
        # Buxgalter crm'ni ko'ra oladi lekin tahrirlay olmaydi
        _make_employee(session, phone="+998901234567", role="buxgalter", password="parol1234")
        token = _login(auth_client, "+998901234567", "parol1234").json()["token"]
        r = auth_client.post("/api/customers", headers=_auth_headers(token),
                             json={"name": "Yangi Mijoz"})
        assert r.status_code == 403

    def test_sotuvchi_can_create_customer(self, auth_client, session):
        _make_employee(session, phone="+998901234567", role="sotuvchi", password="parol1234")
        token = _login(auth_client, "+998901234567", "parol1234").json()["token"]
        r = auth_client.post("/api/customers", headers=_auth_headers(token),
                             json={"name": "Web Mijoz", "credit_limit": 0})
        assert r.status_code == 200
        assert r.json()["customer"]["name"] == "Web Mijoz"

    def test_direktor_roles_and_password(self, auth_client, session):
        _make_employee(session, phone="+998900000001", role="direktor",
                       is_admin=True, password="parol1234")
        worker = _make_employee(session, name="Ishchi2", phone="+998900000002", role="ishchi")
        token = _login(auth_client, "+998900000001", "parol1234").json()["token"]

        # Qisqa parol rad etiladi
        r = auth_client.post(f"/api/roles/{worker.id}/password", headers=_auth_headers(token),
                             json={"password": "qisqa"})
        assert r.status_code == 400

        # To'g'ri parol o'rnatiladi -> ishchi kirishi mumkin
        r = auth_client.post(f"/api/roles/{worker.id}/password", headers=_auth_headers(token),
                             json={"password": "parol12345"})
        assert r.status_code == 200
        assert _login(auth_client, "+998900000002", "parol12345").status_code == 200

    def test_sotuvchi_cannot_set_password(self, auth_client, session):
        _make_employee(session, phone="+998900000001", role="sotuvchi", password="parol1234")
        worker = _make_employee(session, name="Ishchi2", phone="+998900000002")
        token = _login(auth_client, "+998900000001", "parol1234").json()["token"]
        r = auth_client.post(f"/api/roles/{worker.id}/password", headers=_auth_headers(token),
                             json={"password": "parol12345"})
        assert r.status_code == 403

    def test_debt_pay_needs_crm_or_finance_edit(self, auth_client, session):
        # Kassir: sales edit — qarz to'loviga ruxsati yo'q
        _make_employee(session, phone="+998901234567", role="kassir", password="parol1234")
        token = _login(auth_client, "+998901234567", "parol1234").json()["token"]
        r = auth_client.post("/api/customers/1/pay", headers=_auth_headers(token), json={"amount": 1000})
        assert r.status_code == 403

        # Sotuvchi: crm edit — qarz to'lashi mumkin
        _make_employee(session, name="Sotuvchi2", phone="+998900000003",
                       role="sotuvchi", password="parol1234")
        token2 = _login(auth_client, "+998900000003", "parol1234").json()["token"]
        # 403 emas 404 bo'lmasligi kerak (ruxsat bor, mijoz topilmadi)
        r2 = auth_client.post("/api/customers/999999/pay", headers=_auth_headers(token2),
                              json={"amount": 1000})
        assert r2.status_code == 404


COST_KEYS = {"price_per_unit", "value", "production_cost",
             "profit_margin", "total_cost", "warehouse_value"}


def _seed_shop_data(session):
    """Tannarx maydonlari bor xom ashyo / mahsulot / buyurtma / qabul akti"""
    mat = models.RawMaterial(name="Sement 50", unit="qop", category="sement",
                             current_stock=100, min_stock=10,
                             price_per_unit=75000)
    session.add(mat)
    session.flush()
    prod = models.Product(name="Beton M300", category="sement", unit="m3",
                          selling_price=650000, production_cost=400000,
                          profit_margin=0.4, is_active=True)
    session.add(prod)
    session.flush()
    order = models.ProductionOrder(order_number="PO-TEST-1", product_id=prod.id,
                                   quantity=5, total_cost=2000000)
    session.add(order)
    supp = models.Supplier(name="Test Yetkazib Beruvchi", phone="+998911111111")
    session.add(supp)
    session.flush()
    delivery = models.SupplierDelivery(act_number="ACT-TEST-1", supplier_id=supp.id,
                                       raw_material_id=mat.id,
                                       quantity_ordered=100, quantity_received=98,
                                       quality_status="qabul_qilingan",
                                       price_per_unit=75000)
    session.add(delivery)
    session.commit()


def _collect_keys(obj):
    """JSON obyektdagi BARCHA kalitlarni (chuqur) yig'adi"""
    keys = set()
    if isinstance(obj, dict):
        keys.update(obj.keys())
        for v in obj.values():
            keys |= _collect_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            keys |= _collect_keys(item)
    return keys


class TestCostVisibilityServerSide:
    """see_cost=False rollar tannarx maydonlarini server javobida HECH QACHON olmasligi"""

    @pytest.fixture(autouse=True)
    def _seed(self, session):
        _seed_shop_data(session)

    def test_omborchi_warehouse_has_no_cost_fields(self, auth_client, session):
        # Omborchi omborni ko'ra oladi, lekin narx/tannarxni ko'ra olmaydi
        _make_employee(session, phone="+998901234567", role="omborchi", password="parol1234")
        token = _login(auth_client, "+998901234567", "parol1234").json()["token"]
        r = auth_client.get("/api/warehouse", headers=_auth_headers(token))
        assert r.status_code == 200
        body = r.json()
        assert body["materials"], "seed material topilmadi"
        keys = _collect_keys(body)
        assert not (keys & COST_KEYS), f"omborchi tannarx kalitlarini oldi: {keys & COST_KEYS}"
        # Noma'lum bo'lmagan maydonlar qoladi
        assert all("name" in m and "current_stock" in m for m in body["materials"])

    def test_omborchi_receipts_have_no_unit_price(self, auth_client, session):
        _make_employee(session, phone="+998901234567", role="omborchi", password="parol1234")
        token = _login(auth_client, "+998901234567", "parol1234").json()["token"]
        r = auth_client.get("/api/receipts", headers=_auth_headers(token))
        assert r.status_code == 200
        body = r.json()
        assert body["receipts"]
        keys = _collect_keys(body)
        assert "price_per_unit" not in keys
        assert all("act_number" in rec and "quantity_received" in rec
                   for rec in body["receipts"])

    def test_ishchi_products_orders_have_no_cost(self, auth_client, session):
        # Ishchi ishlab chiqarishni ko'ra oladi (mahsulotlar, buyurtmalar)
        _make_employee(session, phone="+998901234567", role="ishchi", password="parol1234")
        token = _login(auth_client, "+998901234567", "parol1234").json()["token"]

        r = auth_client.get("/api/products", headers=_auth_headers(token))
        assert r.status_code == 200
        body = r.json()
        assert body["products"]
        keys = _collect_keys(body)
        assert not (keys & {"production_cost", "profit_margin"})
        # Sotuv narxi qoladi — u tannarx emas
        assert all("selling_price" in p for p in body["products"])

        r = auth_client.get("/api/orders", headers=_auth_headers(token))
        assert r.status_code == 200
        body = r.json()
        keys = _collect_keys(body)
        assert "total_cost" not in keys

    def test_sotuvchi_warehouse_no_cost(self, auth_client, session):
        # Sotuvchi omborni ko'ra oladi (warehouse view), tannarxni emas
        _make_employee(session, phone="+998901234567", role="sotuvchi", password="parol1234")
        token = _login(auth_client, "+998901234567", "parol1234").json()["token"]
        r = auth_client.get("/api/warehouse", headers=_auth_headers(token))
        assert r.status_code == 200
        keys = _collect_keys(r.json())
        assert not (keys & COST_KEYS)

    def test_buxgalter_still_sees_cost(self, auth_client, session):
        # Buxgalter tannarxni ko'ra oladi (see_cost=True)
        _make_employee(session, phone="+998901234567", role="buxgalter", password="parol1234")
        token = _login(auth_client, "+998901234567", "parol1234").json()["token"]
        r = auth_client.get("/api/warehouse", headers=_auth_headers(token))
        assert r.status_code == 200
        body = r.json()
        keys = _collect_keys(body)
        assert "price_per_unit" in keys and "value" in keys
        # Haqiqiy narx qaytadi (server tannarxni kesmaydi)
        assert body["materials"][0]["price_per_unit"] > 0

    def test_direktor_still_sees_product_cost(self, auth_client, session):
        _make_employee(session, phone="+998901234567", role="direktor",
                       is_admin=True, password="parol1234")
        token = _login(auth_client, "+998901234567", "parol1234").json()["token"]
        r = auth_client.get("/api/products", headers=_auth_headers(token))
        assert r.status_code == 200
        body = r.json()
        keys = _collect_keys(body)
        assert "production_cost" in keys and "profit_margin" in keys


class TestLegacyRootPageGate:
    """FastAPI root sahifasi (/) — eski dashboard — login talab qiladi"""

    def test_root_redirects_to_login_when_anonymous(self, auth_client):
        # follow_redirects=False bilan haqiqiy holat tekshiriladi
        r = auth_client.get("/", follow_redirects=False)
        assert r.status_code == 303
        assert "/login" in r.headers.get("location", "")

    def test_login_page_served(self, auth_client):
        r = auth_client.get("/login")
        assert r.status_code == 200
        assert "Telefon raqami" in r.text
        assert "password" in r.text

    def test_login_wrong_password_shows_error(self, auth_client, session):
        _make_employee(session, phone="+998901234567", role="direktor",
                       is_admin=True, password="parol1234")
        r = auth_client.post("/login", data={"phone": "+998901234567", "password": "xato"})
        assert r.status_code == 401
        assert "noto'g'ri" in r.text

    def test_login_unknown_phone_rejected(self, auth_client):
        r = auth_client.post("/login", data={"phone": "+998999999999", "password": "parol1234"})
        assert r.status_code == 401

    def test_employee_without_password_cannot_login(self, auth_client, session):
        # Parol o'rnatilmagan xodim web-login qila olmaydi
        _make_employee(session, phone="+998901234567", role="direktor")
        r = auth_client.post("/login", data={"phone": "+998901234567", "password": "parol1234"})
        assert r.status_code == 401

    def test_login_success_sets_cookie_and_opens_root(self, auth_client, session):
        _make_employee(session, phone="+998901234567", role="direktor",
                       is_admin=True, password="parol1234")
        r = auth_client.post("/login", data={"phone": "+998901234567", "password": "parol1234"},
                             follow_redirects=False)
        assert r.status_code == 303
        assert "web_token" in r.cookies
        # Cookie bilan root ochiladi
        r2 = auth_client.get("/")
        assert r2.status_code == 200
        assert "Qurilish Korxonasi Dashboard" in r2.text

    def test_low_role_cannot_open_root(self, auth_client, session):
        # Omborchi root'ni ocha olmaydi (reports moduli yo'q) — 403 sahifa
        _make_employee(session, phone="+998901234567", role="omborchi", password="parol1234")
        auth_client.post("/login", data={"phone": "+998901234567", "password": "parol1234"})
        r = auth_client.get("/")
        assert r.status_code == 403
        assert "Ruxsat yo'q" in r.text

    def test_logout_clears_cookie(self, auth_client, session):
        _make_employee(session, phone="+998901234567", role="direktor",
                       is_admin=True, password="parol1234")
        auth_client.post("/login", data={"phone": "+998901234567", "password": "parol1234"})
        r = auth_client.get("/logout", follow_redirects=False)
        assert r.status_code == 303
        assert "/login" in r.headers.get("location", "")
        # Cookie o'chirilgan — root yana login'ga yo'naltiradi
        r2 = auth_client.get("/", follow_redirects=False)
        assert r2.status_code == 303
        assert "/login" in r2.headers.get("location", "")

    def test_logout_revokes_html_session(self, auth_client, session):
        # HTML logout sessiyani ham revoke qiladi — eski cookie token ishlamaydi
        _make_employee(session, phone="+998901234567", role="direktor",
                       is_admin=True, password="parol1234")
        auth_client.post("/login", data={"phone": "+998901234567", "password": "parol1234"})
        from database import models as db_models
        web_session = session.query(db_models.WebSession).first()
        assert web_session is not None and web_session.revoked_at is None
        auth_client.get("/logout", follow_redirects=False)
        session.refresh(web_session)
        assert web_session.revoked_at is not None


class TestRefreshTokens:
    """Refresh token: rotatsiya, sliding muddat, logout'da revoke"""

    def test_refresh_returns_new_pair_and_rotates(self, auth_client, session):
        from database import models as db_models
        _make_employee(session, phone="+998901234567", role="sotuvchi", password="parol1234")
        login = _login(auth_client, "+998901234567", "parol1234").json()
        old_refresh = login["refresh_token"]

        r = auth_client.post("/api/refresh", json={"refresh_token": old_refresh})
        assert r.status_code == 200
        body = r.json()
        assert body["token"]
        assert body["refresh_token"] != old_refresh  # rotatsiya
        assert body["user"]["role"] == "sotuvchi"

        # Eski refresh endi ishlamaydi (aylantirilgan)
        r2 = auth_client.post("/api/refresh", json={"refresh_token": old_refresh})
        assert r2.status_code == 401

    def test_refresh_moves_expiry_forward_sliding(self, auth_client, session):
        # Sliding: sessiya muddati har refresh'da hozirgi vaqtdan boshlab uzayadi
        from datetime import timedelta
        from dashboard import auth as auth_mod
        from database import models as db_models

        real_now = auth_mod._now()
        _make_employee(session, phone="+998901234567", role="sotuvchi", password="parol1234")
        login = _login(auth_client, "+998901234567", "parol1234").json()
        web_session = session.query(db_models.WebSession).first()
        original_expiry = web_session.expires_at

        # Vaqtni 2 kun oldinga surib, refresh qilamiz
        shifted = real_now + timedelta(days=2)
        auth_mod._now = lambda: shifted
        try:
            r = auth_client.post("/api/refresh", json={"refresh_token": login["refresh_token"]})
        finally:
            auth_mod._now = lambda: real_now
        assert r.status_code == 200

        session.expire_all()
        web_session = session.query(db_models.WebSession).first()
        expected = shifted + timedelta(seconds=auth_mod.REFRESH_TOKEN_TTL_SECONDS)
        assert abs((web_session.expires_at - expected).total_seconds()) < 5
        # Sliding: yangi muddat eski muddatdan keyinroq
        assert web_session.expires_at > original_expiry

    def test_refresh_with_expired_session_rejected(self, auth_client, session):
        from datetime import timedelta
        from dashboard import auth as auth_mod
        from database import models as db_models

        _make_employee(session, phone="+998901234567", role="sotuvchi", password="parol1234")
        login = _login(auth_client, "+998901234567", "parol1234").json()
        web_session = session.query(db_models.WebSession).first()
        web_session.expires_at = auth_mod._now() - timedelta(seconds=1)
        session.commit()

        r = auth_client.post("/api/refresh", json={"refresh_token": login["refresh_token"]})
        assert r.status_code == 401

    def test_logout_revokes_both_access_and_refresh(self, auth_client, session):
        _make_employee(session, phone="+998901234567", role="sotuvchi", password="parol1234")
        login = _login(auth_client, "+998901234567", "parol1234").json()
        token, refresh = login["token"], login["refresh_token"]

        # Logout (refresh token bilan)
        r = auth_client.post("/api/logout", json={"refresh_token": refresh})
        assert r.status_code == 200
        assert r.json() == {"success": True}

        # Eski access endi ishlamaydi — sessiya revoke qilingan
        assert auth_client.get("/api/me", headers=_auth_headers(token)).status_code == 401
        # Refresh ham ishlamaydi
        assert auth_client.post("/api/refresh", json={"refresh_token": refresh}).status_code == 401

    def test_logout_with_access_token_only(self, auth_client, session):
        _make_employee(session, phone="+998901234567", role="sotuvchi", password="parol1234")
        login = _login(auth_client, "+998901234567", "parol1234").json()
        token = login["token"]

        r = auth_client.post("/api/logout", headers=_auth_headers(token), json={})
        assert r.status_code == 200
        assert auth_client.get("/api/me", headers=_auth_headers(token)).status_code == 401

    def test_logout_unknown_token_401(self, auth_client):
        assert auth_client.post("/api/logout", json={}).status_code == 401

    def test_other_session_survives_logout(self, auth_client, session):
        # Bitta sessiya logout bo'lsa, boshqa sessiya (boshqa login) ishlayveradi
        _make_employee(session, phone="+998901234567", role="sotuvchi", password="parol1234")
        first = _login(auth_client, "+998901234567", "parol1234").json()
        second = _login(auth_client, "+998901234567", "parol1234").json()

        auth_client.post("/api/logout", json={"refresh_token": first["refresh_token"]})
        # Ikkinchi sessiya tirik
        assert auth_client.get("/api/me", headers=_auth_headers(second["token"])).status_code == 200
        # Birinchi o'lgan
        assert auth_client.get("/api/me", headers=_auth_headers(first["token"])).status_code == 401
