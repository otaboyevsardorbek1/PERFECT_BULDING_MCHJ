"""
ARALASH TO'LOV (mixed payment): bitta chekda naqd + karta (+ nasiya).

create_sale_record(payments=[{"method": ..., "amount": ...}, ...]) qo'llab-quvvatlashi:
- Har bir usul uchun alohida Payment yozuvi (Sale.payment_method = "mixed")
- "credit" qismi mijoz qarziga yoziladi (is_credit=True, 30 kun muddat)
- Sodiqlik ballari faqat haqiqatda olingan pulga (paid qismga) beriladi
- Summalar jami final_total ga teng bo'lmasa / usul noto'g'ri bo'lsa xatolik
- Kassir smenasida kutilgan naqdga faqat naqd qismi tushadi
"""
from datetime import datetime, timedelta

import pytest

from database import models, crud


@pytest.fixture
def product(db_session):
    p = models.Product(name="Mix Sement M500", category="sement", unit="qop",
                       selling_price=12000, production_cost=7000, is_active=True)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def customer(db_session):
    return crud.create_customer(db_session, {
        "name": "Aralash Mijoz", "phone": "+998902223344", "credit_limit": 20_000_000,
    })


@pytest.fixture
def cashier(db_session):
    emp = models.Employee(
        telegram_id=7002, full_name="Kassir Malika", phone_number="+998901234702",
        position="Kassir", department="sales",
        status=models.EmployeeStatus.ACTIVE, hire_date=datetime.utcnow(),
        role="kassir",
    )
    db_session.add(emp)
    db_session.commit()
    db_session.refresh(emp)
    return emp


def _payment_rows(db_session):
    return db_session.query(models.Payment).order_by(models.Payment.id).all()


class TestCashCardSplit:
    def test_cash_card_split_creates_two_payment_rows(self, db_session, product, customer):
        """700k naqd + 500k karta = 1.2M: ikkita Payment yozuvi, qarz yo'q"""
        sale = crud.create_sale_record(
            db_session, product_id=product.id, quantity=100, unit_price=12000,
            total_amount=1_200_000, payment_method="mixed",
            payments=[{"method": "cash", "amount": 700_000},
                      {"method": "card", "amount": 500_000}],
            customer=customer, customer_name=customer.name,
            user_id=7, user_name="Sotuvchi",
        )
        assert sale.payment_method == "mixed"
        assert sale.is_credit is False
        assert sale.paid_amount == 1_200_000
        assert sale.total_amount == 1_200_000
        assert sale.credit_status == "toliq_tolangan"
        assert sale.due_date is None

        payments = _payment_rows(db_session)
        assert len(payments) == 2
        by_method = {p.method: p.amount for p in payments}
        assert by_method == {"cash": 700_000, "card": 500_000}
        assert all(p.payment_type == "sale" for p in payments)
        assert all("aralash" in (p.note or "") for p in payments)

        db_session.refresh(customer)
        assert customer.total_debt == 0
        assert customer.total_purchases == 1_200_000
        assert customer.loyalty_points == 12  # 1.2M / 100k

    def test_all_cash_via_mixed(self, db_session, product, customer):
        """Aralash tanlangan, lekin hammasi naqd bo'lsa — bitta Payment yozuvi"""
        sale = crud.create_sale_record(
            db_session, product_id=product.id, quantity=10, unit_price=12000,
            total_amount=120_000, payment_method="mixed",
            payments=[{"method": "cash", "amount": 120_000}],
            customer=customer, customer_name=customer.name,
            user_id=7, user_name="Sotuvchi",
        )
        assert sale.paid_amount == 120_000
        payments = _payment_rows(db_session)
        assert len(payments) == 1
        assert payments[0].method == "cash"
        assert payments[0].amount == 120_000

    def test_mixed_with_discount(self, db_session, product, customer):
        """Chegirma final_total ni kamaytiradi, qismlar yig'indisi shunga teng bo'lishi shart"""
        sale = crud.create_sale_record(
            db_session, product_id=product.id, quantity=100, unit_price=10_000,
            total_amount=1_000_000, discount_amount=100_000, payment_method="mixed",
            payments=[{"method": "cash", "amount": 400_000},
                      {"method": "card", "amount": 500_000}],
            customer=customer, customer_name=customer.name,
            user_id=7, user_name="Sotuvchi",
        )
        assert sale.total_amount == 900_000
        assert sale.paid_amount == 900_000
        db_session.refresh(customer)
        assert customer.loyalty_points == 9


