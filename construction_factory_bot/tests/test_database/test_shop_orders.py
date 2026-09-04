"""
OMMAVIY WEB-DO'KON (catalog -> savat -> checkout) DB testlari

Qamrov:
- Naqd buyurtma darhol Sale'ga aylanadi (ombor + to'lov + CRM mijoz)
- Onlayn buyurtma 'kutilmoqda' bo'lib, to'lov tasdiqlangach yakunlanadi
- Aralash (Click/Payme + Naqd) buyurtma: qismlari bo'linadi, onlayn qismi
  to'langach har bir Sale aralash Payment qatorlari bilan yoziladi
- Zaxira/mahsulot/telefon validatsiyalari
- Buyurtmani bekor qilish
- PaymentInvoice._confirm_payment shop buyurtmasini yakunlashi (qarzga yozilmasdan)
"""
from datetime import datetime

import pytest

from database import models, crud


@pytest.fixture
def products(db_session):
    """Zaxirasi bor 2 ta mahsulot"""
    p1 = models.Product(name="Shop Sement", category="sement", unit="qop",
                        selling_price=12000, production_cost=7000, is_active=True)
    p2 = models.Product(name="Shop Kafel", category="kafel", unit="dona",
                        selling_price=8000, production_cost=4000, is_active=True)
    p3 = models.Product(name="Shop Aktiv Emas", category="boshqa", unit="dona",
                        selling_price=1000, production_cost=500, is_active=False)
    db_session.add_all([p1, p2, p3])
    db_session.flush()
    for p in (p1, p2):
        db_session.add(models.WarehouseTransaction(
            product_id=p.id, quantity=200, transaction_type=models.TransactionType.PRODUCTION,
            user_id=1, user_name="Test",
        ))
    db_session.commit()
    for p in (p1, p2, p3):
        db_session.refresh(p)
    return {"p1": p1, "p2": p2, "p3": p3}


def _sales(db_session):
    return db_session.query(models.Sale).order_by(models.Sale.id).all()


class TestCashOrder:
    def test_cash_order_creates_sales_and_customer(self, db_session, products):
        p1, p2 = products["p1"], products["p2"]
        order = crud.create_shop_order(
            db_session, name="Ali Do'konchi", phone="+998 90 123 45 67",
            address="Chilonzor", method="cash",
            items=[{"product_id": p1.id, "quantity": 2},
                   {"product_id": p2.id, "quantity": 5}],
        )
        assert order.order_number.startswith("SHOP-")
        assert order.status == "yakunlangan"
        assert order.paid_at is not None
        assert order.total_amount == 2 * 12000 + 5 * 8000  # 64 000
        assert len(order.items) == 2

        # Sale sifatida yozilgan (har bir qator uchun)
        sales = _sales(db_session)
        assert len(sales) == 2
        by_product = {s.product_id: s for s in sales}
        assert by_product[p1.id].quantity == 2
        assert by_product[p1.id].total_amount == 24_000
        assert by_product[p1.id].payment_method == "cash"
        assert by_product[p2.id].quantity == 5

        # Mijoz CRM'ga qo'shilgan
        cust = db_session.query(models.Customer).filter(
            models.Customer.phone == "+998901234567"
        ).first()
        assert cust is not None
        assert order.customer_id == cust.id
        db_session.refresh(cust)
        assert cust.total_purchases == 64_000

        # Zaxira kamaygan (200 - sotilgan)
        assert crud.get_available_product_qty(db_session, p1.id) == 198
        assert crud.get_available_product_qty(db_session, p2.id) == 195

    def test_cash_order_returns_dict(self, db_session, products):
        p1 = products["p1"]
        order = crud.create_shop_order(
            db_session, name="Bekzod", phone="+998901112233", method="cash",
            items=[{"product_id": p1.id, "quantity": 1}],
        )
        d = crud.shop_order_to_dict(order)
        assert d["status"] == "yakunlangan"
        assert d["method_label"] == "Naqd"
        assert len(d["items"]) == 1
        assert d["items"][0]["product_name"] == "Shop Sement"

    def test_duplicate_items_merged(self, db_session, products):
        p1 = products["p1"]
        order = crud.create_shop_order(
            db_session, name="Ali", phone="+998901112244", method="cash",
            items=[{"product_id": p1.id, "quantity": 1},
                   {"product_id": p1.id, "quantity": 2}],
        )
        assert len(order.items) == 1
        assert order.items[0].quantity == 3
        assert order.total_amount == 36_000


