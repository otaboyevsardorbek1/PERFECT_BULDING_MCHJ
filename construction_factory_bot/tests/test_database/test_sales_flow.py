"""
INTEGRATSIYA: Nasiya sotuv -> qarz to'lovi -> sodiqlik ballari zanjiri.

Botning confirm_sale handleri endi crud.create_sale_record() ga tayanadi,
shuning uchun bu testlar haqiqiy ishlab chiqarish kod yo'lini sinaydi:
kredit limiti -> sotuv yozuvi (avans/qarz) -> FIFO qarz to'lovi -> ballar.

Qoida (v3): sodiqlik ballari faqat haqiqatda olingan pulga beriladi
(100 000 so'm = 1 ball) — naqd/karta sotuvda ham, nasiya avansida ham,
qarz to'lovida ham.
"""
from datetime import datetime, timedelta

import pytest

from database import models, crud


@pytest.fixture
def product(db_session):
    p = models.Product(name="Flow Sement M500", category="sement", unit="qop",
                       selling_price=12000, production_cost=7000, is_active=True)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def customer(db_session):
    return crud.create_customer(db_session, {
        "name": "Nasiya Mijoz", "phone": "+998901112233", "credit_limit": 10_000_000,
    })


def _payment_rows(db_session):
    return db_session.query(models.Payment).order_by(models.Payment.id).all()


def _wh_rows(db_session):
    return db_session.query(models.WarehouseTransaction).all()


