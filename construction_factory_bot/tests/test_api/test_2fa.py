"""
2FA (Google Authenticator / TOTP) testlari — v4.2

- utils/totp: RFC 6238 kod generatsiyasi va tekshiruvi
- API: /api/auth/2fa/setup|enable|disable + /api/login 2-bosqich (428 -> otp_code)
- Web dashboard: /login HTML ikki bosqich (parol -> otp_token -> kod)
"""
import re
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import models
from database.session import get_db
from dashboard.auth import get_current_user, set_employee_password
from utils import totp


@pytest.fixture
def session():
    """Thread-safe in-memory SQLite (StaticPool)"""
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
    from dashboard.app import app

    def _override_get_db():
        yield session

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def _make_employee(session, name="Test Xodim", phone="+998901234567",
                   role="direktor", is_admin=True, password=None):
    emp = models.Employee(
        full_name=name, phone_number=phone, position="Direktor",
        department="boshqaruv", hire_date=datetime.utcnow(),
        role=role, is_admin=is_admin,
    )
    session.add(emp)
    session.commit()
    session.refresh(emp)
    if password:
        set_employee_password(session, emp, password)
    return emp


def _login(client, phone, password, otp_code=None):
    payload = {"phone": phone, "password": password}
    if otp_code:
        payload["otp_code"] = otp_code
    return client.post("/api/login", json=payload)


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


class TestTOTP:
    """utils/totp — RFC 6238 asosiy tekshiruvlar"""

    def test_generate_secret_format(self):
        secret = totp.generate_secret()
        # base32, 32 belgi (160 bit -> 32 base32 chars)
        assert len(secret) == 32
        assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for c in secret)

    def test_totp_code_deterministic(self):
        secret = totp.generate_secret()
        t = 1_700_000_000
        assert totp.totp_code(secret, t) == totp.totp_code(secret, t)
        assert totp.totp_code(secret, t) != totp.totp_code(secret, t + 30)

    def test_totp_code_six_digits(self):
        secret = totp.generate_secret()
        code = totp.totp_code(secret)
        assert re.fullmatch(r"\d{6}", code)

    def test_verify_ok(self):
        secret = totp.generate_secret()
        t = 1_700_000_000
        code = totp.totp_code(secret, t)
        assert totp.verify_totp(secret, code, at_time=t)

    def test_verify_window(self):
        secret = totp.generate_secret()
        t = 1_700_000_000
        # Oldingi va keyingi 30-sekundlik kodlar ham qabul qilinadi (±1 window)
        assert totp.verify_totp(secret, totp.totp_code(secret, t - 30), at_time=t)
        assert totp.verify_totp(secret, totp.totp_code(secret, t + 30), at_time=t)

    def test_verify_rejects_wrong(self):
        secret = totp.generate_secret()
        t = 1_700_000_000
        assert not totp.verify_totp(secret, "000000", at_time=t)
        assert not totp.verify_totp(secret, "", at_time=t)

    def test_verify_normalizes_secret(self):
        secret = totp.generate_secret()
        t = 1_700_000_000
        code = totp.totp_code(secret, t)
        spaced = " ".join(secret[i:i + 4] for i in range(0, len(secret), 4))
        assert totp.verify_totp(spaced.lower(), code, at_time=t)

    def test_provisioning_uri(self):
        secret = totp.generate_secret()
        uri = totp.provisioning_uri(secret, "Ali", issuer="Perfect Building")
        assert uri.startswith("otpauth://totp/Perfect%20Building:Ali?")
        assert f"secret={secret}" in uri
        assert "period=30" in uri and "digits=6" in uri