class TestOnlineOrder:
    def test_online_order_pending_until_payment(self, db_session, products):
        p1 = products["p1"]
        order = crud.create_shop_order(
            db_session, name="Vali", phone="+998901112255", method="click",
            items=[{"product_id": p1.id, "quantity": 10}],
        )
        assert order.status == "kutilmoqda"
        assert order.method == "click"
        # To'lovgacha Sale yozilmaydi va zaxira o'zgarmaydi
        assert _sales(db_session) == []
        assert crud.get_available_product_qty(db_session, p1.id) == 200

        crud.finalize_shop_order_payment(db_session, order.id, method="click",
                                         invoice_id="INV-TEST-1")
        db_session.refresh(order)
        assert order.status == "yakunlangan"
        assert order.invoice_id == "INV-TEST-1"

        sales = _sales(db_session)
        assert len(sales) == 1
        assert sales[0].product_id == p1.id
        assert sales[0].payment_method == "click"
        assert crud.get_available_product_qty(db_session, p1.id) == 190

        # Idempotent — ikkinchi marta yakunlash qo'shimcha Sale yaratmaydi
        crud.finalize_shop_order_payment(db_session, order.id, method="click")
        assert len(_sales(db_session)) == 1

    def test_cancel_pending_order(self, db_session, products):
        p1 = products["p1"]
        order = crud.create_shop_order(
            db_session, name="Sobir", phone="+998901112266", method="payme",
            items=[{"product_id": p1.id, "quantity": 3}],
        )
        crud.cancel_shop_order(db_session, order.id)
        db_session.refresh(order)
        assert order.status == "bekor_qilingan"
        assert _sales(db_session) == []

        # Yakunlanganni bekor qilib bo'lmaydi
        order2 = crud.create_shop_order(
            db_session, name="Sobir", phone="+998901112266", method="cash",
            items=[{"product_id": p1.id, "quantity": 1}],
        )
        with pytest.raises(ValueError):
            crud.cancel_shop_order(db_session, order2.id)


class TestValidation:
    def test_unavailable_quantity_rejected(self, db_session, products):
        p1 = products["p1"]
        with pytest.raises(ValueError) as e:
            crud.create_shop_order(
                db_session, name="Ali", phone="+998901112277", method="cash",
                items=[{"product_id": p1.id, "quantity": 500}],
            )
        assert "zaxirada" in str(e.value)

    def test_inactive_product_rejected(self, db_session, products):
        p3 = products["p3"]
        with pytest.raises(ValueError):
            crud.create_shop_order(
                db_session, name="Ali", phone="+998901112277", method="cash",
                items=[{"product_id": p3.id, "quantity": 1}],
            )

    def test_empty_cart_rejected(self, db_session, products):
        with pytest.raises(ValueError):
            crud.create_shop_order(db_session, name="Ali", phone="+998901112277",
                                   method="cash", items=[])

    def test_bad_phone_rejected(self, db_session, products):
        p1 = products["p1"]
        with pytest.raises(ValueError):
            crud.create_shop_order(db_session, name="Ali", phone="123",
                                   method="cash",
                                   items=[{"product_id": p1.id, "quantity": 1}])

    def test_unknown_method_rejected(self, db_session, products):
        p1 = products["p1"]
        with pytest.raises(ValueError):
            crud.create_shop_order(db_session, name="Ali", phone="+998901112277",
                                   method="bank",
                                   items=[{"product_id": p1.id, "quantity": 1}])

    def test_unknown_product_rejected(self, db_session):
        with pytest.raises(ValueError):
            crud.create_shop_order(db_session, name="Ali", phone="+998901112277",
                                   method="cash",
                                   items=[{"product_id": 999999, "quantity": 1}])