# =============== 1) SOTUV YOZUVLARI (create_sale_record) ===============
class TestCreateSaleRecord:
    def test_pure_nasiya_full_credit(self, db_session, product, customer):
        """To'liq nasiya: avans yo'q, butun summa qarzga, ball berilmaydi"""
        sale = crud.create_sale_record(
            db_session, product_id=product.id, quantity=100, unit_price=12000,
            total_amount=1_200_000, payment_method="credit", advance_amount=0,
            customer=customer, customer_name=customer.name,
            user_id=7, user_name="Sotuvchi",
        )
        assert sale.is_credit is True
        assert sale.paid_amount == 0
        assert sale.total_amount == 1_200_000
        assert sale.credit_status == "tolanmagan"
        assert sale.status == "completed"
        assert sale.due_date is not None
        now = datetime.utcnow()
        assert now + timedelta(days=29) < sale.due_date < now + timedelta(days=31)

        db_session.refresh(customer)
        assert customer.total_debt == 1_200_000
        assert customer.total_purchases == 1_200_000
        assert customer.loyalty_points == 0  # hali pul tushmagan

        assert _payment_rows(db_session) == []   # avans yo'q -> to'lov yozuvi yo'q
        assert len(_wh_rows(db_session)) == 1    # ombor harakati yoziladi
        assert _wh_rows(db_session)[0].transaction_type == models.TransactionType.SALE

    def test_nasiya_with_advance_earns_points(self, db_session, product, customer):
        """Nasiya + avans: avansga ball beriladi, qolgan qism qarzga yoziladi"""
        sale = crud.create_sale_record(
            db_session, product_id=product.id, quantity=1, unit_price=2_000_000,
            total_amount=2_000_000, payment_method="credit", advance_amount=500_000,
            customer=customer, customer_name=customer.name,
            user_id=7, user_name="Sotuvchi",
        )
        assert sale.paid_amount == 500_000
        assert sale.credit_status == "tolanmagan"

        db_session.refresh(customer)
        assert customer.total_debt == 1_500_000
        assert customer.loyalty_points == 5  # 500 000 / 100 000

        payments = _payment_rows(db_session)
        assert len(payments) == 1
        assert payments[0].amount == 500_000
        assert payments[0].method == "cash"   # nasiya avansi naqd sifatida
        assert payments[0].payment_type == "debt"

    def test_cash_sale_pays_full_and_earns_points(self, db_session, product, customer):
        """Naqd sotuv: to'liq to'lanadi, ball to'liq summaga, qarz yo'q"""
        sale = crud.create_sale_record(
            db_session, product_id=product.id, quantity=1, unit_price=1_200_000,
            total_amount=1_200_000, payment_method="cash",
            customer=customer, customer_name=customer.name,
            user_id=7, user_name="Sotuvchi",
        )
        assert sale.is_credit is False
        assert sale.paid_amount == 1_200_000
        assert sale.credit_status == "toliq_tolangan"
        assert sale.due_date is None

        db_session.refresh(customer)
        assert customer.total_debt == 0
        assert customer.loyalty_points == 12  # 1 200 000 / 100 000

        payments = _payment_rows(db_session)
        assert len(payments) == 1
        assert payments[0].method == "cash"
        assert payments[0].payment_type == "sale"

    def test_discount_applied_and_points_on_net(self, db_session, product, customer):
        """Chegirma: to'lov va ballar chegirmadan keyingi summaga"""
        sale = crud.create_sale_record(
            db_session, product_id=product.id, quantity=1, unit_price=1_000_000,
            total_amount=1_000_000, discount_amount=50_000, payment_method="cash",
            customer=customer, customer_name=customer.name,
            user_id=7, user_name="Sotuvchi",
        )
        assert sale.total_amount == 950_000
        assert sale.discount_amount == 50_000
        assert sale.paid_amount == 950_000

        db_session.refresh(customer)
        assert customer.total_purchases == 950_000
        assert customer.loyalty_points == 9  # 950 000 // 100 000

    def test_wholesale_customer_sale_type(self, db_session, product, customer):
        customer.is_wholesale = True
        db_session.commit()
        sale = crud.create_sale_record(
            db_session, product_id=product.id, quantity=1, unit_price=10_000,
            total_amount=10_000, payment_method="cash",
            customer=customer, customer_name=customer.name,
            user_id=7, user_name="Sotuvchi",
        )
        assert sale.sale_type == "wholesale"

    def test_walkin_cash_sale_without_customer(self, db_session, product):
        """Ro'yxatdan o'tmagan mijozga naqd sotuv: mijoz hisobi yangilanmaydi"""
        sale = crud.create_sale_record(
            db_session, product_id=product.id, quantity=1, unit_price=500_000,
            total_amount=500_000, payment_method="cash",
            customer_name="Yo'lovchi mijoz", user_id=7, user_name="Sotuvchi",
        )
        assert sale.customer_id is None
        assert sale.credit_status == "toliq_tolangan"
        # mijoz yo'q -> ball yo'q, lekin to'lov yozuvi bor (naqd qabul qilindi)
        payments = _payment_rows(db_session)
        assert len(payments) == 1
        assert payments[0].amount == 500_000

    def test_advance_over_total_is_clamped(self, db_session, product, customer):
        """Avans summadan oshsa final_total gacha qisqartiriladi"""
        sale = crud.create_sale_record(
            db_session, product_id=product.id, quantity=1, unit_price=800_000,
            total_amount=800_000, payment_method="credit", advance_amount=5_000_000,
            customer=customer, customer_name=customer.name,
            user_id=7, user_name="Sotuvchi",
        )
        assert sale.paid_amount == 800_000
        assert sale.credit_status == "toliq_tolangan"
        db_session.refresh(customer)
        assert customer.total_debt == 0


