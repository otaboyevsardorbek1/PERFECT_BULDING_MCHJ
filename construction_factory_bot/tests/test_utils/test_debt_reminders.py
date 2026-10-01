"""
NASIYA QARZ SMS ESLATMALARI (3/7/14/30 kun) testlari

check_debt_reminders() fon vazifasi har 5 daqiqada chaqiriladi; har bir
(sotuv, kun-chegara) uchun eslatma BIR MARTA yuboriladi (DebtReminder unikalligi).
"""
from datetime import datetime, timedelta

import pytest

from database import models, crud


class FakeSmsService:
    """Yuborilgan SMSlarni to'playdigan fake — tarmoqqa chiqmaydi"""

    def __init__(self):
        self.sent = []

    async def send_sms(self, phone_number: str, message: str):
        self.sent.append({"phone": phone_number, "message": message})
        return {"success": True, "id": len(self.sent)}


@pytest.fixture
def product(db_session):
    p = models.Product(name="Qarz Sement", category="sement", unit="qop",
                       selling_price=12000, production_cost=7000, is_active=True)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def customer(db_session):
    return crud.create_customer(db_session, {
        "name": "Qarz Mijoz", "phone": "+998901122333", "credit_limit": 50_000_000,
    })


def _credit_sale(db_session, product, customer, amount=1_200_000, days_overdue=5):
    """Muddati o'tgan nasiya sotuv (to'liq qarz, avanssiz)"""
    sale = crud.create_sale_record(
        db_session, product_id=product.id, quantity=int(amount / 12000),
        unit_price=12000, total_amount=amount, payment_method="credit",
        advance_amount=0, customer=customer, customer_name=customer.name,
        customer_phone=customer.phone, user_id=7, user_name="Sotuvchi",
    )
    sale.due_date = datetime.utcnow() - timedelta(days=days_overdue)
    db_session.commit()
    db_session.refresh(sale)
    return sale


@pytest.fixture
def sms_env(monkeypatch):
    """SMS yoqilgan + 3 kunlik chegara + fake sms xizmati"""
    from config import INTEGRATION_SETTINGS
    monkeypatch.setitem(INTEGRATION_SETTINGS, "sms_enabled", True)
    monkeypatch.setattr("config.DEBT_REMINDER_DAYS", [3])
    import utils.sms_service as sms_mod
    fake = FakeSmsService()
    monkeypatch.setattr(sms_mod, "sms_service", fake)
    return fake


class TestDebtReminderCandidates:
    def test_candidate_when_bucket_reached(self, db_session, product, customer):
        sale = _credit_sale(db_session, product, customer, days_overdue=5)
        cands = crud.get_debt_reminder_candidates(db_session, 3)
        assert any(s.id == sale.id for s in cands)

    def test_no_candidate_before_bucket(self, db_session, product, customer):
        sale = _credit_sale(db_session, product, customer, days_overdue=2)
        cands = crud.get_debt_reminder_candidates(db_session, 3)
        assert all(s.id != sale.id for s in cands)

    def test_paid_sale_excluded(self, db_session, product, customer):
        sale = _credit_sale(db_session, product, customer, days_overdue=10)
        sale.paid_amount = sale.total_amount
        sale.credit_status = models.CreditStatus.PAID.value
        db_session.commit()
        cands = crud.get_debt_reminder_candidates(db_session, 3)
        assert all(s.id != sale.id for s in cands)

    def test_fully_returned_sale_excluded(self, db_session, product, customer):
        sale = _credit_sale(db_session, product, customer, days_overdue=10)
        crud.create_return_act(db_session, sale_id=sale.id, quantity=sale.quantity,
                               refund_type="cash", user_name="Sotuvchi")
        cands = crud.get_debt_reminder_candidates(db_session, 3)
        assert all(s.id != sale.id for s in cands)

    def test_already_reminded_sale_excluded(self, db_session, product, customer):
        sale = _credit_sale(db_session, product, customer, days_overdue=10)
        crud.mark_debt_reminder_sent(db_session, sale.id, 3)
        cands = crud.get_debt_reminder_candidates(db_session, 3)
        assert all(s.id != sale.id for s in cands)


