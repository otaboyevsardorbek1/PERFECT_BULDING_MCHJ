"""
KASSIR SMENASI (smena yopish + naqd farq) DB testlari

Qamrov:
- Smena boshlash (boshlang'ich naqd) va bir vaqtda bitta ochiq smena
- Kutilgan naqd: naqd sotuv + nasiya avans/qarz kirim, kartalar kirmaydi,
  qaytarish chiqim sifatida ayriladi
- Yopish: farq = haqiqiy - kutilgan (kamomad / ortiqcha)
- Qayta yopish / ikkinchi ochiq smena cheklovlari
"""
from datetime import datetime

import pytest

from database import models, crud


@pytest.fixture
def cashier(db_session):
    emp = models.Employee(
        telegram_id=7001, full_name="Kassir Nodira", phone_number="+998901234700",
        position="Kassir", department="sales",
        status=models.EmployeeStatus.ACTIVE, hire_date=datetime.utcnow(),
        role="kassir",
    )
    db_session.add(emp)
    db_session.commit()
    db_session.refresh(emp)
    return emp


@pytest.fixture
def product(db_session):
    p = models.Product(name="Shift Sement", category="sement", unit="qop",
                       selling_price=12000, production_cost=7000, is_active=True)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def customer(db_session):
    return crud.create_customer(db_session, {
        "name": "Shift Mijoz", "phone": "+998907771188", "credit_limit": 10_000_000,
    })


def _open(db_session, cashier, opening=500_000):
    return crud.create_cash_shift(db_session, employee_id=cashier.id,
                                  opening_balance=opening)


def _cash_sale(db_session, product, customer, amount, method="cash", credit_advance=None):
    """Naqd/karta yoki nasiya (avansli) sotuv"""
    if method == "credit":
        return crud.create_sale_record(
            db_session, product_id=product.id, quantity=int(amount / 12000),
            unit_price=12000, total_amount=amount, payment_method="credit",
            advance_amount=credit_advance, customer=customer,
            customer_name=customer.name, user_id=7, user_name="Kassir",
        )
    return crud.create_sale_record(
        db_session, product_id=product.id, quantity=int(amount / 12000),
        unit_price=12000, total_amount=amount, payment_method=method,
        customer=customer, customer_name=customer.name,
        user_id=7, user_name="Kassir",
    )


class TestOpenShift:
    def test_open_with_balance(self, db_session, cashier):
        shift = _open(db_session, cashier, opening=500_000)
        assert shift.shift_number.startswith("SHT-")
        assert shift.status == "ochiq"
        assert shift.opening_balance == 500_000
        assert shift.cashier_name == cashier.full_name
        assert shift.actual_cash is None

    def test_cannot_open_second_while_open(self, db_session, cashier):
        _open(db_session, cashier)
        with pytest.raises(ValueError):
            _open(db_session, cashier, opening=100_000)

    def test_can_open_after_close(self, db_session, cashier):
        shift = _open(db_session, cashier)
        crud.close_cash_shift(db_session, shift.id, actual_cash=shift.opening_balance)
        shift2 = _open(db_session, cashier, opening=200_000)
        assert shift2.id != shift.id
        assert shift2.opening_balance == 200_000

    def test_negative_opening_rejected(self, db_session, cashier):
        with pytest.raises(ValueError):
            crud.create_cash_shift(db_session, employee_id=cashier.id, opening_balance=-5)


class TestExpectedCash:
    def test_summary_counts_only_cash(self, db_session, cashier, product, customer):
        shift = _open(db_session, cashier, opening=500_000)
        _cash_sale(db_session, product, customer, 1_200_000, method="cash")   # kirim
        _cash_sale(db_session, product, customer, 600_000, method="card")     # kirmaydi
        _cash_sale(db_session, product, customer, 900_000, method="credit",
                   credit_advance=400_000)  # avans naqd kirim

        summary = crud.cash_shift_summary(db_session, shift)
        # 500k + 1.2M + 400k avans (karta 600k kirmaydi)
        assert summary["expected_cash"] == 500_000 + 1_200_000 + 400_000
        assert summary["payment_count"] == 2

    def test_refund_reduces_expected(self, db_session, cashier, product, customer):
        shift = _open(db_session, cashier, opening=500_000)
        sale = _cash_sale(db_session, product, customer, 1_200_000, method="cash")
        crud.create_return_act(db_session, sale_id=sale.id, quantity=sale.quantity,
                               refund_type="cash", user_name="Kassir")  # -1.2M chiqim

        summary = crud.cash_shift_summary(db_session, shift)
        assert summary["expected_cash"] == 500_000  # +1.2M sotuv, -1.2M qaytarish
        types = {g["label"]: g["total"] for g in summary["groups"]}
        assert types["↩️ Qaytarish (chiqim)"] == -1_200_000

    def test_payments_before_shift_not_counted(self, db_session, cashier, product, customer):
        # Smena ochilishidan oldingi naqd sotuv kirmaydi
        _cash_sale(db_session, product, customer, 1_200_000, method="cash")
        shift = _open(db_session, cashier, opening=0)
        summary = crud.cash_shift_summary(db_session, shift)
        assert summary["expected_cash"] == 0


class TestCloseShift:
    def test_close_with_shortage(self, db_session, cashier, product, customer):
        shift = _open(db_session, cashier, opening=500_000)
        _cash_sale(db_session, product, customer, 1_200_000, method="cash")

        closed = crud.close_cash_shift(db_session, shift.id, actual_cash=1_500_000)
        # kutilgan 1.7M, sanalgan 1.5M -> kamomad 200k
        assert closed.status == "yopilgan"
        assert closed.expected_cash == 1_700_000
        assert closed.actual_cash == 1_500_000
        assert closed.difference == -200_000
        assert closed.closed_at is not None

    def test_close_with_surplus(self, db_session, cashier, product, customer):
        shift = _open(db_session, cashier, opening=500_000)
        _cash_sale(db_session, product, customer, 1_200_000, method="cash")
        closed = crud.close_cash_shift(db_session, shift.id, actual_cash=1_800_000)
        assert closed.difference == 100_000

    def test_close_exact(self, db_session, cashier, product, customer):
        shift = _open(db_session, cashier, opening=500_000)
        _cash_sale(db_session, product, customer, 1_200_000, method="cash")
        closed = crud.close_cash_shift(db_session, shift.id, actual_cash=1_700_000)
        assert closed.difference == 0

    def test_double_close_rejected(self, db_session, cashier):
        shift = _open(db_session, cashier)
        crud.close_cash_shift(db_session, shift.id, actual_cash=shift.opening_balance)
        with pytest.raises(ValueError):
            crud.close_cash_shift(db_session, shift.id, actual_cash=shift.opening_balance)

    def test_negative_actual_rejected(self, db_session, cashier):
        shift = _open(db_session, cashier)
        with pytest.raises(ValueError):
            crud.close_cash_shift(db_session, shift.id, actual_cash=-1)

    def test_close_unknown_shift(self, db_session):
        with pytest.raises(ValueError):
            crud.close_cash_shift(db_session, 999999, actual_cash=0)

    def test_history_and_serialization(self, db_session, cashier):
        shift = _open(db_session, cashier, opening=100_000)
        crud.close_cash_shift(db_session, shift.id, actual_cash=100_000)
        shifts = crud.list_cash_shifts(db_session)
        assert len(shifts) == 1
        d = crud.cash_shift_to_dict(shifts[0])
        assert d["shift_number"].startswith("SHT-")
        assert d["status"] == "yopilgan"
        assert d["difference"] == 0
        assert d["status_label"] == "🔴 Yopilgan"
