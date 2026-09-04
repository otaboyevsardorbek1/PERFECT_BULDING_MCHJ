"""
💳 Onlayn to'lovlar (Click / Payme) testlari

- Click SHOP API: prepare/complete, MD5 imzo (2 xil formula), xatolik kodlari
- Payme Merchant API: JSON-RPC 2.0, Basic auth, barcha metodlar
- API: schyot-faktura yaratish va ro'yxat
"""
import hashlib
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import models
from database.session import get_db


@pytest.fixture
def payment_env(monkeypatch):
    """Webhook imzo tekshiruvi uchun test kalitlari"""
    from dashboard import payments as p

    monkeypatch.setattr(p, "CLICK_MERCHANT_ID", "12345")
    monkeypatch.setattr(p, "CLICK_SERVICE_ID", "67890")
    monkeypatch.setattr(p, "CLICK_SECRET_KEY", "SECRET_TEST_KEY")
    monkeypatch.setattr(p, "PAYME_MERCHANT_ID", "5e45f1e1d1a1b1c1d1e1f1a1")
    monkeypatch.setattr(p, "PAYME_KEY", "PAYME_TEST_KEY")
    return p


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
def client(session):
    """Webhook'lar uchun TestClient (auth talab qilmaydi)"""
    from dashboard.app import app

    def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _make_invoice(session, *, gateway="click", amount=50000, customer=None):
    inv = models.PaymentInvoice(
        invoice_id=f"INV-TEST-{gateway}-{datetime.now().timestamp():.0f}",
        gateway=gateway,
        amount=amount,
        status="pending",
        customer_id=customer.id if customer else None,
        customer_name=customer.name if customer else None,
    )
    session.add(inv)
    session.commit()
    session.refresh(inv)
    return inv


# ============================================================
# IMZO (SIGNATURE) TEKSHIRUVI
# ============================================================

class TestClickSignatures:
    def test_prepare_signature_formula(self, payment_env):
        """Prepare imzosi: click_trans_id + service_id + SECRET + merchant_trans_id + amount + action + sign_time"""
        params = {
            "click_trans_id": "123",
            "service_id": "67890",
            "merchant_trans_id": "INV-1",
            "amount": "50000",
            "action": "0",
            "sign_time": "2024-01-01 12:00:00",
        }
        raw = "12367890SECRET_TEST_KEYINV-15000002024-01-01 12:00:00"
        expected = hashlib.md5(raw.encode("utf-8")).hexdigest()
        assert payment_env._click_sign(params, prepare=True) == expected

    def test_complete_signature_includes_prepare_id(self, payment_env):
        """Complete imzosi prepare'dan farq qiladi: merchant_prepare_id ham qo'shiladi"""
        params = {
            "click_trans_id": "123",
            "service_id": "67890",
            "merchant_trans_id": "INV-1",
            "merchant_prepare_id": "999",
            "amount": "50000",
            "action": "1",
            "sign_time": "2024-01-01 12:00:00",
        }
        raw = "12367890SECRET_TEST_KEYINV-19995000012024-01-01 12:00:00"
        expected = hashlib.md5(raw.encode("utf-8")).hexdigest()
        assert payment_env._click_sign(params, prepare=False) == expected
        # Prepare formulasi bilan bir xil EMAS
        assert payment_env._click_sign(params, prepare=False) != payment_env._click_sign(
            {k: v for k, v in params.items() if k != "merchant_prepare_id"}, prepare=True
        )


# ============================================================
# CLICK WEBHOOK
# ============================================================

def _click_form(payment_env, *, action=0, invoice_id="INV-TEST-CLICK-1",
                amount="50000", sign_time="2024-01-01 12:00:00", error="0",
                merchant_prepare_id="", click_trans_id="1001"):
    params = {
        "click_trans_id": click_trans_id,
        "service_id": payment_env.CLICK_SERVICE_ID,
        "click_paydoc_id": "2222",
        "merchant_trans_id": invoice_id,
        "amount": amount,
        "action": str(action),
        "error": error,
        "error_note": "",
        "sign_time": sign_time,
    }
    if action == 1:
        params["merchant_prepare_id"] = merchant_prepare_id or "0"
    params["sign_string"] = payment_env._click_sign(params, prepare=(action == 0))
    return params