# =============== 2) KREDIT LIMITI DARVOZASI ===============
class TestCreditLimitGateFlow:
    def test_second_nasiya_over_limit_not_created(self, db_session, product):
        """Limit tugagach navbatdagi nasiya rad etiladi va sotuv yozilmaydi"""
        limited = crud.create_customer(db_session, {
            "name": "Kichik Limit", "phone": "+998903334455", "credit_limit": 2_000_000,
        })
        sale1 = crud.create_sale_record(
            db_session, product_id=product.id, quantity=1, unit_price=1_500_000,
            total_amount=1_500_000, payment_method="credit", advance_amount=0,
            customer=limited, customer_name=limited.name,
            user_id=7, user_name="Sotuvchi",
        )
        # Hali yetarli joy bor
        check_ok = crud.check_credit_limit(db_session, limited, 400_000)
        assert check_ok["allowed"] is True

        # Endi bo'sh limit 500 000 — yana 1 000 000 so'mga nasiya so'raladi
        check_block = crud.check_credit_limit(db_session, limited, 1_000_000)
        assert check_block["allowed"] is False
        assert "500,000" in check_block["reason"]  # bo'sh limit xabarda ko'rsatiladi

        # Darvoza o'tmagan -> bot sotuvni yozmaydi (handler logikasi)
        assert db_session.query(models.Sale).count() == 1
        db_session.refresh(limited)
        assert limited.total_debt == 1_500_000

    def test_blocked_customer_nasiya_rejected(self, db_session, product, customer):
        customer.status = models.CustomerStatus.BLOCKED.value
        db_session.commit()
        check = crud.check_credit_limit(db_session, customer, 100_000)
        assert check["allowed"] is False
        assert "bloklangan" in check["reason"]

    def test_no_credit_limit_customer_rejected(self, db_session, product):
        no_limit = crud.create_customer(db_session, {"name": "Limitsiz", "credit_limit": 0})
        check = crud.check_credit_limit(db_session, no_limit, 100_000)
        assert check["allowed"] is False


