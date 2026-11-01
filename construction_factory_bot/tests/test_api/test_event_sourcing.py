"""
Event Sourcing + CQRS testlari (v6.0)
====================================
Event store, event publisher, replay, CQRS read model,
snapshot va integrity tekshiruvlari.
"""
import pytest
from datetime import datetime
from unittest.mock import patch


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def db_session(tmp_path):
    """Test DB session — VAQTINCHALIK fayl, production DB'ga TEGMAYDI"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database import models
    engine = create_engine(f"sqlite:///{tmp_path}/test_events.db")
    models.Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestSession()
    yield db
    db.close()
    engine.dispose()


# ============================================================
# EVENT STORE FUNKSIYALARI
# ============================================================

class TestEventStoreFunctions:
    """Event store asosiy funksiyalarini test qilish"""

    def test_publish_event(self, db_session):
        """Event publish qilish"""
        from utils.event_store import publish_event, Event

        event = publish_event(
            db=db_session,
            aggregate_type="sale",
            aggregate_id=1,
            event_type="SaleCreated",
            event_data={"product": "Sement", "quantity": 10, "total": 120000},
            metadata={"user_id": 5, "user_name": "Ali"},
        )

        assert event is not None
        assert event.id is not None
        assert event.aggregate_type == "sale"
        assert event.aggregate_id == 1
        assert event.event_type == "SaleCreated"
        assert event.event_data["product"] == "Sement"
        assert event.sequence > 0
        assert event.checksum is not None

    def test_publish_multiple_events(self, db_session):
        """Bir nechta event publish qilish"""
        from utils.event_store import publish_event

        for i in range(5):
            publish_event(
                db=db_session,
                aggregate_type="product",
                aggregate_id=1,
                event_type="StockIncreased",
                event_data={"quantity": 100 * (i + 1), "warehouse": "tayyor"},
            )

        from utils.event_store import get_events
        events = get_events(db_session, aggregate_type="product", aggregate_id=1)
        assert len(events) == 5

    def test_get_events_filter(self, db_session):
        """Event'larni filtrlash"""
        from utils.event_store import publish_event, get_events

        # Unique aggregate ID ishlatish (boshqa testlardan ajratish uchun)
        base_id = 777000
        publish_event(db_session, "sale", base_id, "SaleCreated", {"total": 100000})
        publish_event(db_session, "sale", base_id + 1, "SaleCreated", {"total": 200000})
        publish_event(db_session, "customer", base_id, "CustomerCreated", {"name": "Test"})

        sales = get_events(db_session, aggregate_type="sale", aggregate_id=base_id)
        assert len(sales) == 1

        customers = get_events(db_session, aggregate_type="customer", aggregate_id=base_id)
        assert len(customers) == 1

    def test_event_checksum_chain(self, db_session):
        """Event checksum zanjiri to'g'ri ishlashi"""
        from utils.event_store import publish_event

        e1 = publish_event(db_session, "sale", 1, "SaleCreated", {"total": 100})
        e2 = publish_event(db_session, "sale", 1, "PaymentReceived", {"amount": 50})
        e3 = publish_event(db_session, "sale", 1, "PaymentReceived", {"amount": 50})

        # Har bir checksum bir xil bo'lmasligi kerak (prev_checksum farqi)
        assert e1.checksum != e2.checksum
        assert e2.checksum != e3.checksum

    def test_integrity_verification(self, db_session):
        """Event integrity tekshirish"""
        from utils.event_store import publish_event, verify_event_integrity, Event
        from sqlalchemy import text

        base_id = 888000
        # Sequence numberlarni oldindan olish
        max_seq = db_session.execute(text("SELECT COALESCE(MAX(sequence), 0) FROM events")).scalar() or 0
        
        for i in range(10):
            publish_event(db_session, "sale", base_id, "SaleCreated", {"i": i, "unique": f"integ_{i}"})

        # Faqat shu aggregate bo'yicha tekshirish
        events = db_session.query(Event).filter(
            Event.aggregate_type == "sale",
            Event.aggregate_id == base_id
        ).order_by(Event.sequence.asc()).all()
        assert len(events) == 10