class TestClickWebhook:
    def test_prepare_success(self, client, session, payment_env):
        inv = _make_invoice(session, gateway="click")
        r = client.post("/api/payments/click", data=_click_form(
            payment_env, action=0, invoice_id=inv.invoice_id))
        assert r.status_code == 200
        body = r.json()
        assert body["error"] == 0
        assert body["merchant_trans_id"] == inv.invoice_id
        assert body["merchant_prepare_id"]
        # merchant_prepare_id 32-bit int
        assert 0 <= int(body["merchant_prepare_id"]) < 2147483647

    def test_prepare_returns_same_prepare_id_on_retry(self, client, session, payment_env):
        """Qayta chaqiruvda bir xil merchant_prepare_id qaytadi (idempotent)"""
        inv = _make_invoice(session, gateway="click")
        form = _click_form(payment_env, action=0, invoice_id=inv.invoice_id)
        first = client.post("/api/payments/click", data=form).json()
        second = client.post("/api/payments/click", data=form).json()
        assert first["merchant_prepare_id"] == second["merchant_prepare_id"]
        assert first["error"] == 0 and second["error"] == 0

    def test_prepare_bad_signature(self, client, session, payment_env):
        inv = _make_invoice(session, gateway="click")
        form = _click_form(payment_env, action=0, invoice_id=inv.invoice_id)
        form["sign_string"] = "0" * 32  # noto'g'ri imzo
        body = client.post("/api/payments/click", data=form).json()
        assert body["error"] == -1  # SIGN CHECK FAILED

    def test_prepare_unknown_invoice(self, client, session, payment_env):
        form = _click_form(payment_env, action=0, invoice_id="NOMAVJUD")
        body = client.post("/api/payments/click", data=form).json()
        assert body["error"] == -5  # USER NOT FOUND

    def test_prepare_wrong_amount(self, client, session, payment_env):
        inv = _make_invoice(session, gateway="click", amount=50000)
        form = _click_form(payment_env, action=0, invoice_id=inv.invoice_id, amount="99999")
        body = client.post("/api/payments/click", data=form).json()
        assert body["error"] == -2  # INCORRECT AMOUNT

    def test_complete_success_marks_paid(self, client, session, payment_env):
        inv = _make_invoice(session, gateway="click", amount=50000)
        # Avval prepare qilinadi (merchant_prepare_id olinadi)
        prep = client.post("/api/payments/click", data=_click_form(
            payment_env, action=0, invoice_id=inv.invoice_id)).json()
        prepare_id = prep["merchant_prepare_id"]

        r = client.post("/api/payments/click", data=_click_form(
            payment_env, action=1, invoice_id=inv.invoice_id,
            merchant_prepare_id=prepare_id))
        assert r.status_code == 200
        body = r.json()
        assert body["error"] == 0
        assert body["merchant_confirm_id"]

        session.expire_all()
        inv2 = session.query(models.PaymentInvoice).filter(
            models.PaymentInvoice.id == inv.id).first()
        assert inv2.status == "paid"
        assert inv2.paid_at is not None

    def test_complete_already_paid_returns_minus4(self, client, session, payment_env):
        """Idempotentlik: takroriy complete -> -4 (Already paid), 0 emas"""
        inv = _make_invoice(session, gateway="click", amount=50000)
        prep = client.post("/api/payments/click", data=_click_form(
            payment_env, action=0, invoice_id=inv.invoice_id)).json()
        prepare_id = prep["merchant_prepare_id"]
        form = _click_form(payment_env, action=1, invoice_id=inv.invoice_id,
                           merchant_prepare_id=prepare_id)
        first = client.post("/api/payments/click", data=form).json()
        second = client.post("/api/payments/click", data=form).json()
        assert first["error"] == 0
        assert second["error"] == -4  # Already paid

    def test_complete_error_negative_is_failure(self, client, session, payment_env):
        """Complete'da error < 0 bo'lsa to'lov muvaffaqiyatsiz -> cancelled"""
        inv = _make_invoice(session, gateway="click", amount=50000)
        prep = client.post("/api/payments/click", data=_click_form(
            payment_env, action=0, invoice_id=inv.invoice_id)).json()
        prepare_id = prep["merchant_prepare_id"]

        form = _click_form(payment_env, action=1, invoice_id=inv.invoice_id,
                           merchant_prepare_id=prepare_id, error="-9")
        body = client.post("/api/payments/click", data=form).json()
        assert body["error"] == -9  # Transaction cancelled

        session.expire_all()
        inv2 = session.query(models.PaymentInvoice).filter(
            models.PaymentInvoice.id == inv.id).first()
        assert inv2.status == "cancelled"

    def test_complete_unknown_action(self, client, session, payment_env):
        inv = _make_invoice(session, gateway="click")
        form = _click_form(payment_env, action=5, invoice_id=inv.invoice_id)
        body = client.post("/api/payments/click", data=form).json()
        assert body["error"] == -3  # ACTION NOT FOUND


# ============================================================
# PAYME WEBHOOK (JSON-RPC 2.0)
# ============================================================

def _payme_headers(payment_env):
    import base64
    token = base64.b64encode(
        f"{payment_env.PAYME_MERCHANT_ID}:{payment_env.PAYME_KEY}".encode("utf-8")
    ).decode("utf-8")
    return {"X-Authorization": f"Basic {token}"}


