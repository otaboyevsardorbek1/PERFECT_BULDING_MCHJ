"""
SEKIN SOTILADIGAN ZAXIRA (30+ kun harakatlanmagan) OGOHLANTIRISHLARI testlari

check_slow_stock_notifications() fon vazifasi har 5 daqiqada chaqiriladi; har bir
tovar/xom ashyo uchun ogohlantirish BIR MARTA yuboriladi (SlowStockAlert unikalligi),
tovar harakatga qaytsa qayd o'chadi va yana N kun jim tursa qayta ogohlantiriladi.
"""
from datetime import datetime, timedelta

import pytest

from database import models, crud


class FakeNotifier:
    """Yuborilgan push bildirishnomalarni to'playdigan fake — tarmoqqa chiqmaydi"""

    def __init__(self, admin_ok=True, dept_ok=True):
        self.admin = []
        self.dept = []
        self.admin_ok = admin_ok
        self.dept_ok = dept_ok

    async def send_notification_to_admins(self, title, message, ntype):
        self.admin.append((title, message, ntype))
        return self.admin_ok

    async def send_notification_to_department(self, dept, title, message, ntype):
        self.dept.append((dept, title, message, ntype))
        return {"success": 1} if self.dept_ok else {"success": 0}


@pytest.fixture
def notifier_env(monkeypatch):
    """SLOW_STOCK_DAYS = 30 + fake push yuboruvchilar"""
    monkeypatch.setattr("config.SLOW_STOCK_DAYS", 30)
    import utils.notifications as nmod
    fake = FakeNotifier()
    monkeypatch.setattr(nmod, "send_notification_to_admins", fake.send_notification_to_admins)
    monkeypatch.setattr(nmod, "send_notification_to_department", fake.send_notification_to_department)
    return fake


@pytest.fixture
def product(db_session):
    p = models.Product(name="Sement M400", category="sement", unit="qop",
                       selling_price=95000, production_cost=60000, is_active=True)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def raw_material(db_session):
    m = models.RawMaterial(name="Klinker", category="xomashyo", unit="kg",
                           current_stock=20000, min_stock=1000,
                           price_per_unit=500)
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    return m


def _add_tx(db_session, item_type, item_id, qty, tx_type, age_days, age_hours=2):
    """Eski sanali ombor harakati yozuvi (age_hours marja floor kunlarni barqaror qiladi)"""
    when = datetime.utcnow() - timedelta(days=age_days, hours=age_hours)
    tx = models.WarehouseTransaction(
        product_id=item_id if item_type == "product" else None,
        raw_material_id=item_id if item_type == "raw" else None,
        quantity=qty,
        transaction_type=tx_type,
        user_id=7,
        user_name="Test",
        date=when,
    )
    db_session.add(tx)
    db_session.commit()
    db_session.refresh(tx)
    return tx


def _produce(db_session, product, qty, days_ago):
    """Mahsulotni omborga ishlab chiqarish (PRODUCTION kirim)"""
    return _add_tx(db_session, "product", product.id, qty,
                   models.TransactionType.PRODUCTION, days_ago)