class TestMixedOrder:
    def _mixed(self, db_session, products, cash=20_000, gateway="click", **kw):
        p1, p2 = products["p1"], products["p2"]
        return crud.create_shop_order(
            db_session, name="Mixed Mijoz", phone="+998901119900",
            method="mixed", cash_amount=cash, online_gateway=gateway,
            items=[{"product_id": p1.id, "quantity": 2},
                   {"product_id": p2.id, "quantity": 5}],
            **kw,
        )

    def _payment_sums(self, db_session, sales):
        rows = db_session.query(models.Payment).filter(
            models.Payment.sale_id.in_([s.id for s in sales])
        ).all()
        by_method: dict = {}
        for r in rows:
            by_method[r.method] = by_method.get(r.method, 0) + (r.amount or 0)
        return by_method

    def test_mixed_order_split_fields(self, db_session, products):
        # Jami 2*12000 + 5*8000 = 64 000; naqd 20 000, onlayn 44 000
        order = self._mixed(db_session, products, cash=20_000, gateway="click")
        assert order.method == "mixed"
        assert order.online_gateway == "click"
        assert order.cash_amount == 20_000
        assert order.online_amount == 44_000
        assert order.total_amount == 64_000
        assert order.status == "kutilmoqda"
        # To'lovgacha Sale yozilmaydi / zaxira o'zgarmaydi
        assert _sales(db_session) == []
        assert crud.get_available_product_qty(db_session, products["p1"].id) == 200

    def test_mixed_finalize_writes_split_payments(self, db_session, products):
        order = self._mixed(db_session, products, cash=20_000, gateway="click")
        crud.finalize_shop_order_payment(db_session, order.id, method="click",
                                         invoice_id="INV-MIX-1")
        db_session.refresh(order)
        assert order.status == "yakunlangan"

        sales = _sales(db_session)
        assert len(sales) == 2
        assert all(s.payment_method == "mixed" for s in sales)
        # Qator summalari buzilmagan
        by_product = {s.product_id: s for s in sales}
        assert by_product[products["p1"].id].total_amount == 24_000
        assert by_product[products["p2"].id].total_amount == 40_000

        # Har bir qator bo'yicha onlayn + naqd qismlar aynan qator summasini beradi
        for s in sales:
            line_pay = sum(p.amount for p in s.payments)
            assert abs(line_pay - s.total_amount) < 1e-6

        by_method = self._payment_sums(db_session, sales)
        assert abs(by_method.get("cash", 0) - 20_000) < 0.01   # naqd qismi
        assert abs(by_method.get("click", 0) - 44_000) < 0.01  # onlayn qismi

        # Zaxira kamaygan
        assert crud.get_available_product_qty(db_session, products["p1"].id) == 198
        assert crud.get_available_product_qty(db_session, products["p2"].id) == 195

        # Idempotent
        crud.finalize_shop_order_payment(db_session, order.id, method="click")
        assert len(_sales(db_session)) == 2

    def test_mixed_split_exact_on_odd_total(self, db_session, products):
        """Qoldiqli bo'linish ham aynan yig'iladi (so'm aniqligida)"""
        p1, p2 = products["p1"], products["p2"]
        # Jami 1*12000 + 1*8000 = 20 000; naqd 7 777 -> onlayn 12 223
        order = crud.create_shop_order(
            db_session, name="Odd", phone="+998901119911", method="mixed",
            cash_amount=7_777, online_gateway="payme",
            items=[{"product_id": p1.id, "quantity": 1},
                   {"product_id": p2.id, "quantity": 1}],
        )
        assert order.online_amount == 12_223
        crud.finalize_shop_order_payment(db_session, order.id, method="payme")
        by_method = self._payment_sums(db_session, _sales(db_session))
        assert abs(by_method.get("cash", 0) - 7_777) < 0.01
        assert abs(by_method.get("payme", 0) - 12_223) < 0.01

    def test_mixed_invalid_inputs(self, db_session, products):
        p1 = products["p1"]
        items = [{"product_id": p1.id, "quantity": 1}]
        # Naqd qismi 0
        with pytest.raises(ValueError):
            crud.create_shop_order(db_session, name="X", phone="+998901119912",
                                   method="mixed", cash_amount=0,
                                   online_gateway="click", items=items)
        # Naqd qismi jami summani to'liq qoplaydi
        with pytest.raises(ValueError):
            crud.create_shop_order(db_session, name="X", phone="+998901119912",
                                   method="mixed", cash_amount=12_000,
                                   online_gateway="click", items=items)
        # Noto'g'ri gateway
        with pytest.raises(ValueError):
            crud.create_shop_order(db_session, name="X", phone="+998901119912",
                                   method="mixed", cash_amount=5_000,
                                   online_gateway="bank", items=items)
        # To'liq onlayn usulda naqd qismi kiritilmaydi
        with pytest.raises(ValueError):
            crud.create_shop_order(db_session, name="X", phone="+998901119912",
                                   method="click", cash_amount=5_000, items=items)

    def test_mixed_to_dict_breakdown(self, db_session, products):
        order = self._mixed(db_session, products, cash=20_000, gateway="payme")
        d = crud.shop_order_to_dict(order)
        assert d["method"] == "mixed"
        assert d["method_label"] == "Payme + Naqd"
        assert d["online_gateway"] == "payme"
        assert d["cash_amount"] == 20_000
        assert d["online_amount"] == 44_000