def _payme_body(method, params, rpc_id=1):
    return {"jsonrpc": "2.0", "id": rpc_id, "method": method, "params": params}


def _payme_account(invoice_id):
    return {"order_id": invoice_id}


class TestPaymeWebhook:
    def test_auth_required(self, client, session, payment_env):
        r = client.post("/api/payments/payme", json=_payme_body("CheckPerformTransaction", {}))
        assert r.status_code == 401

    def test_bad_auth_rejected(self, client, session, payment_env):
        import base64
        bad = base64.b64encode(b"wrong:wrong").decode("utf-8")
        r = client.post("/api/payments/payme", json=_payme_body("CheckPerformTransaction", {}),
                        headers={"X-Authorization": f"Basic {bad}"})
        assert r.status_code == 401

    def test_check_perform_allow(self, client, session, payment_env):
        inv = _make_invoice(session, gateway="payme", amount=50000)
        r = client.post("/api/payments/payme",
                        json=_payme_body("CheckPerformTransaction", {
                            "amount": 5000000,  # tiyin: 50000 UZS * 100
                            "account": _payme_account(inv.invoice_id),
                        }),
                        headers=_payme_headers(payment_env))
        assert r.status_code == 200
        assert r.json()["result"] == {"allow": True}

    def test_check_perform_wrong_amount(self, client, session, payment_env):
        inv = _make_invoice(session, gateway="payme", amount=50000)
        r = client.post("/api/payments/payme",
                        json=_payme_body("CheckPerformTransaction", {
                            "amount": 999999,
                            "account": _payme_account(inv.invoice_id),
                        }),
                        headers=_payme_headers(payment_env))
        assert r.status_code == 200
        assert r.json()["error"]["code"] == -31001  # Noto'g'ri summa

    def test_check_perform_unknown_order(self, client, session, payment_env):
        r = client.post("/api/payments/payme",
                        json=_payme_body("CheckPerformTransaction", {
                            "amount": 100000,
                            "account": _payme_account("NOMAVJUD"),
                        }),
                        headers=_payme_headers(payment_env))
        assert r.status_code == 200
        assert r.json()["error"]["code"] == -31050  # Buyurtma topilmadi

    def test_create_transaction(self, client, session, payment_env):
        inv = _make_invoice(session, gateway="payme", amount=50000)
        r = client.post("/api/payments/payme",
                        json=_payme_body("CreateTransaction", {
                            "id": "5305e3bab097f420a62ced0b",
                            "time": 1399114284039,
                            "amount": 5000000,
                            "account": _payme_account(inv.invoice_id),
                        }),
                        headers=_payme_headers(payment_env))
        assert r.status_code == 200
        result = r.json()["result"]
        assert result["state"] == 1  # created
        assert result["transaction"] == inv.invoice_id
        assert result["create_time"] > 0

    def test_create_transaction_idempotent(self, client, session, payment_env):
        inv = _make_invoice(session, gateway="payme", amount=50000)
        body = _payme_body("CreateTransaction", {
            "id": "5305e3bab097f420a62ced0b",
            "time": 1399114284039,
            "amount": 5000000,
            "account": _payme_account(inv.invoice_id),
        })
        headers = _payme_headers(payment_env)
        first = client.post("/api/payments/payme", json=body, headers=headers).json()
        second = client.post("/api/payments/payme", json=body, headers=headers).json()
        assert first["result"] == second["result"]

    def test_perform_transaction_marks_paid(self, client, session, payment_env):
        inv = _make_invoice(session, gateway="payme", amount=50000)
        headers = _payme_headers(payment_env)
        client.post("/api/payments/payme", json=_payme_body("CreateTransaction", {
            "id": "tx1", "time": 1, "amount": 5000000,
            "account": _payme_account(inv.invoice_id),
        }), headers=headers)

        r = client.post("/api/payments/payme", json=_payme_body("PerformTransaction", {
            "id": "tx1", "time": 2, "account": _payme_account(inv.invoice_id),
        }), headers=headers)
        assert r.status_code == 200
        result = r.json()["result"]
        assert result["state"] == 2  # performed

        session.expire_all()
        inv2 = session.query(models.PaymentInvoice).filter(
            models.PaymentInvoice.id == inv.id).first()
        assert inv2.status == "paid"
        assert inv2.paid_at is not None

    def test_cancel_transaction_by_user(self, client, session, payment_env):
        inv = _make_invoice(session, gateway="payme", amount=50000)
        r = client.post("/api/payments/payme", json=_payme_body("CancelTransaction", {
            "id": "tx1", "time": 2, "reason": 1,
            "account": _payme_account(inv.invoice_id),
        }), headers=_payme_headers(payment_env))
        assert r.status_code == 200
        assert r.json()["result"]["state"] == -1  # user bekor qildi

    def test_cancel_transaction_timeout(self, client, session, payment_env):
        inv = _make_invoice(session, gateway="payme", amount=50000)
        r = client.post("/api/payments/payme", json=_payme_body("CancelTransaction", {
            "id": "tx1", "time": 2, "reason": 4,  # timeout
            "account": _payme_account(inv.invoice_id),
        }), headers=_payme_headers(payment_env))
        assert r.status_code == 200
        assert r.json()["result"]["state"] == -2  # timeout

    def test_check_transaction_state(self, client, session, payment_env):
        inv = _make_invoice(session, gateway="payme", amount=50000)
        headers = _payme_headers(payment_env)
        client.post("/api/payments/payme", json=_payme_body("CreateTransaction", {
            "id": "tx1", "time": 1, "amount": 5000000,
            "account": _payme_account(inv.invoice_id),
        }), headers=headers)
        r = client.post("/api/payments/payme", json=_payme_body("CheckTransaction", {
            "id": "tx1", "time": 3, "account": _payme_account(inv.invoice_id),
        }), headers=headers)
        assert r.status_code == 200
        assert r.json()["result"]["state"] == 1

    def test_unknown_method(self, client, session, payment_env):
        r = client.post("/api/payments/payme",
                        json=_payme_body("NotAMethod", {}),
                        headers=_payme_headers(payment_env))
        assert r.status_code == 200
        assert r.json()["error"]["code"] == -32601  # Method not found