class TestCandidates:
    def test_slow_product_found(self, db_session, product):
        _produce(db_session, product, 100, 40)
        cands = crud.get_slow_moving_products(db_session, 30)
        assert len(cands) == 1
        assert cands[0]["item_type"] == "product"
        assert cands[0]["name"] == product.name
        assert cands[0]["quantity"] == 100
        assert cands[0]["days_unmoved"] == 40

    def test_recently_moved_product_excluded(self, db_session, product):
        _produce(db_session, product, 100, 60)
        # 5 kun oldin sotilgan — harakat bor, ogohlantirilmaydi
        _add_tx(db_session, "product", product.id, 10,
                models.TransactionType.SALE, 5)
        cands = crud.get_slow_moving_products(db_session, 30)
        assert all(c["item_id"] != product.id for c in cands)

    def test_zero_stock_product_excluded(self, db_session, product):
        _produce(db_session, product, 100, 40)
        _add_tx(db_session, "product", product.id, 100,
                models.TransactionType.SALE, 40)
        cands = crud.get_slow_moving_products(db_session, 30)
        assert all(c["item_id"] != product.id for c in cands)

    def test_slow_raw_material_found(self, db_session, raw_material):
        _add_tx(db_session, "raw", raw_material.id, 20000,
                models.TransactionType.INCOME, 40)
        cands = crud.get_slow_moving_raw_materials(db_session, 30)
        assert len(cands) == 1
        assert cands[0]["name"] == raw_material.name
        assert cands[0]["days_unmoved"] == 40

    def test_recently_used_raw_excluded(self, db_session, raw_material):
        _add_tx(db_session, "raw", raw_material.id, 20000,
                models.TransactionType.INCOME, 60)
        # 3 kun oldin ishlab chiqarishda ishlatilgan
        raw_material.current_stock = 19000
        _add_tx(db_session, "raw", raw_material.id, 1000,
                models.TransactionType.PRODUCTION, 3)
        cands = crud.get_slow_moving_raw_materials(db_session, 30)
        assert all(c["item_id"] != raw_material.id for c in cands)

    def test_never_moved_raw_with_stock_found(self, db_session, raw_material):
        # Hech qachon harakat yozuvi yo'q, lekin qoldiq bor — sekin zaxira
        cands = crud.get_slow_moving_raw_materials(db_session, 30)
        assert any(c["item_id"] == raw_material.id for c in cands)

    def test_already_alerted_product_excluded(self, db_session, product):
        _produce(db_session, product, 100, 40)
        crud.mark_slow_stock_alerted(db_session, "product", product.id,
                                     days_unmoved=40, last_moved_at=datetime.utcnow())
        cands = crud.get_slow_moving_products(db_session, 30)
        assert all(c["item_id"] != product.id for c in cands)

    def test_clear_moved_alert_allows_recandidate(self, db_session, product):
        _produce(db_session, product, 100, 40)
        crud.mark_slow_stock_alerted(db_session, "product", product.id,
                                     days_unmoved=40, last_moved_at=datetime.utcnow())
        # Tovar harakatga qaytdi (sotuv) — qayd tozalanadi
        _add_tx(db_session, "product", product.id, 5, models.TransactionType.SALE, 1)
        assert crud.clear_moved_slow_stock_alerts(db_session, 30) == 1
        row = db_session.query(models.SlowStockAlert).filter(
            models.SlowStockAlert.item_type == "product",
            models.SlowStockAlert.item_id == product.id,
        ).first()
        assert row is None
        # Hozir yaqinda harakatlangani uchun nomzod emas; yana 30 kun jim tursa qayta chiqadi
        cands = crud.get_slow_moving_products(db_session, 30)
        assert all(c["item_id"] != product.id for c in cands)


class TestCheckSlowStock:
    async def test_sends_aggregated_once_and_dedupes(self, db_session, product,
                                                     raw_material, notifier_env):
        _produce(db_session, product, 100, 40)
        _add_tx(db_session, "raw", raw_material.id, 20000,
                models.TransactionType.INCOME, 40)
        from utils.notifications import check_slow_stock_notifications

        count = await check_slow_stock_notifications(db_session)
        assert count == 2
        # Rahbariyat + Ombor bo'limiga bittadan jamlangan xabar
        assert len(notifier_env.admin) == 1
        assert len(notifier_env.dept) == 1
        title, message, ntype = notifier_env.admin[0]
        assert ntype == "slow_stock"
        assert "2 ta zaxira 30+ kun harakatlanmagan" in title
        assert product.name in message
        assert raw_material.name in message
        assert "kun harakatlanmagan" in message

        rows = db_session.query(models.SlowStockAlert).all()
        assert len(rows) == 2
        assert all(r.status == "sent" for r in rows)

        # Ikkinchi chaqiruvda takror yuborilmaydi
        count2 = await check_slow_stock_notifications(db_session)
        assert count2 == 0
        assert len(notifier_env.admin) == 1
        assert len(notifier_env.dept) == 1

    async def test_no_candidates_no_send(self, db_session, product, notifier_env):
        _produce(db_session, product, 100, 5)  # yaqinda harakatlangan
        from utils.notifications import check_slow_stock_notifications

        assert await check_slow_stock_notifications(db_session) == 0
        assert notifier_env.admin == []
        assert notifier_env.dept == []

    async def test_failed_send_retried_next_cycle(self, db_session, product,
                                                  monkeypatch):
        monkeypatch.setattr("config.SLOW_STOCK_DAYS", 30)
        _produce(db_session, product, 100, 40)

        import utils.notifications as nmod
        fail = FakeNotifier(admin_ok=False, dept_ok=False)
        monkeypatch.setattr(nmod, "send_notification_to_admins", fail.send_notification_to_admins)
        monkeypatch.setattr(nmod, "send_notification_to_department", fail.send_notification_to_department)

        # Birinchi urinish — yuborilmadi (bot qabul qilmadi), qayd failed
        assert await nmod.check_slow_stock_notifications(db_session) == 0
        row = db_session.query(models.SlowStockAlert).filter(
            models.SlowStockAlert.item_type == "product",
            models.SlowStockAlert.item_id == product.id,
        ).first()
        assert row is not None and row.status == "failed"

        # Bot tiklandi — keyingi tsiklda qayta uriniladi va muvaffaqiyatli
        ok = FakeNotifier(admin_ok=True, dept_ok=True)
        monkeypatch.setattr(nmod, "send_notification_to_admins", ok.send_notification_to_admins)
        monkeypatch.setattr(nmod, "send_notification_to_department", ok.send_notification_to_department)

        count = await nmod.check_slow_stock_notifications(db_session)
        assert count == 1
        assert len(ok.admin) == 1
        db_session.refresh(row)
        assert row.status == "sent"