# =============== 3) NASIYA HAYOT AYLANISHI: sotuv -> to'lov -> ball ===============
class TestNasiyaLifecycle:
    def test_full_nasiya_then_full_repayment(self, db_session, product, customer):
        """To'liq nasiya 2M -> butun qarz to'lanadi -> 20 ball"""
        sale = crud.create_sale_record(
            db_session, product_id=product.id, quantity=1, unit_price=2_000_000,
            total_amount=2_000_000, payment_method="credit", advance_amount=0,
            customer=customer, customer_name=customer.name,
            user_id=7, user_name="Sotuvchi",
        )
        db_session.refresh(customer)
        assert customer.total_debt == 2_000_000
        assert customer.loyalty_points == 0

        result = crud.pay_customer_debt(
            db_session, customer.id, 2_000_000, method="cash",
            created_by="Kassir",
        )
        assert result["paid"] == 2_000_000
        assert result["new_debt"] == 0
        assert result["points_earned"] == 20

        db_session.refresh(sale)
        db_session.refresh(customer)
        assert sale.credit_status == "toliq_tolangan"
        assert sale.paid_amount == 2_000_000
        assert customer.total_debt == 0
        assert customer.loyalty_points == 20  # 2 000 000 / 100 000

    def test_advance_then_remaining_repayment_full_points(self, db_session, product, customer):
        """Nasiya 3M (avans 300k) -> qolgan 2.7M to'lanadi -> jami 30 ball"""
        sale = crud.create_sale_record(
            db_session, product_id=product.id, quantity=1, unit_price=3_000_000,
            total_amount=3_000_000, payment_method="credit", advance_amount=300_000,
            customer=customer, customer_name=customer.name,
            user_id=7, user_name="Sotuvchi",
        )
        db_session.refresh(customer)
        assert customer.total_debt == 2_700_000
        assert customer.loyalty_points == 3  # avansga

        result = crud.pay_customer_debt(db_session, customer.id, 2_700_000, method="card")
        assert result["paid"] == 2_700_000
        assert result["points_earned"] == 27

        db_session.refresh(sale)
        db_session.refresh(customer)
        assert sale.credit_status == "toliq_tolangan"
        assert sale.paid_amount == 3_000_000
        assert customer.total_debt == 0
        assert customer.loyalty_points == 30  # butun 3M bo'ylab
        assert len(_payment_rows(db_session)) == 2  # avans + qolgan qism

    def test_partial_repayment_updates_status_and_points(self, db_session, product, customer):
        """Qisman to'lov: qisman holat, qolgan qarz va qisman ball"""
        sale = crud.create_sale_record(
            db_session, product_id=product.id, quantity=1, unit_price=1_000_000,
            total_amount=1_000_000, payment_method="credit", advance_amount=0,
            customer=customer, customer_name=customer.name,
            user_id=7, user_name="Sotuvchi",
        )
        result = crud.pay_customer_debt(db_session, customer.id, 400_000, method="cash")
        assert result["paid"] == 400_000
        assert result["new_debt"] == 600_000
        assert result["points_earned"] == 4

        db_session.refresh(sale)
        db_session.refresh(customer)
        assert sale.credit_status == "qisman"
        assert sale.paid_amount == 400_000
        assert customer.loyalty_points == 4

        # Qolganini to'lasa — sale yopiladi, jami ball 10 ga yetadi
        crud.pay_customer_debt(db_session, customer.id, 600_000, method="cash")
        db_session.refresh(sale)
        db_session.refresh(customer)
        assert sale.credit_status == "toliq_tolangan"
        assert customer.total_debt == 0
        assert customer.loyalty_points == 10

    def test_fifo_repayment_oldest_first_with_loyalty(self, db_session, product, customer):
        """Ikki nasiya: to'lov eng eskisidan boshlanadi, ball to'langan pulga"""
        sale_old = crud.create_sale_record(
            db_session, product_id=product.id, quantity=1, unit_price=1_000_000,
            total_amount=1_000_000, payment_method="credit", advance_amount=0,
            customer=customer, customer_name=customer.name,
            invoice_number="INV-FIFO-OLD",
            user_id=7, user_name="Sotuvchi",
        )
        sale_old.sale_date = datetime.utcnow() - timedelta(days=40)
        sale_old.due_date = sale_old.sale_date + timedelta(days=30)
        db_session.commit()

        sale_new = crud.create_sale_record(
            db_session, product_id=product.id, quantity=1, unit_price=500_000,
            total_amount=500_000, payment_method="credit", advance_amount=0,
            customer=customer, customer_name=customer.name,
            invoice_number="INV-FIFO-NEW",
            user_id=7, user_name="Sotuvchi",
        )
        db_session.refresh(customer)
        assert customer.total_debt == 1_500_000

        result = crud.pay_customer_debt(db_session, customer.id, 1_200_000, method="cash")
        assert result["paid"] == 1_200_000
        assert result["new_debt"] == 300_000
        assert result["points_earned"] == 12

        db_session.refresh(sale_old)
        db_session.refresh(sale_new)
        assert sale_old.credit_status == "toliq_tolangan"     # eski birinchi yopildi
        assert sale_new.credit_status == "qisman"             # yangida 200 000 to'landi
        assert sale_new.paid_amount == 200_000
        db_session.refresh(customer)
        assert customer.loyalty_points == 12

    def test_overpayment_clamped_no_extra_points(self, db_session, product, customer):
        """Ortiqcha to'lov qaytariladi (yopiladi): faqat haqiqiy qarzga ball"""
        sale = crud.create_sale_record(
            db_session, product_id=product.id, quantity=1, unit_price=800_000,
            total_amount=800_000, payment_method="credit", advance_amount=0,
            customer=customer, customer_name=customer.name,
            user_id=7, user_name="Sotuvchi",
        )
        result = crud.pay_customer_debt(db_session, customer.id, 5_000_000, method="cash")
        assert result["paid"] == 800_000
        assert result["new_debt"] == 0
        assert result["points_earned"] == 8  # 50 emas!

        db_session.refresh(sale)
        assert sale.credit_status == "toliq_tolangan"
        assert sale.paid_amount == 800_000


# =============== 4) BALLAR HISOBLASH ===============
class TestLoyaltyRounding:
    def test_rounding_thresholds(self):
        assert crud.calc_loyalty_points(99_999) == 0
        assert crud.calc_loyalty_points(100_000) == 1
        assert crud.calc_loyalty_points(150_000) == 1
        assert crud.calc_loyalty_points(1_000_000) == 10

    def test_zero_and_none_safe(self):
        assert crud.calc_loyalty_points(0) == 0
        assert crud.calc_loyalty_points(None) == 0
