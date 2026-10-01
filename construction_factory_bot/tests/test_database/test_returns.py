"""
QAYTARISH AKTI (RETURN) moduli testlari — TZ F bo'limi

Qamrov:
- Ruxsat tekshiruvi (7 kun, qoldiq, to'liq qaytarilgan sotuv)
- Naqd/karta pul qaytarish (Payment yozuvi, ballar qaytarilishi, xaridlar)
- Bonus ball bilan qaytarish
- Nasiya sotuvini qaytarish (qarz hisobdan chiqariladi)
- Almashtirish (teng / qimmat / arzon mahsulotga)
- Ombor: RETURN tranzaksiyasi va available qty tiklanishi
- Moliya: P&L da refunds va cogs tuzatishlari
"""
from datetime import datetime, timedelta

import pytest

from database import models, crud


@pytest.fixture
def product(db_session):
    p = models.Product(name="Ret Sement M500", category="sement", unit="qop",
                       selling_price=12000, production_cost=7000, is_active=True)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def product2(db_session):
    """Almashtirish uchun boshqa mahsulot"""
    p = models.Product(name="Ret Kafel", category="kafel", unit="dona",
                       selling_price=8000, production_cost=4000, is_active=True)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def customer(db_session):
    return crud.create_customer(db_session, {
        "name": "Ret Mijoz", "phone": "+998907771122", "credit_limit": 5_000_000,
    })


def _paid_sale(db_session, product, customer, qty=100, unit_price=12000,
               method="cash"):
    """To'liq naqd to'langan sotuv (stock + points + payment yoziladi)"""
    total = qty * unit_price
    # Zaxira: PRODUCTION tranzaksiyasi (qoldiq hisoblash uchun)
    db_session.add(models.WarehouseTransaction(
        product_id=product.id, quantity=500, transaction_type=models.TransactionType.PRODUCTION,
        user_id=1, user_name="Test",
    ))
    db_session.commit()
    return crud.create_sale_record(
        db_session, product_id=product.id, quantity=qty, unit_price=unit_price,
        total_amount=total, payment_method=method,
        customer=customer, customer_name=customer.name,
        user_id=7, user_name="Sotuvchi",
    )


def _payments(db_session):
    return db_session.query(models.Payment).order_by(models.Payment.id).all()


def _refund_payments(db_session):
    return db_session.query(models.Payment).filter(
        models.Payment.payment_type == "refund"
    ).all()


# =============== RUXSAT TEKSHIRUVI ===============
class TestEligibility:
    def test_recent_paid_sale_eligible(self, db_session, product, customer):
        sale = _paid_sale(db_session, product, customer, qty=10)
        check = crud.check_return_eligibility(db_session, sale.id, 5)
        assert check["allowed"] is True
        assert check["remaining"] == 10

    def test_quantity_over_remaining_rejected(self, db_session, product, customer):
        sale = _paid_sale(db_session, product, customer, qty=10)
        check = crud.check_return_eligibility(db_session, sale.id, 11)
        assert check["allowed"] is False
        assert "oshadi" in check["reason"]

    def test_old_sale_rejected_after_return_period(self, db_session, product, customer,
                                                   monkeypatch):
        monkeypatch.setattr("config.RETURN_PERIOD_DAYS", 7)
        sale = _paid_sale(db_session, product, customer, qty=10)
        sale.sale_date = datetime.utcnow() - timedelta(days=8)
        db_session.commit()
        check = crud.check_return_eligibility(db_session, sale.id, 1)
        assert check["allowed"] is False
        assert "muddat" in check["reason"]

    def test_fully_returned_sale_rejected(self, db_session, product, customer):
        sale = _paid_sale(db_session, product, customer, qty=10)
        crud.create_return_act(db_session, sale_id=sale.id, quantity=10,
                               refund_type="cash", user_name="Sotuvchi")
        with pytest.raises(ValueError):
            crud.create_return_act(db_session, sale_id=sale.id, quantity=1,
                                   refund_type="cash", user_name="Sotuvchi")