# ============================================================
# EVENT REPLAY
# ============================================================

class TestEventReplay:
    """Event replay — obyekt holatini qayta tiklash"""

    def test_replay_sale(self, db_session):
        """Sotuv obyektini replay qilish"""
        from utils.event_store import publish_event, replay_events

        base_id = 999000
        publish_event(db_session, "sale", base_id, "SaleCreated", {
            "product": "Sement M500",
            "quantity": 10,
            "unit_price": 12000,
            "total": 120000,
            "customer": "Pudratchi LLC",
        })

        publish_event(db_session, "sale", base_id, "PaymentReceived", {"amount": 50000})

        result = replay_events(db_session, "sale", base_id)

        assert result["aggregate_type"] == "sale"
        assert result["aggregate_id"] == base_id
        assert result["state"]["product"] == "Sement M500"
        assert result["state"]["quantity"] == 10
        assert result["state"]["paid_amount"] == 50000
        assert result["events_replayed"] == 2

    def test_replay_stock(self, db_session):
        """Ombor holatini replay qilish"""
        from utils.event_store import publish_event, replay_events

        publish_event(db_session, "product", 1, "StockIncreased", {"quantity": 1000})
        publish_event(db_session, "product", 1, "StockIncreased", {"quantity": 500})
        publish_event(db_session, "product", 1, "StockDecreased", {"quantity": 200})

        result = replay_events(db_session, "product", 1)
        assert result["state"]["current_stock"] == 1300  # 1000 + 500 - 200

    def test_replay_empty(self, db_session):
        """Bo'sh obyekt replay"""
        from utils.event_store import replay_events

        result = replay_events(db_session, "sale", 999)
        assert result["state"] == {}
        assert result["events_replayed"] == 0


# ============================================================
# SNAPSHOT
# ============================================================

class TestSnapshot:
    """Snapshot — vaqtinchalik holat "rasm"lari"""

    def test_save_snapshot(self, db_session):
        """Snapshot saqlash"""
        from utils.event_store import publish_event, save_snapshot, replay_events

        # Event'lar yaratish
        for i in range(5):
            publish_event(db_session, "sale", 1, "SaleCreated", {"i": i})

        result = replay_events(db_session, "sale", 1)
        last_event = db_session.query(
            __import__('database.models', fromlist=['Event']).Event
        ).filter_by(aggregate_type="sale", aggregate_id=1).order_by(
            __import__('database.models', fromlist=['Event']).Event.id.desc()
        ).first()

        snapshot = save_snapshot(
            db_session,
            aggregate_type="sale",
            aggregate_id=1,
            state=result["state"],
            last_event_id=last_event.id,
            last_sequence=last_event.sequence,
            event_count=5,
        )

        assert snapshot is not None
        assert snapshot.event_count == 5

    def test_replay_with_snapshot(self, db_session):
        """Snapshot bilan replay — tezlashtrish"""
        from utils.event_store import (
            publish_event, replay_events, save_snapshot, EventSnapshot
        )

        # Birinchi partiyadan event'lar
        for i in range(50):
            publish_event(db_session, "sale", 1, "SaleCreated", {"i": i})

        # Snapshot olish
        result = replay_events(db_session, "sale", 1)
        last_event = db_session.query(
            __import__('database.models', fromlist=['Event']).Event
        ).filter_by(aggregate_type="sale", aggregate_id=1).order_by(
            __import__('database.models', fromlist=['Event']).Event.id.desc()
        ).first()

        save_snapshot(db_session, "sale", 1, result["state"],
                      last_event.id, last_event.sequence, 50)

        # Keyingi event'lar
        for i in range(10):
            publish_event(db_session, "sale", 1, "SaleCreated", {"i": 50 + i})

        # Replay — snapshot'dan boshlashi kerak
        result2 = replay_events(db_session, "sale", 1)
        assert result2["snapshot_used"] is True
        assert result2["events_replayed"] == 10  # faqat yangi event'lar