class TestPaymentConfirmIntegration:
    def test_confirm_payment_finalizes_shop_order(self, db_session, products):
        """Webhook tasdiqlashi (payments._confirm_payment) shop buyurtmasini yakunlaydi"""
        from dashboard import payments as p_mod

        p1 = products["p1"]
        order = crud.create_shop_order(
            db_session, name="Karim", phone="+998901112288", method="click",
            items=[{"product_id": p1.id, "quantity": 4}],
        )
        invoice = p_mod.create_payment_invoice(
            db_session, gateway="click", amount=order.total_amount,
            customer_id=order.customer_id, customer_name=order.customer_name,
            note=order.order_number,
        )
        invoice.shop_order_id = order.id
        order.invoice_id = invoice.invoice_id
        db_session.commit()
        db_session.refresh(invoice)

        p_mod._confirm_payment(db_session, invoice, gateway="click")

        assert invoice.status == "paid"
        db_session.refresh(order)
        assert order.status == "yakunlangan"
        sales = _sales(db_session)
        assert len(sales) == 1
        assert sales[0].payment_method == "click"
        # Qarzga yozilmaydi (to'lov buyurtmaga ketdi, FIFO qarz yopish emas)
        db_session.refresh(order)
        cust = db_session.query(models.Customer).get(order.customer_id)
        assert cust.total_debt == 0
        assert cust.total_purchases == 48_000

    def test_confirm_payment_finalizes_mixed_order(self, db_session, products):
        """Webhook faqat onlayn qismini tasdiqlaydi — aralash buyurtma to'liq yoziladi"""
        from dashboard import payments as p_mod

        p1 = products["p1"]
        order = crud.create_shop_order(
            db_session, name="Mixed Webhook", phone="+998901119913",
            method="mixed", cash_amount=8_000, online_gateway="click",
            items=[{"product_id": p1.id, "quantity": 3}],  # jami 36 000
        )
        assert order.online_amount == 28_000

        invoice = p_mod.create_payment_invoice(
            db_session, gateway="click", amount=order.online_amount,
            customer_id=order.customer_id, customer_name=order.customer_name,
            note=order.order_number,
        )
        invoice.shop_order_id = order.id
        order.invoice_id = invoice.invoice_id
        db_session.commit()
        db_session.refresh(invoice)

        p_mod._confirm_payment(db_session, invoice, gateway="click")

        assert invoice.status == "paid"
        db_session.refresh(order)
        assert order.status == "yakunlangan"
        sales = _sales(db_session)
        assert len(sales) == 1
        assert sales[0].payment_method == "mixed"
        by_method: dict = {}
        for p in sales[0].payments:
            by_method[p.method] = by_method.get(p.method, 0) + (p.amount or 0)
        assert abs(by_method.get("click", 0) - 28_000) < 0.01
        assert abs(by_method.get("cash", 0) - 8_000) < 0.01