class TestCheckDebtReminders:
    async def test_sends_once_per_sale_bucket(self, db_session, product, customer, sms_env):
        sale = _credit_sale(db_session, product, customer, days_overdue=10)
        from utils.notifications import check_debt_reminders

        count = await check_debt_reminders(db_session)
        assert count == 1
        assert len(sms_env.sent) == 1
        assert "1,200,000" in sms_env.sent[0]["message"]
        assert "3 kun" in sms_env.sent[0]["message"]
        assert sale.customer_phone in sms_env.sent[0]["phone"]

        row = db_session.query(models.DebtReminder).filter(
            models.DebtReminder.sale_id == sale.id,
            models.DebtReminder.day_bucket == 3,
        ).first()
        assert row is not None
        assert row.status == "sent"

        # Ikkinchi chaqiruvda takror yuborilmaydi
        count2 = await check_debt_reminders(db_session)
        assert count2 == 0
        assert len(sms_env.sent) == 1

    async def test_groups_multiple_sales_into_one_sms(self, db_session, product, customer, sms_env):
        s1 = _credit_sale(db_session, product, customer, amount=1_200_000, days_overdue=10)
        s2 = _credit_sale(db_session, product, customer, amount=2_400_000, days_overdue=10)
        from utils.notifications import check_debt_reminders

        count = await check_debt_reminders(db_session)
        assert count == 2              # ikkala sotuv eslatildi
        assert len(sms_env.sent) == 1  # lekin bitta SMS'da (bitta mijoz)
        assert s1.invoice_number in sms_env.sent[0]["message"]
        assert s2.invoice_number in sms_env.sent[0]["message"]
        assert "3,600,000" in sms_env.sent[0]["message"]  # jami qarz

    async def test_no_candidates_no_send(self, db_session, product, customer, sms_env):
        _credit_sale(db_session, product, customer, days_overdue=2)  # hali 3 kun emas
        from utils.notifications import check_debt_reminders
        assert await check_debt_reminders(db_session) == 0
        assert sms_env.sent == []

    async def test_sms_disabled_returns_zero(self, db_session, product, customer, monkeypatch):
        from config import INTEGRATION_SETTINGS
        monkeypatch.setitem(INTEGRATION_SETTINGS, "sms_enabled", False)
        import utils.sms_service as sms_mod
        fake = FakeSmsService()
        monkeypatch.setattr(sms_mod, "sms_service", fake)

        _credit_sale(db_session, product, customer, days_overdue=10)
        from utils.notifications import check_debt_reminders
        assert await check_debt_reminders(db_session) == 0
        assert fake.sent == []

    async def test_failed_send_marked_failed_and_retried(self, db_session, product, customer, monkeypatch):
        from config import INTEGRATION_SETTINGS
        monkeypatch.setitem(INTEGRATION_SETTINGS, "sms_enabled", True)
        monkeypatch.setattr("config.DEBT_REMINDER_DAYS", [3])
        import utils.sms_service as sms_mod

        class FailingSms:
            def __init__(self):
                self.calls = 0
            async def send_sms(self, phone_number, message):
                self.calls += 1
                if self.calls == 1:
                    return {"success": False, "error": "Xato"}
                return {"success": True}

        fake = FailingSms()
        monkeypatch.setattr(sms_mod, "sms_service", fake)

        sale = _credit_sale(db_session, product, customer, days_overdue=10)
        from utils.notifications import check_debt_reminders

        assert await check_debt_reminders(db_session) == 0  # birinchi urinish muvaffaqiyatsiz
        row = db_session.query(models.DebtReminder).filter(
            models.DebtReminder.sale_id == sale.id,
            models.DebtReminder.day_bucket == 3,
        ).first()
        assert row is not None and row.status == "failed"

        # Muvaffaqiyatsiz eslatma har 5 daqiqada qayta urinilmaydi (spam bo'lmasligi uchun):
        # yozuv 'failed' bo'lib qoladi va navbatdagi eslatma keyingi kun oralig'ida (7/14/30)
        # yuboriladi. Keyingi tekshiruvda yangi SMS jo'natilmaydi.
        assert await check_debt_reminders(db_session) == 0
        assert fake.calls == 1
