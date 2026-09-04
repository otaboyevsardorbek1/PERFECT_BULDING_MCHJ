"""
Mijoz triaji (Oltin/Kumush/Bronza) va o'xshash mahsulot taklifi testlari (TZ asosida)
"""
from datetime import datetime, timedelta

from database import models, crud


class TestCustomerTier:
    def _customer(self, db_session, name, purchases=0, debt=0):
        c = models.Customer(name=name, total_purchases=purchases, total_debt=debt)
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)
        return c

    def test_bronze_by_default(self, db_session):
        c = self._customer(db_session, "Bronza Client")
        assert crud.calculate_customer_tier(db_session, c) == "bronze"

    def test_silver_threshold(self, db_session):
        c = self._customer(db_session, "Silver", purchases=20_000_000)
        assert crud.calculate_customer_tier(db_session, c) == "silver"

    def test_gold_threshold(self, db_session):
        c = self._customer(db_session, "Gold", purchases=60_000_000)
        assert crud.calculate_customer_tier(db_session, c) == "gold"

    def test_high_debt_downgrades(self, db_session):
        # Qarz xaridning 50% dan oshsa — daraja pasayadi
        c = self._customer(db_session, "Gold Debtor", purchases=60_000_000, debt=50_000_000)
        assert crud.calculate_customer_tier(db_session, c) == "silver"

    def test_overdue_credit_downgrades_to_bronze(self, db_session):
        p = models.Product(name="Tier Test Product", category="sement", unit="qop",
                           selling_price=12000, production_cost=7000, is_active=True)
        db_session.add(p)
        db_session.commit()
        db_session.refresh(p)
        c = self._customer(db_session, "Overdue Gold", purchases=60_000_000)
        sale = models.Sale(
            invoice_number=f"INV-TIER-{datetime.utcnow().timestamp()}",
            product_id=p.id, quantity=1, unit_price=1_000_000,
            total_amount=1_000_000, customer_id=c.id, customer_name=c.name,
            is_credit=True, paid_amount=0, credit_status="muddati_otgan",
            due_date=datetime.utcnow() - timedelta(days=5),
        )
        db_session.add(sale)
        db_session.commit()
        assert crud.calculate_customer_tier(db_session, c) == "bronze"

    def test_segmentation_counts(self, db_session):
        self._customer(db_session, "G1", purchases=60_000_000)
        self._customer(db_session, "G2", purchases=70_000_000)
        self._customer(db_session, "S1", purchases=20_000_000)
        self._customer(db_session, "B1")
        seg = crud.get_customer_segmentation(db_session)
        assert seg["gold"] == 2
        assert seg["silver"] == 1
        assert seg["bronze"] == 1
        assert seg["total"] == 4

    def test_list_by_tier(self, db_session):
        self._customer(db_session, "Gold A", purchases=60_000_000)
        self._customer(db_session, "Bronze A")
        gold = crud.list_customers_by_tier(db_session, "gold")
        assert len(gold) == 1 and gold[0].name == "Gold A"

    def test_customer_to_dict_includes_tier(self, db_session):
        c = self._customer(db_session, "Dict Gold", purchases=60_000_000)
        d = crud.customer_to_dict(db_session, c)
        assert d["tier"] == "gold"
        assert d["tier_label"] == "🏅 Oltin mijoz"


class TestRelatedProducts:
    def _product(self, db_session, name, category, price, stock=100):
        p = models.Product(name=name, category=category, unit="dona",
                           selling_price=price, production_cost=price * 0.5,
                           is_active=True)
        db_session.add(p)
        db_session.commit()
        db_session.refresh(p)
        # Omborda qoldiq (WarehouseTransaction PRODUCTION orqali —
        # get_available_product_qty faqat PRODUCTION/SALE/RETURN hisoblaydi)
        tx = models.WarehouseTransaction(
            product_id=p.id, quantity=stock,
            transaction_type=models.TransactionType.PRODUCTION, user_id=1,
        )
        db_session.add(tx)
        db_session.commit()
        return p

    def test_same_category_related(self, db_session):
        gisht = self._product(db_session, "G'isht M150", "gisht", 1200)
        sement = self._product(db_session, "Sement M500", "sement", 12000)
        arm = self._product(db_session, "Armatura A500", "rodbin", 15000)
        # G'isht kategoriyasida yana bitta
        gisht2 = self._product(db_session, "G'isht M100", "gisht", 1000)

        related = crud.get_related_products(db_session, gisht.id, limit=5)
        ids = [p.id for p in related]
        assert gisht2.id in ids          # bir xil kategoriya birinchi
        assert sement.id not in ids      # boshqa kategoriya chiqmaydi

    def test_fallback_when_no_same_category(self, db_session):
        kafel = self._product(db_session, "Kafel 30x30", "kafel", 850)
        sement = self._product(db_session, "Sement M500", "sement", 12000)
        arm = self._product(db_session, "Armatura A500", "rodbin", 15000)
        related = crud.get_related_products(db_session, kafel.id, limit=5)
        assert len(related) > 0
        assert all(p.id != kafel.id for p in related)

    def test_excludes_self_and_inactive(self, db_session):
        p1 = self._product(db_session, "Mahsulot 1", "kat", 1000)
        p2 = models.Product(name="Inactive", category="kat", unit="dona",
                            selling_price=500, production_cost=250, is_active=False)
        db_session.add(p2)
        db_session.commit()
        related = crud.get_related_products(db_session, p1.id, limit=5)
        assert all(r.id != p1.id for r in related)
        assert all(r.is_active for r in related)

    def test_no_stock_excluded(self, db_session):
        p1 = self._product(db_session, "Asosiy", "kat", 1000, stock=50)
        no_stock = models.Product(name="Stoksiz", category="kat", unit="dona",
                                  selling_price=900, production_cost=400, is_active=True)
        db_session.add(no_stock)
        db_session.commit()
        related = crud.get_related_products(db_session, p1.id, limit=5)
        assert all(r.id != no_stock.id for r in related)

    def test_missing_product_returns_empty(self, db_session):
        assert crud.get_related_products(db_session, 99999) == []