# =============== NAQD / KARTA PUL QAYTARISH ===============
class TestCashRefund:
    def test_full_cash_refund_reverses_everything(self, db_session, product, customer):
        sale = _paid_sale(db_session, product, customer, qty=100)  # 1.2M so'm
        db_session.refresh(customer)
        assert customer.loyalty_points == 12
        assert customer.total_purchases == 1_200_000

        act = crud.create_return_act(db_session, sale_id=sale.id, quantity=100,
                                     reason="brak", refund_type="cash",
                                     user_id=7, user_name="Sotuvchi")

        assert act.act_number.startswith("RTN-")
        assert act.refund_type == "cash"
        assert act.refund_amount == 1_200_000
        assert act.warehouse == "brak"  # sifat muammosi -> brak ombori
        assert act.status == "completed"

        # Sotuv "qaytarilgan" bo'ldi
        db_session.refresh(sale)
        assert sale.returned_qty == 100
        assert sale.returned_amount == 1_200_000
        assert sale.status == "qaytarilgan"

        # Mijoz hisobi qaytarildi
        db_session.refresh(customer)
        assert customer.total_purchases == 0
        assert customer.loyalty_points == 0  # olingan 12 ball qaytarildi

        # To'lovlar: +1.2M sotuv, -1.2M qaytarish
        payments = _payments(db_session)
        assert len(payments) == 2
        refunds = _refund_payments(db_session)
        assert len(refunds) == 1
        assert refunds[0].amount == -1_200_000
        assert refunds[0].method == "cash"
        assert refunds[0].sale_id == sale.id

        # Ombor: SALE 100 va RETURN 100
        wh = db_session.query(models.WarehouseTransaction).order_by(
            models.WarehouseTransaction.id
        ).all()
        types = [w.transaction_type for w in wh]
        assert models.TransactionType.SALE in types
        assert models.TransactionType.RETURN in types
        ret_txn = [w for w in wh if w.transaction_type == models.TransactionType.RETURN][0]
        assert ret_txn.quantity == 100
        assert ret_txn.document_number == act.act_number
        assert ret_txn.target_warehouse == "brak"

        # Available qty tiklangan (500 ishlab chiqarilgan - 100 sotilgan + 100 qaytgan)
        assert crud.get_available_product_qty(db_session, product.id) == 500

    def test_partial_cash_refund_keeps_remaining(self, db_session, product, customer):
        sale = _paid_sale(db_session, product, customer, qty=100)
        act = crud.create_return_act(db_session, sale_id=sale.id, quantity=40,
                                     refund_type="card", user_name="Sotuvchi")
        assert act.refund_amount == 480_000
        db_session.refresh(sale)
        assert sale.status == "completed"      # qisman qaytarish
        assert sale.returned_qty == 40

        db_session.refresh(customer)
        assert customer.total_purchases == 720_000
        assert customer.loyalty_points == 12 - 4  # 480k -> 4 ball qaytarildi
        assert _refund_payments(db_session)[0].method == "card"

        # Qolgan qismini qaytarish mumkin
        crud.create_return_act(db_session, sale_id=sale.id, quantity=60,
                               refund_type="cash", user_name="Sotuvchi")
        db_session.refresh(sale)
        assert sale.status == "qaytarilgan"

    def test_return_without_customer_record(self, db_session, product):
        sale = crud.create_sale_record(
            db_session, product_id=product.id, quantity=5, unit_price=12000,
            total_amount=60_000, payment_method="cash",
            customer_name="Noma'lum mijoz", user_id=7, user_name="Sotuvchi",
        )
        act = crud.create_return_act(db_session, sale_id=sale.id, quantity=5,
                                     refund_type="cash", user_name="Sotuvchi")
        assert act.refund_amount == 60_000
        assert act.customer_id is None


# =============== BONUS BALL ===============
class TestBonusRefund:
    def test_bonus_refund_credits_points(self, db_session, product, customer):
        sale = _paid_sale(db_session, product, customer, qty=100)
        db_session.refresh(customer)
        assert customer.loyalty_points == 12

        act = crud.create_return_act(db_session, sale_id=sale.id, quantity=100,
                                     refund_type="bonus", user_name="Sotuvchi")
        assert act.refund_amount == 0
        assert act.bonus_points == 12  # 1.2M so'm -> 12 ball bonus

        db_session.refresh(customer)
        assert customer.loyalty_points == 24  # 12 (sotuv) + 12 (bonus)
        assert customer.total_purchases == 0
        assert _refund_payments(db_session) == []  # pul chiqmadi


