"""
CRM (mijozlar) v3 moduli testlari
"""
from datetime import datetime, timedelta
import pytest

from database import models, crud


@pytest.fixture
def sample_product(db_session):
    p = models.Product(name="CRM Test Sement", category="sement", unit="qop",
                       selling_price=12000, production_cost=7000, is_active=True)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


class TestCustomerCRUD:
    def test_create_customer(self, db_session):
        c = crud.create_customer(db_session, {
            "name": "Ali", "phone": "+998901234567", "credit_limit": 5000000
        })
        assert c.id is not None
        assert c.name == "Ali"
        assert c.credit_limit == 5000000
        assert c.total_debt == 0

    def test_get_by_phone(self, db_session):
        crud.create_customer(db_session, {"name": "Vali", "phone": "+998901234567"})
        found = crud.get_customer_by_phone(db_session, "+998901234567")
        assert found is not None and found.name == "Vali"

    def test_search(self, db_session):
        crud.create_customer(db_session, {"name": "Akmal Pudratchi", "phone": "+998901111111",
                                          "company": "Akmal MCHJ"})
        res = crud.search_customers(db_session, "akmal")
        assert len(res) == 1

    def test_list_limit(self, db_session):
        for i in range(5):
            crud.create_customer(db_session, {"name": f"Customer {i}"})
        all_c = crud.list_customers(db_session)
        assert len(all_c) == 5

    def test_update_customer(self, db_session):
        c = crud.create_customer(db_session, {"name": "Bobur", "credit_limit": 0})
        updated = crud.update_customer(db_session, c.id, {"credit_limit": 9000000, "is_wholesale": True})
        assert updated.credit_limit == 9000000
        assert updated.is_wholesale is True


class TestCreditLimit:
    def test_blocked_customer(self, db_session):
        c = crud.create_customer(db_session, {"name": "Blocked", "status": "bloklangan",
                                              "credit_limit": 10000000})
        result = crud.check_credit_limit(db_session, c, 5000)
        assert result["allowed"] is False
        assert "bloklangan" in result["reason"]

    def test_zero_limit_means_credit_off(self, db_session):
        c = crud.create_customer(db_session, {"name": "No Credit", "credit_limit": 0})
        result = crud.check_credit_limit(db_session, c, 1000)
        assert result["allowed"] is False

    def test_credit_within_limit(self, db_session):
        c = crud.create_customer(db_session, {"name": "OK Credit", "credit_limit": 1000000})
        result = crud.check_credit_limit(db_session, c, 500000)
        assert result["allowed"] is True
        assert result["free_limit"] == 1000000

    def test_credit_over_limit_blocks(self, db_session):
        c = crud.create_customer(db_session, {"name": "Over", "credit_limit": 1000000})
        result = crud.check_credit_limit(db_session, c, 2000000)
        assert result["allowed"] is False

    def test_existing_debt_reduces_free_limit(self, db_session):
        c = crud.create_customer(db_session, {"name": "Debtor", "credit_limit": 1000000})
        c.total_debt = 700000
        db_session.commit()
        result = crud.check_credit_limit(db_session, c, 400000)
        assert result["allowed"] is False
        result2 = crud.check_credit_limit(db_session, c, 200000)
        assert result2["allowed"] is True


class TestDebtPaymentFIFO:
    def _sale(self, db_session, customer, product, amount, days_ago=0):
        s = models.Sale(
            invoice_number=f"INV-FIFO-{datetime.utcnow().timestamp()}-{days_ago}",
            product_id=product.id, quantity=1, unit_price=amount,
            total_amount=amount, customer_id=customer.id,
            customer_name=customer.name, is_credit=True,
            paid_amount=0, credit_status="tolanmagan",
            sale_date=datetime.utcnow() - timedelta(days=days_ago),
            due_date=datetime.utcnow() + timedelta(days=30 - days_ago),
        )
        db_session.add(s)
        db_session.commit()
        db_session.refresh(s)
        return s

    def test_fifo_oldest_paid_first(self, db_session, sample_product):
        """Qarz to'langanda eng eski nasiya birinchi yopiladi"""
        customer = crud.create_customer(db_session, {"name": "FIFO", "credit_limit": 10_000_000})
        old = self._sale(db_session, customer, sample_product, 1_000_000, days_ago=40)
        new = self._sale(db_session, customer, sample_product, 1_000_000, days_ago=1)
        customer.total_debt = 2_000_000
        db_session.commit()

        crud.pay_customer_debt(db_session, customer.id, 1_000_000, method="cash")
        db_session.refresh(old)
        db_session.refresh(new)
        assert old.credit_status == "toliq_tolangan"
        assert new.credit_status == "tolanmagan"

    def test_partial_payment_updates_debt(self, db_session, sample_product):
        customer = crud.create_customer(db_session, {"name": "FIFO Client", "credit_limit": 10_000_000})
        sale = self._sale(db_session, customer, sample_product, 2_000_000)
        customer.total_debt = 2_000_000
        db_session.commit()

        result = crud.pay_customer_debt(db_session, customer.id, 500_000, method="cash")
        assert result["paid"] == 500_000
        assert result["new_debt"] == 1_500_000

        db_session.refresh(sale)
        assert sale.paid_amount == 500_000
        assert sale.credit_status == "qisman"

    def test_full_payment_marks_paid(self, db_session, sample_product):
        customer = crud.create_customer(db_session, {"name": "Full", "credit_limit": 5_000_000})
        sale = self._sale(db_session, customer, sample_product, 1_000_000)
        customer.total_debt = 1_000_000
        db_session.commit()

        crud.pay_customer_debt(db_session, customer.id, 1_000_000, method="card")
        db_session.refresh(sale)
        assert sale.credit_status == "toliq_tolangan"
        assert sale.paid_amount == 1_000_000

    def test_overpayment_is_clamped(self, db_session, sample_product):
        customer = crud.create_customer(db_session, {"name": "Overpay", "credit_limit": 5_000_000})
        self._sale(db_session, customer, sample_product, 800_000)
        customer.total_debt = 800_000
        db_session.commit()
        result = crud.pay_customer_debt(db_session, customer.id, 5_000_000)
        assert result["paid"] == 800_000
        assert result["new_debt"] == 0


class TestLoyaltyPoints:
    def test_points_accumulate(self, db_session):
        customer = crud.create_customer(db_session, {"name": "Loyal"})
        points = crud.add_loyalty_points(db_session, customer, 2_000_000)
        assert points == 20  # 100 ming so'm -> 1 ball
        db_session.refresh(customer)
        assert customer.loyalty_points == 20

    def test_points_sum(self, db_session):
        customer = crud.create_customer(db_session, {"name": "Loyal2"})
        crud.add_loyalty_points(db_session, customer, 1_000_000)
        crud.add_loyalty_points(db_session, customer, 500_000)
        db_session.refresh(customer)
        assert customer.loyalty_points == 15