# ============================================================
# API: SCHYOT-FAKTURA YARATISH
# ============================================================

class TestInvoiceAPI:
    def test_create_invoice_returns_links(self, client, session, payment_env):
        # Auth override: direktor
        from dashboard.auth import get_current_user

        class _Admin:
            id = 1
            full_name = "Test Admin"
            phone = "+998000000000"
            telegram_id = 123456789
            is_admin = True
            role = "direktor"

            def to_dict(self):
                return {"id": self.id, "full_name": self.full_name,
                        "role": self.role, "permissions": {"can_view": [], "can_edit": [], "see_cost": True}}

        client.app.dependency_overrides[get_current_user] = lambda: _Admin()

        r = client.post("/api/payments/invoice", json={
            "gateway": "click", "amount": 75000, "customer_name": "Test Mijoz",
        })
        assert r.status_code == 200
        body = r.json()
        assert "invoice" in body and "links" in body
        assert body["invoice"]["gateway"] == "click"
        assert body["invoice"]["status"] == "pending"
        assert "my.click.uz/services/pay" in body["links"]["click"]
        assert "transaction_param=" in body["links"]["click"]

    def test_create_payme_invoice_link(self, client, session, payment_env):
        from dashboard.auth import get_current_user

        class _Admin:
            id = 1
            full_name = "Test Admin"
            phone = "+998000000000"
            telegram_id = 123456789
            is_admin = True
            role = "direktor"

            def to_dict(self):
                return {"id": self.id, "full_name": self.full_name,
                        "role": self.role, "permissions": {"can_view": [], "can_edit": [], "see_cost": True}}

        client.app.dependency_overrides[get_current_user] = lambda: _Admin()

        r = client.post("/api/payments/invoice", json={
            "gateway": "payme", "amount": 75000,
        })
        assert r.status_code == 200
        body = r.json()
        assert "checkout.paycom.uz" in body["links"]["payme"]

    def test_create_invoice_invalid_amount(self, client, session, payment_env):
        from dashboard.auth import get_current_user

        class _Admin:
            id = 1
            full_name = "Test Admin"
            phone = "+998000000000"
            telegram_id = 123456789
            is_admin = True
            role = "direktor"

            def to_dict(self):
                return {"id": self.id, "full_name": self.full_name,
                        "role": self.role, "permissions": {"can_view": [], "can_edit": [], "see_cost": True}}

        client.app.dependency_overrides[get_current_user] = lambda: _Admin()

        r = client.post("/api/payments/invoice", json={"gateway": "click", "amount": -5})
        assert r.status_code == 400

    def test_list_invoices(self, client, session, payment_env):
        from dashboard.auth import get_current_user

        class _Admin:
            id = 1
            full_name = "Test Admin"
            phone = "+998000000000"
            telegram_id = 123456789
            is_admin = True
            role = "direktor"

            def to_dict(self):
                return {"id": self.id, "full_name": self.full_name,
                        "role": self.role, "permissions": {"can_view": [], "can_edit": [], "see_cost": True}}

        client.app.dependency_overrides[get_current_user] = lambda: _Admin()
        _make_invoice(session, gateway="click", amount=10000)
        _make_invoice(session, gateway="payme", amount=20000)

        r = client.get("/api/payments/invoices")
        assert r.status_code == 200
        assert len(r.json()["invoices"]) == 2