# =============== NASIYA (KREDIT) SOTUVNI QAYTARISH ===============
class TestCreditReturn:
    def test_pure_credit_return_clears_debt(self, db_session, product, customer):
        sale = crud.create_sale_record(
            db_session, product_id=product.id, quantity=100, unit_price=12000,
            total_amount=1_200_000, payment_method="credit", advance_amount=0,
            customer=customer, customer_name=customer.name,
            user_id=7, user_name="Sotuvchi",
        )
        db_session.refresh(customer)
        assert customer.total_debt == 1_200_000

        act = crud.create_return_act(db_session, sale_id=sale.id, quantity=100,
                                     refund_type="cash", user_name="Sotuvchi")
        assert act.debt_reduction == 1_200_000
        assert act.refund_amount == 0  # mijoz hech narsa to'lamagan

        db_session.refresh(customer)
        assert customer.total_debt == 0
        assert customer.loyalty_points == 0

        db_session.refresh(sale)
        assert sale.credit_status == "toliq_tolangan"  # qarzdorlik yo'q
        assert _refund_payments(db_session) == []

    def test_credit_with_advance_refunds_paid_part(self, db_session, product, customer):
        sale = crud.create_sale_record(
            db_session, product_id=product.id, quantity=100, unit_price=12000,
            total_amount=1_200_000, payment_method="credit", advance_amount=500_000,
            customer=customer, customer_name=customer.name,
            user_id=7, user_name="Sotuvchi",
        )
        db_session.refresh(customer)
        assert customer.total_debt == 700_000

        act = crud.create_return_act(db_session, sale_id=sale.id, quantity=100,
                                     refund_type="cash", user_name="Sotuvchi")
        assert act.debt_reduction == 700_000
        assert act.refund_amount == 500_000  # avans qaytariladi

        db_session.refresh(customer)
        assert customer.total_debt == 0
        assert customer.total_purchases == 0
        assert customer.loyalty_points == 0  # 5 ball (avans) qaytarildi
        assert _refund_payments(db_session)[0].amount == -500_000


# =============== ALMASHTIRISH (EXCHANGE) ===============
class TestExchange:
    def test_exchange_to_equal_value(self, db_session, product, product2, customer):
        sale = _paid_sale(db_session, product, customer, qty=100)  # X = 1.2M
        act = crud.create_return_act(
            db_session, sale_id=sale.id, quantity=100,
            refund_type="exchange", exchange_product_id=product2.id,
            exchange_quantity=150, user_name="Sotuvchi",  # 150 * 8000 = 1.2M
        )
        assert act.exchange_product_name == product2.name
        assert act.exchange_quantity == 150
        assert act.exchange_amount == 1_200_000
        assert act.tradein_amount == 1_200_000
        assert act.extra_amount == 0
        assert act.refund_amount == 0

        # Yangi sotuv (chegirma sifatida trade-in) yaratilgan.
        # Sale.total_amount = chegirmadan keyingi (net) qiymat.
        new_sales = db_session.query(models.Sale).filter(
            models.Sale.product_id == product2.id
        ).all()
        assert len(new_sales) == 1
        assert new_sales[0].total_amount == 0
        assert new_sales[0].discount_amount == 1_200_000
        assert new_sales[0].paid_amount == 0
        assert _refund_payments(db_session) == []

        db_session.refresh(sale)
        assert sale.status == "qaytarilgan"

    def test_exchange_to_more_expensive_charges_extra(self, db_session, product, customer):
        expensive = models.Product(name="Ret Premium", category="kafel", unit="dona",
                                   selling_price=24000, production_cost=10000,
                                   is_active=True)
        db_session.add(expensive)
        db_session.commit()
        db_session.refresh(expensive)

        sale = _paid_sale(db_session, product, customer, qty=100)  # X = 1.2M
        act = crud.create_return_act(
            db_session, sale_id=sale.id, quantity=100,
            refund_type="exchange", exchange_product_id=expensive.id,
            exchange_quantity=100, refund_method="cash", user_name="Sotuvchi",
        )  # Y = 2.4M -> farq 1.2M
        assert act.extra_amount == 1_200_000
        assert act.tradein_amount == 1_200_000
        assert act.refund_amount == 0

        new_sale = db_session.query(models.Sale).filter(
            models.Sale.product_id == expensive.id
        ).first()
        assert new_sale.total_amount == 1_200_000  # net: 2.4M - 1.2M trade-in
        assert new_sale.discount_amount == 1_200_000
        assert new_sale.paid_amount == 1_200_000  # farq naqd to'landi
        payments = _payments(db_session)
        assert any(p.amount == 1_200_000 and p.payment_type == "sale"
                   for p in payments)

        db_session.refresh(customer)
        assert customer.loyalty_points == 24  # 12 (eski) + 12 (qo'shimcha to'lov)

    def test_exchange_to_cheaper_refunds_difference(self, db_session, product, product2, customer):
        cheap = models.Product(name="Ret Arzon", category="kafel", unit="dona",
                               selling_price=6000, production_cost=3000, is_active=True)
        db_session.add(cheap)
        db_session.commit()
        db_session.refresh(cheap)

        sale = _paid_sale(db_session, product, customer, qty=100)  # X = 1.2M
        act = crud.create_return_act(
            db_session, sale_id=sale.id, quantity=100,
            refund_type="exchange", exchange_product_id=cheap.id,
            exchange_quantity=100, refund_method="card", user_name="Sotuvchi",
        )  # Y = 600k -> 600k qaytariladi
        assert act.tradein_amount == 600_000
        assert act.extra_amount == 0
        assert act.refund_amount == 600_000
        assert _refund_payments(db_session)[0].amount == -600_000
        assert _refund_payments(db_session)[0].method == "card"

        db_session.refresh(customer)
        assert customer.loyalty_points == 12 - 6  # 600k ga 6 ball qaytarildi

    def test_exchange_rejected_on_unpaid_credit(self, db_session, product, product2, customer):
        crud.create_sale_record(
            db_session, product_id=product.id, quantity=100, unit_price=12000,
            total_amount=1_200_000, payment_method="credit", advance_amount=0,
            customer=customer, customer_name=customer.name,
            user_id=7, user_name="Sotuvchi",
        )
        sale = db_session.query(models.Sale).filter(
            models.Sale.product_id == product.id
        ).first()
        with pytest.raises(ValueError):
            crud.create_return_act(
                db_session, sale_id=sale.id, quantity=100,
                refund_type="exchange", exchange_product_id=product2.id,
                exchange_quantity=1, user_name="Sotuvchi",
            )

    def test_exchange_requires_valid_replacement(self, db_session, product, customer):
        sale = _paid_sale(db_session, product, customer, qty=10)
        with pytest.raises(ValueError):
            crud.create_return_act(
                db_session, sale_id=sale.id, quantity=10,
                refund_type="exchange", user_name="Sotuvchi",
            )
        with pytest.raises(ValueError):
            crud.create_return_act(
                db_session, sale_id=sale.id, quantity=10,
                refund_type="exchange", exchange_product_id=999999,
                exchange_quantity=1, user_name="Sotuvchi",
            )


