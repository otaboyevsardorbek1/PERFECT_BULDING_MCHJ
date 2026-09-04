"""
Web dashboard parol tiklash flow testlari (self-service):

  so'rov berish -> admin tasdiqlaydi (kod) -> xodim kod bilan parolni yangilaydi
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
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
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
    """Real auth + in-memory DB"""
    from dashboard.app import app

    def _override_get_db():
        yield session

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


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestPasswordResetRequest:
    def test_unknown_phone_still_ok_no_leak(self, auth_client, session):
        # Telefon ro'yxatda bo'lmasa ham "qabul qilindi" deyiladi (raqam oshkor bo'lmaydi)
        r = auth_client.post("/api/password-reset/request", json={"phone": "+998999999999"})
        assert r.status_code == 200
        assert r.json()["success"] is True
        assert session.query(models.PasswordResetRequest).count() == 0

    def test_request_creates_pending(self, auth_client, session):
        _make_employee(session, phone="+998901234567", role="sotuvchi", password="parol1234")
        r = auth_client.post("/api/password-reset/request",
                             json={"phone": "+998901234567", "reason": "Parolni unutdim"})
        assert r.status_code == 200
        assert r.json()["success"] is True
        req = session.query(models.PasswordResetRequest).one()
        assert req.status == "pending"
        assert req.phone_number == "+998901234567"

    def test_duplicate_pending_not_created(self, auth_client, session):
        _make_employee(session, phone="+998901234567", role="sotuvchi", password="parol1234")
        auth_client.post("/api/password-reset/request", json={"phone": "+998901234567"})
        r = auth_client.post("/api/password-reset/request", json={"phone": "+998901234567"})
        assert r.status_code == 200
        assert session.query(models.PasswordResetRequest).count() == 1

    def test_request_requires_phone(self, auth_client):
        r = auth_client.post("/api/password-reset/request", json={})
        assert r.status_code == 400

    def test_phone_format_tolerant(self, auth_client, session):
        # 998901234567 (plus belgisisiz) ham topiladi
        _make_employee(session, phone="+998901234567", role="sotuvchi", password="parol1234")
        r = auth_client.post("/api/password-reset/request", json={"phone": "998901234567"})
        assert r.status_code == 200
        assert session.query(models.PasswordResetRequest).count() == 1


class TestPasswordResetAdmin:
    def _seed(self, session):
        _make_employee(session, name="Sotuvchi A", phone="+998900000001",
                       role="sotuvchi", password="parol1234")
        _make_employee(session, name="Direktor B", phone="+998900000002",
                       role="direktor", is_admin=True, password="direktor123")

    def test_non_admin_cannot_list(self, auth_client, session):
        self._seed(session)
        token = _login(auth_client, "+998900000001", "parol1234").json()["token"]
        r = auth_client.get("/api/password-reset/requests", headers=_auth(token))
        assert r.status_code == 403

    def test_non_admin_cannot_approve(self, auth_client, session):
        self._seed(session)
        token = _login(auth_client, "+998900000001", "parol1234").json()["token"]
        r = auth_client.post("/api/password-reset/1/approve", headers=_auth(token))
        assert r.status_code == 403

    def test_list_requires_admin(self, auth_client, session):
        self._seed(session)
        assert auth_client.get("/api/password-reset/requests").status_code == 401
        token = _login(auth_client, "+998900000002", "direktor123").json()["token"]
        r = auth_client.get("/api/password-reset/requests", headers=_auth(token))
        assert r.status_code == 200
        assert "requests" in r.json()

    def test_admin_approves_and_returns_code(self, auth_client, session):
        self._seed(session)
        auth_client.post("/api/password-reset/request", json={"phone": "+998900000001"})
        req = session.query(models.PasswordResetRequest).one()
        token = _login(auth_client, "+998900000002", "direktor123").json()["token"]

        r = auth_client.post(f"/api/password-reset/{req.id}/approve", headers=_auth(token))
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert len(body["reset_code"]) == 10
        assert body["expires_in_hours"] == 2
        session.refresh(req)
        assert req.status == "approved"
        assert req.reset_hash  # kod xeshlangan holda saqlanadi
        assert req.reset_hash != body["reset_code"]

    def test_approve_unknown_id(self, auth_client, session):
        self._seed(session)
        token = _login(auth_client, "+998900000002", "direktor123").json()["token"]
        r = auth_client.post("/api/password-reset/999999/approve", headers=_auth(token))
        assert r.status_code == 400

    def test_admin_can_reject(self, auth_client, session):
        self._seed(session)
        auth_client.post("/api/password-reset/request", json={"phone": "+998900000001"})
        req = session.query(models.PasswordResetRequest).one()
        token = _login(auth_client, "+998900000002", "direktor123").json()["token"]
        r = auth_client.post(f"/api/password-reset/{req.id}/reject", headers=_auth(token))
        assert r.status_code == 200
        session.refresh(req)
        assert req.status == "rejected"


class TestPasswordResetComplete:
    def _seed_with_request(self, auth_client, session):
        _make_employee(session, name="Sotuvchi A", phone="+998900000001",
                       role="sotuvchi", password="eski_parol1")
        _make_employee(session, name="Direktor B", phone="+998900000002",
                       role="direktor", is_admin=True, password="direktor123")
        auth_client.post("/api/password-reset/request", json={"phone": "+998900000001"})
        req = session.query(models.PasswordResetRequest).one()
        admin_token = _login(auth_client, "+998900000002", "direktor123").json()["token"]
        resp = auth_client.post(f"/api/password-reset/{req.id}/approve",
                                headers=_auth(admin_token)).json()
        return resp["reset_code"]

    def test_complete_changes_password(self, auth_client, session):
        code = self._seed_with_request(auth_client, session)
        r = auth_client.post("/api/password-reset/complete", json={
            "phone": "+998900000001", "code": code, "new_password": "yangi_parol9",
        })
        assert r.status_code == 200
        assert r.json()["success"] is True
        # Eski parol endi ishlamaydi, yangisi ishlaydi
        assert _login(auth_client, "+998900000001", "eski_parol1").status_code == 401
        assert _login(auth_client, "+998900000001", "yangi_parol9").status_code == 200
        req = session.query(models.PasswordResetRequest).one()
        assert req.status == "done"
        assert req.reset_hash is None  # kod bir marta ishlatilgan

    def test_complete_wrong_code(self, auth_client, session):
        self._seed_with_request(auth_client, session)
        r = auth_client.post("/api/password-reset/complete", json={
            "phone": "+998900000001", "code": "XXXXXXXXXX", "new_password": "yangi_parol9",
        })
        assert r.status_code == 400

    def test_complete_code_case_insensitive(self, auth_client, session):
        code = self._seed_with_request(auth_client, session)
        r = auth_client.post("/api/password-reset/complete", json={
            "phone": "+998900000001", "code": code.lower(), "new_password": "yangi_parol9",
        })
        assert r.status_code == 200

    def test_complete_short_password_rejected(self, auth_client, session):
        code = self._seed_with_request(auth_client, session)
        r = auth_client.post("/api/password-reset/complete", json={
            "phone": "+998900000001", "code": code, "new_password": "qisqa",
        })
        assert r.status_code == 400

    def test_complete_after_reject_fails(self, auth_client, session):
        _make_employee(session, name="Sotuvchi A", phone="+998900000001",
                       role="sotuvchi", password="eski_parol1")
        _make_employee(session, name="Direktor B", phone="+998900000002",
                       role="direktor", is_admin=True, password="direktor123")
        auth_client.post("/api/password-reset/request", json={"phone": "+998900000001"})
        req = session.query(models.PasswordResetRequest).one()
        admin_token = _login(auth_client, "+998900000002", "direktor123").json()["token"]
        auth_client.post(f"/api/password-reset/{req.id}/reject", headers=_auth(admin_token))

        r = auth_client.post("/api/password-reset/complete", json={
            "phone": "+998900000001", "code": "ABCDEFGHIJ", "new_password": "yangi_parol9",
        })
        assert r.status_code == 400

    def test_complete_expired_code(self, auth_client, session):
        code = self._seed_with_request(auth_client, session)
        req = session.query(models.PasswordResetRequest).one()
        req.code_expires_at = datetime.utcnow() - timedelta(minutes=1)
        session.commit()
        r = auth_client.post("/api/password-reset/complete", json={
            "phone": "+998900000001", "code": code, "new_password": "yangi_parol9",
        })
        assert r.status_code == 400

    def test_complete_revokes_web_sessions(self, auth_client, session):
        # Parol o'zgartirilgach barcha eski web sessiyalar revoke bo'ladi
        _make_employee(session, name="Sotuvchi A", phone="+998900000001",
                       role="sotuvchi", password="eski_parol1")
        _make_employee(session, name="Direktor B", phone="+998900000002",
                       role="direktor", is_admin=True, password="direktor123")
        old_token = _login(auth_client, "+998900000001", "eski_parol1").json()["token"]
        assert auth_client.get("/api/me", headers=_auth(old_token)).status_code == 200

        auth_client.post("/api/password-reset/request", json={"phone": "+998900000001"})
        req = session.query(models.PasswordResetRequest).one()
        admin_token = _login(auth_client, "+998900000002", "direktor123").json()["token"]
        code = auth_client.post(f"/api/password-reset/{req.id}/approve",
                                headers=_auth(admin_token)).json()["reset_code"]
        r = auth_client.post("/api/password-reset/complete", json={
            "phone": "+998900000001", "code": code, "new_password": "yangi_parol9",
        })
        assert r.status_code == 200
        # Eski access token ishlamaydi — sessiya revoke qilingan
        assert auth_client.get("/api/me", headers=_auth(old_token)).status_code == 401
        # Yangi parol bilan kirilgach ishlaydi
        new_token = _login(auth_client, "+998900000001", "yangi_parol9").json()["token"]
        assert auth_client.get("/api/me", headers=_auth(new_token)).status_code == 200

    def test_full_flow_employee_can_login_again(self, auth_client, session):
        code = self._seed_with_request(auth_client, session)
        r = auth_client.post("/api/password-reset/complete", json={
            "phone": "+998900000001", "code": code, "new_password": "parol12345",
        })
        assert r.status_code == 200
        login = _login(auth_client, "+998900000001", "parol12345")
        assert login.status_code == 200
        assert login.json()["refresh_token"]
