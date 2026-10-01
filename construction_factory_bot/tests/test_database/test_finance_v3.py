"""
Moliya (v3): P&L, soliq, qarz hisobotlari
"""
from datetime import datetime, date, timedelta
import pytest

from database import models, crud


@pytest.fixture
def pl_data(db_session):
    """Sotuv + mahsulot + xarajatlar"""
    p = models.Product(name="Fin Sement", category="sement", unit="qop",
                       selling_price=12000, production_cost=7000, is_active=True)
    db_session.add(p)
    db_session.flush()

    db_session.add(models.Sale(
        invoice_number="INV-FIN-1", product_id=p.id, quantity=100,
        unit_price=12000, total_amount=1_200_000, discount_amount=0,
        paid_amount=1_200_000, customer_name="A", payment_method="cash",
        sale_date=datetime.utcnow(),
    ))
    db_session.add(models.ProductionOrder(
        order_number="PO-FIN-1", product_id=p.id, quantity=100,
        total_cost=500_000, status=models.OrderStatus.COMPLETED,
        created_at=datetime.utcnow(),
    ))
    db_session.add(models.SalaryPayment(
        employee_id=1, month=datetime.utcnow().month, year=datetime.utcnow().year,
        base_salary=300_000, total_amount=300_000, status="paid",
        payment_date=datetime.utcnow(),
    ))
    db_session.commit()
    return p


class TestPLReport:
    def test_pl_with_data(self, db_session, pl_data):
        today = datetime.utcnow().date()
        report = crud.get_pl_report(db_session, today.replace(day=1), today)
        assert report["revenue"] == 1_200_000
        assert report["cogs"] == 700_000  # 100 qop * 7000
        assert report["production_cost"] == 500_000
        assert report["salary_cost"] == 300_000
        assert report["net_profit"] == 1_200_000 - 700_000 - 500_000 - 300_000

    def test_pl_empty(self, db_session):
        report = crud.get_pl_report(db_session, date(2020, 1, 1), date(2020, 1, 31))
        assert report["revenue"] == 0
        assert report["profit_margin"] == 0


class TestTax:
    def test_qqs_12(self):
        tax = crud.calculate_tax(1_000_000, 12.0)
        assert tax["qqs"] == 120_000
        assert tax["net"] == 880_000

    def test_turnover_4(self):
        tax = crud.calculate_tax(10_000_000, 4.0)
        assert tax["qqs"] == 400_000
        assert tax["net"] == 9_600_000


class TestDebtsReport:
    def test_debts_report(self, db_session, pl_data):
        customer = models.Customer(name="Debtor Mijoz", credit_limit=5_000_000)
        db_session.add(customer)
        db_session.flush()
        db_session.add(models.Sale(
            invoice_number="INV-DEBT-1", product_id=pl_data.id, quantity=10,
            unit_price=12000, total_amount=120_000, discount_amount=0,
            paid_amount=0, customer_id=customer.id, customer_name=customer.name,
            is_credit=True, credit_days=30, credit_status="tolanmagan",
            due_date=datetime.utcnow() - timedelta(days=10),  # muddati o'tgan
            sale_date=datetime.utcnow() - timedelta(days=40),
        ))
        customer.total_debt = 120_000
        db_session.commit()

        report = crud.get_customer_debts_report(db_session)
        assert report["total_debt"] == 120_000
        assert report["debtor_count"] == 1
        assert report["overdue_count"] == 1

    def test_credit_sales_filter(self, db_session, pl_data):
        customer = models.Customer(name="C2", credit_limit=1_000_000)
        db_session.add(customer)
        db_session.flush()
        db_session.add(models.Sale(
            invoice_number="INV-OD-1", product_id=pl_data.id, quantity=1,
            unit_price=10000, total_amount=10000, customer_id=customer.id,
            customer_name=customer.name, is_credit=True,
            paid_amount=0, credit_status="tolanmagan",
            due_date=datetime.utcnow() - timedelta(days=5),
            sale_date=datetime.utcnow() - timedelta(days=30),
        ))
        db_session.commit()
        overdue = crud.get_credit_sales(db_session, status="muddati_otgan")
        assert len(overdue) == 1
        assert overdue[0].invoice_number == "INV-OD-1"

    def test_no_credit_sales(self, db_session):
        assert crud.get_credit_sales(db_session) == []