# =============== RO'YXAT / SERIALIZATSIYA ===============
class TestListing:
    def test_list_and_serialization(self, db_session, product, customer):
        sale = _paid_sale(db_session, product, customer, qty=10)
        crud.create_return_act(db_session, sale_id=sale.id, quantity=4,
                               reason="notogri", refund_type="cash",
                               user_name="Sotuvchi")
        crud.create_return_act(db_session, sale_id=sale.id, quantity=6,
                               refund_type="bonus", user_name="Sotuvchi")

        acts = crud.list_return_acts(db_session)
        assert len(acts) == 2
        assert crud.list_return_acts(db_session, sale_id=sale.id) == acts
        assert crud.list_return_acts(db_session, sale_id=999999) == []

        by_type = {crud.return_act_to_dict(a)["refund_type"]: crud.return_act_to_dict(a) for a in acts}
        d_cash = by_type["cash"]
        assert d_cash["act_number"].startswith("RTN-")
        assert d_cash["reason_label"] == "Noto'g'ri mahsulot"
        assert d_cash["quantity"] == 4
        assert "created_at" in d_cash
        assert by_type["bonus"]["refund_type"] == "bonus"
        assert by_type["bonus"]["quantity"] == 6
        assert crud.get_return_act(db_session, acts[0].id).id == acts[0].id
        assert crud.get_return_act(db_session, 999999) is None


# =============== MOLIYA: P&L ===============
class TestFinanceImpact:
    def test_pl_reflects_full_cash_refund(self, db_session, product, customer):
        sale = _paid_sale(db_session, product, customer, qty=100)
        crud.create_return_act(db_session, sale_id=sale.id, quantity=100,
                               refund_type="cash", user_name="Sotuvchi")

        today = datetime.utcnow().date()
        report = crud.get_pl_report(db_session, today - timedelta(days=1), today + timedelta(days=1))
        assert report["refunds"] == 1_200_000
        # Daromad 1.2M, refund 1.2M, cogs ham 0 ga tushadi (tovar qaytdi)
        assert report["revenue"] == 1_200_000
        assert report["cogs"] == 0
        assert report["net_profit"] == 0

    def test_pl_unchanged_without_returns(self, db_session, product, customer):
        _paid_sale(db_session, product, customer, qty=100)
        today = datetime.utcnow().date()
        report = crud.get_pl_report(db_session, today - timedelta(days=1), today + timedelta(days=1))
        assert report["refunds"] == 0
        assert report["cogs"] == 700_000
        assert report["revenue"] == 1_200_000