class TestAPI2FA:
    """API: setup -> enable -> login 2-bosqich -> disable"""

    def test_setup_requires_auth(self, auth_client):
        r = auth_client.post("/api/auth/2fa/setup", json={})
        assert r.status_code in (401, 403)

    def test_enable_flow_and_login(self, auth_client, session):
        emp = _make_employee(session, password="parol1234")
        r = _login(auth_client, "+998901234567", "parol1234")
        assert r.status_code == 200
        token = r.json()["token"]

        # 1) Setup: secret + QR beriladi, 2FA hali yoqilmagan
        r = auth_client.post("/api/auth/2fa/setup", headers=_auth_headers(token))
        assert r.status_code == 200
        data = r.json()
        assert data["secret"] and data["provisioning_uri"].startswith("otpauth://")
        assert data["qr_data_url"] is None or data["qr_data_url"].startswith("data:image/png")
        assert data["enabled"] is False

        # /api/me hali two_fa_enabled=False ko'rsatadi
        r = auth_client.get("/api/me", headers=_auth_headers(token))
        assert r.json()["user"]["two_fa_enabled"] is False

        # 2) Noto'g'ri kod bilan yoqib bo'lmaydi
        r = auth_client.post("/api/auth/2fa/enable", json={"code": "000000"},
                             headers=_auth_headers(token))
        assert r.status_code == 400

        # 3) To'g'ri kod bilan yoqiladi
        code = totp.totp_code(data["secret"])
        r = auth_client.post("/api/auth/2fa/enable", json={"code": code},
                             headers=_auth_headers(token))
        assert r.status_code == 200
        assert r.json()["enabled"] is True

        r = auth_client.get("/api/me", headers=_auth_headers(token))
        assert r.json()["user"]["two_fa_enabled"] is True

        # 4) Login endi kod talab qiladi: kodsiz -> 428, noto'g'ri kod -> 401
        r = _login(auth_client, "+998901234567", "parol1234")
        assert r.status_code == 428

        r = _login(auth_client, "+998901234567", "parol1234", otp_code="000000")
        assert r.status_code == 401

        # 5) To'g'ri kod bilan muvaffaqiyatli
        good_code = totp.totp_code(emp.otp_secret)
        r = _login(auth_client, "+998901234567", "parol1234", otp_code=good_code)
        assert r.status_code == 200
        assert "token" in r.json()
        assert r.json()["user"]["two_fa_enabled"] is True

    def test_disable_flow(self, auth_client, session):
        emp = _make_employee(session, password="parol1234")
        r = _login(auth_client, "+998901234567", "parol1234")
        token = r.json()["token"]
        r = auth_client.post("/api/auth/2fa/setup", headers=_auth_headers(token))
        secret = r.json()["secret"]
        auth_client.post("/api/auth/2fa/enable", json={"code": totp.totp_code(secret)},
                         headers=_auth_headers(token))

        # Kodsiz login bloklanadi
        assert _login(auth_client, "+998901234567", "parol1234").status_code == 428

        # Noto'g'ri kod bilan o'chirib bo'lmaydi
        r = auth_client.post("/api/auth/2fa/disable", json={"code": "000000"},
                             headers=_auth_headers(token))
        assert r.status_code == 400

        # To'g'ri kod bilan o'chadi va login yana kodsiz ishlaydi
        r = auth_client.post("/api/auth/2fa/disable", json={"code": totp.totp_code(secret)},
                             headers=_auth_headers(token))
        assert r.status_code == 200
        assert r.json()["enabled"] is False

        r = _login(auth_client, "+998901234567", "parol1234")
        assert r.status_code == 200

    def test_login_pending_token_not_usable(self, auth_client, session):
        """2FA yoqilmagan xodimda setup chaqirilsa ham login kodsiz ishlaydi"""
        _make_employee(session, password="parol1234")
        r = _login(auth_client, "+998901234567", "parol1234")
        assert r.status_code == 200


class TestWebLogin2FA:
    """Root dashboard /login HTML — ikki bosqichli 2FA form"""

    def test_html_login_step_to_otp(self, auth_client, session):
        emp = _make_employee(session, password="parol1234")
        r = auth_client.post("/login", data={"phone": "+998901234567", "password": "parol1234"},
                             follow_redirects=False)
        # 2FA yoqilmagan — darhol sessiya ochilib dashboard'ga o'tadi
        assert r.status_code == 303
        assert r.headers.get("location") == "/"

        # 2FA yoqamiz
        login = _login(auth_client, "+998901234567", "parol1234")
        token = login.json()["token"]
        auth_client.post("/api/auth/2fa/setup", headers=_auth_headers(token))
        secret = emp.otp_secret
        auth_client.post("/api/auth/2fa/enable", json={"code": totp.totp_code(secret)},
                         headers=_auth_headers(token))

        # Endi /login paroldan keyin OTP bosqichini ko'rsatadi
        r = auth_client.post("/login", data={"phone": "+998901234567", "password": "parol1234"},
                             follow_redirects=False)
        assert r.status_code == 200
        html = r.text
        assert "name=\"otp_token\"" in html
        m = re.search(r'name="otp_token" value="([^"]+)"', html)
        assert m, "otp_token hidden maydon bo'lishi kerak"
        otp_token = m.group(1)

        # Noto'g'ri kod -> 401 va yana otp bosqichi
        r = auth_client.post("/login", data={"otp_token": otp_token, "otp_code": "000000"},
                             follow_redirects=False)
        assert r.status_code == 401
        assert "Google Authenticator kodi noto'g'ri" in r.text
        assert "name=\"otp_token\"" in r.text

        # To'g'ri kod -> sessiya ochiladi (cookie + redirect)
        r = auth_client.post("/login", data={"otp_token": otp_token,
                                             "otp_code": totp.totp_code(secret)},
                             follow_redirects=False)
        assert r.status_code == 303
        assert r.headers.get("location") == "/"
        assert "web_token=" in (r.headers.get("set-cookie") or "")

    def test_html_login_bad_otp_token(self, auth_client, session):
        _make_employee(session, password="parol1234")
        r = auth_client.post("/login", data={"otp_token": "soxta-token", "otp_code": "123456"},
                             follow_redirects=False)
        assert r.status_code == 401