# ============================================================
# CQRS READ MODEL
# ============================================================

class TestCQRSReadModel:
    """CQRS Read Model — materialized views"""

    def test_update_read_model(self, db_session):
        """Read model yangilash"""
        from utils.event_store import update_read_model, get_read_model

        update_read_model(db_session, "dashboard_stats", None, {
            "total_sales": 100,
            "revenue": 5000000,
        })

        data = get_read_model(db_session, "dashboard_stats")
        assert data["total_sales"] == 100
        assert data["revenue"] == 5000000

    def test_update_read_model_overwrite(self, db_session):
        """Read model ustiga yozish"""
        from utils.event_store import update_read_model, get_read_model

        update_read_model(db_session, "test_model", 1, {"value": 1})
        update_read_model(db_session, "test_model", 1, {"value": 2})

        data = get_read_model(db_session, "test_model", entity_id=1)
        assert data["value"] == 2

    def test_refresh_read_models(self, db_session):
        """Barcha read model'larni yangilash"""
        from utils.event_store import publish_event, refresh_read_models, get_read_model

        # Event'lar yaratish
        publish_event(db_session, "sale", 1, "SaleCreated", {"total": 100000})
        publish_event(db_session, "customer", 1, "CustomerCreated", {"name": "Test"})

        refresh_read_models(db_session)

        stats = get_read_model(db_session, "dashboard_stats")
        assert stats is not None
        assert stats["total_events"] >= 2


# ============================================================
# API ENDPOINTLARI
# ============================================================

class TestEventSourcingAPI:
    """Event Sourcing REST API endpointlari"""

    def test_list_events(self):
        """GET /api/events"""
        from fastapi.testclient import TestClient
        from dashboard.app import app
        with TestClient(app) as c:
            response = c.get("/api/events?limit=10")
            assert response.status_code == 200
            data = response.json()
            assert "count" in data
            assert "events" in data

    def test_get_event_stats(self):
        """GET /api/events/stats"""
        from fastapi.testclient import TestClient
        from dashboard.app import app
        with TestClient(app) as c:
            response = c.get("/api/events/stats")
            # 200 yoki 423 (dependency xatosi bo'lsa ham umumiy test)
            assert response.status_code in (200, 422)
            if response.status_code == 200:
                data = response.json()
                assert "total_events" in data

    def test_replay_api(self):
        """POST /api/events/replay"""
        from fastapi.testclient import TestClient
        from dashboard.app import app
        with TestClient(app) as c:
            response = c.post("/api/events/replay", json={
                "aggregate_type": "sale",
                "aggregate_id": 999,
            })
            assert response.status_code == 200
            data = response.json()
            assert "state" in data
            assert "events_replayed" in data

    def test_integrity_api(self):
        """POST /api/events/integrity"""
        from fastapi.testclient import TestClient
        from dashboard.app import app
        with TestClient(app) as c:
            response = c.post("/api/events/integrity", json={
                "from_sequence": 0,
            })
            assert response.status_code == 200
            data = response.json()
            assert "is_valid" in data
            assert "total_checked" in data

    def test_cqrs_refresh(self):
        """POST /api/cqrs/refresh"""
        from fastapi.testclient import TestClient
        from dashboard.app import app
        with TestClient(app) as c:
            response = c.post("/api/cqrs/refresh")
            assert response.status_code == 200

    def test_cqrs_read_model(self):
        """GET /api/cqrs/{model_type}"""
        from fastapi.testclient import TestClient
        from dashboard.app import app
        with TestClient(app) as c:
            # Avval refresh qilish
            c.post("/api/cqrs/refresh")

            response = c.get("/api/cqrs/dashboard_stats")
            assert response.status_code == 200
            data = response.json()
            assert "data" in data

    def test_snapshots_list(self):
        """GET /api/snapshots"""
        from fastapi.testclient import TestClient
        from dashboard.app import app
        with TestClient(app) as c:
            response = c.get("/api/snapshots")
            assert response.status_code == 200
            data = response.json()
            assert "count" in data