class TestCashCardNasiya:
    def test_credit_portion_creates_debt(self, db_session, product, customer):
        """1M naqd + 1M karta + 1M nasiya = 3M: qarz faqat nasiya qismiga"""
        sale = crud.create_sale_record(
            db_session, product_id=product.id, quantity=250, unit_price=12000,
            total_amount=3_000_000, payment_method="mixed",
            payments=[{"method": "cash", "amount": 1_000_000},
                      {"method": "card", "amount": 1_000_000},
                      {"method": "credit", "amount": 1_000_000}],
            customer=customer, customer_name=customer.name,
            user_id=7, user_name="Sotuvchi",
        )
        assert sale.payment_method == "mixed"
        assert sale.is_credit is True
        assert sale.paid_amount == 2_000_000
        assert sale.credit_status == "tolanmagan"
        assert sale.due_date is not None
        now = datetime.utcnow()
        assert now + timedelta(days=29) < sale.due_date < now + timedelta(days=31)

        db_session.refresh(customer)
        assert customer.total_debt == 1_000_000
        assert customer.loyalty_points == 20  # faqat to'langan 2M ga

        payments = _payment_rows(db_session)
        assert len(payments) == 2  # nasiya qismi Payment yozuvi emas
        by_method = {p.method: p.amount for p in payments}
        assert by_method == {"cash": 1_000_000, "card": 1_000_000}

    def test_credit_portion_paid_fifo(self, db_session, product, customer):
        """Aralash nasiya qismini pay_customer_debt orqali FIFO yopish"""
        sale = crud.create_sale_record(
            db_session, product_id=product.id, quantity=250, unit_price=12000,
            total_amount=3_000_000, payment_method="mixed",
            payments=[{"method": "cash", "amount": 1_000_000},
                      {"method": "card", "amount": 1_000_000},
                      {"method": "credit", "amount": 1_000_000}],
            customer=customer, customer_name=customer.name,
            user_id=7, user_name="Sotuvchi",
        )
        crud.pay_customer_debt(db_session, customer.id, 400_000, method="cash",
                               created_by="Kassir")
        db_session.refresh(sale)
        assert sale.paid_amount == 2_400_000
        assert sale.credit_status == models.CreditStatus.PARTIAL.value

        crud.pay_customer_debt(db_session, customer.id, 600_000, method="cash",
                               created_by="Kassir")
        db_session.refresh(sale)
        db_session.refresh(customer)
        assert sale.paid_amount == 3_000_000
        assert sale.credit_status == models.CreditStatus.PAID.value
        assert customer.total_debt == 0


class TestValidation:
    def test_sum_below_total_raises(self, db_session, product, customer):
        """Qismlar yig'indisi jami summadan kam bo'lsa — xatolik"""
        with pytest.raises(ValueError):
            crud.create_sale_record(
                db_session, product_id=product.id, quantity=100, unit_price=12000,
                total_amount=1_200_000, payment_method="mixed",
                payments=[{"method": "cash", "amount": 700_000},
                          {"method": "card", "amount": 400_000}],
                customer=customer, customer_name=customer.name,
            )
        assert _payment_rows(db_session) == []
        assert db_session.query(models.Sale).count() == 0

    def test_sum_above_total_raises(self, db_session, product, customer):
        with pytest.raises(ValueError):
            crud.create_sale_record(
                db_session, product_id=product.id, quantity=100, unit_price=12000,
                total_amount=1_200_000, payment_method="mixed",
                payments=[{"method": "cash", "amount": 700_000},
                          {"method": "card", "amount": 600_000}],
                customer=customer, customer_name=customer.name,
            )

    def test_zero_amount_raises(self, db_session, product, customer):
        with pytest.raises(ValueError):
            crud.create_sale_record(
                db_session, product_id=product.id, quantity=100, unit_price=12000,
                total_amount=1_200_000, payment_method="mixed",
                payments=[{"method": "cash", "amount": 700_000},
                          {"method": "card", "amount": 0}],
                customer=customer, customer_name=customer.name,
            )

    def test_negative_amount_raises(self, db_session, product, customer):
        with pytest.raises(ValueError):
            crud.create_sale_record(
                db_session, product_id=product.id, quantity=100, unit_price=12000,
                total_amount=1_200_000, payment_method="mixed",
                payments=[{"method": "cash", "amount": -100},
                          {"method": "card", "amount": 1_300_000}],
                customer=customer, customer_name=customer.name,
            )

    def test_unknown_method_raises(self, db_session, product, customer):
        with pytest.raises(ValueError):
            crud.create_sale_record(
                db_session, product_id=product.id, quantity=100, unit_price=12000,
                total_amount=1_200_000, payment_method="mixed",
                payments=[{"method": "bitcoin", "amount": 1_200_000}],
                customer=customer, customer_name=customer.name,
            )


class TestShiftMath:
    def test_shift_expected_cash_counts_only_cash_portion(self, db_session, cashier,
                                                          product, customer):
        """Smena kutilgan naqdiga aralash to'lovning faqat naqd qismi tushadi"""
        shift = crud.create_cash_shift(db_session, employee_id=cashier.id,
                                       opening_balance=500_000)
        crud.create_sale_record(
            db_session, product_id=product.id, quantity=100, unit_price=12000,
            total_amount=1_200_000, payment_method="mixed",
            payments=[{"method": "cash", "amount": 700_000},
                      {"method": "card", "amount": 500_000}],
            customer=customer, customer_name=customer.name,
            user_id=cashier.id, user_name=cashier.full_name,
        )
        summary = crud.cash_shift_summary(db_session, shift)
        assert summary["expected_cash"] == 500_000 + 700_000  # karta kirmaydi
        assert summary["payment_count"] == 1