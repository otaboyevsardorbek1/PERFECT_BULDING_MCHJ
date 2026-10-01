"""
Event Sourcing moduli (TZ 3.11)
================================
Barcha holat o'zgarishlari voqealar (events) sifatida saqlanadi.
Bu tizim orqali:
- Istalgan vaqtga tizim holatini qayta tiklash (replay)
- To'liq audit log (kim, qachon, nima qilgani)
- CQRS: yozish (event store) va o'qish (read model) ajratiladi

Jadvallar:
- events: barcha voqealar (append-only, o'chirilmaydi)
- event_snapshots: vaqtinchalik snapshot (tez replay uchun)
- read_models: CQRS materialized views (dashboard, hisobotlar uchun)
"""

import json
import hashlib
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy import text
from sqlalchemy.orm import Session

from database.models import (
    Base, engine, SessionLocal,
    Event, EventSnapshot, ReadModel,
)

logger = logging.getLogger(__name__)


# ============================================================
# EVENT STORE MODELLARI
# ============================================================




# ============================================================
# EVENT PUBLISHER — operatsiyalarni event sifatida yozish
# ============================================================

# Global sequence counter (thread-safe yetarli oddiy holat uchun)
_sequence_counter = 0

# Snapshot: har N ta event'dan keyin snapshot olish
SNAPSHOT_INTERVAL = 100


def _next_sequence(db: Session) -> int:
    """Keyingi global sequence raqamini olish"""
    global _sequence_counter
    if _sequence_counter == 0:
        # DB'dan eng oxirgi sequence'ni olish
        result = db.execute(text("SELECT COALESCE(MAX(sequence), 0) FROM events"))
        _sequence_counter = result.scalar() or 0
    _sequence_counter += 1
    return _sequence_counter


def _compute_checksum(event_data: dict, prev_checksum: Optional[str] = None) -> str:
    """Event integrity uchun checksum (SHA256)"""
    payload = json.dumps(event_data, sort_keys=True, default=str)
    if prev_checksum:
        payload = prev_checksum + payload
    return hashlib.sha256(payload.encode()).hexdigest()


def publish_event(
    db: Session,
    aggregate_type: str,
    aggregate_id: int,
    event_type: str,
    event_data: dict,
    metadata: Optional[dict] = None,
) -> Event:
    """
    Event'ni store'ga yozish (append-only).
    
    Misol:
        publish_event(db, "sale", sale_id, "SaleCreated", {
            "product": "Sement M500",
            "quantity": 10,
            "total": 120000,
        }, metadata={"user_id": 5, "user_name": "Ali"})
    """
    # Oldingi event'ning checksum'ini olish
    last_event = db.query(Event).filter(
        Event.aggregate_type == aggregate_type,
        Event.aggregate_id == aggregate_id
    ).order_by(Event.id.desc()).first()
    
    prev_checksum = last_event.checksum if last_event else None
    
    # Sequence
    seq = _next_sequence(db)
    
    # Checksum
    checksum = _compute_checksum(event_data, prev_checksum)
    
    event = Event(
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event_type,
        event_data=event_data,
        metadata_json=metadata or {},
        sequence=seq,
        version=1,
        checksum=checksum,
        occurred_at=datetime.utcnow(),
        recorded_at=datetime.utcnow(),
    )
    
    db.add(event)
    db.flush()  # ID olish uchun
    
    logger.info(
        f"Event yozildi: {event_type} | {aggregate_type}/{aggregate_id} | seq={seq}"
    )
    
    return event


def get_events(
    db: Session,
    aggregate_type: Optional[str] = None,
    aggregate_id: Optional[int] = None,
    event_type: Optional[str] = None,
    after_sequence: Optional[int] = None,
    after_time: Optional[datetime] = None,
    limit: int = 100,
) -> List[Event]:
    """
    Event'larni olish (filter bilan).
    """
    q = db.query(Event)
    
    if aggregate_type:
        q = q.filter(Event.aggregate_type == aggregate_type)
    if aggregate_id is not None:
        q = q.filter(Event.aggregate_id == aggregate_id)
    if event_type:
        q = q.filter(Event.event_type == event_type)
    if after_sequence is not None:
        q = q.filter(Event.sequence > after_sequence)
    if after_time:
        q = q.filter(Event.occurred_at > after_time)
    
    return q.order_by(Event.sequence.asc()).limit(limit).all()


def replay_events(
    db: Session,
    aggregate_type: str,
    aggregate_id: int,
    from_sequence: Optional[int] = None,
) -> dict:
    """
    Event replay — obyektning joriy holatini event'lardan qayta tiklash.
    
    1. Eng so'nggi snapshot'ni topish
    2. Snapshot'dan keyingi event'larni olish
    3. Har bir event'ni qo'llash → joriy holat
    """
    # 1. Snapshot qidirish
    snapshot = db.query(EventSnapshot).filter(
        EventSnapshot.aggregate_type == aggregate_type,
        EventSnapshot.aggregate_id == aggregate_id
    ).order_by(EventSnapshot.last_sequence.desc()).first()
    
    if snapshot:
        state = dict(snapshot.snapshot_data)
        start_seq = snapshot.last_sequence
        logger.info(f"Snapshot topildi: seq={start_seq}, {len(state)} ta field")
    else:
        state = {}
        start_seq = 0
    
    # 2. Event'larni olish
    q = db.query(Event).filter(
        Event.aggregate_type == aggregate_type,
        Event.aggregate_id == aggregate_id,
    )
    if from_sequence is not None:
        q = q.filter(Event.sequence > from_sequence)
    elif start_seq > 0:
        q = q.filter(Event.sequence > start_seq)
    
    events = q.order_by(Event.sequence.asc()).all()
    
    # 3. Event'larni qo'llash
    for event in events:
        state = _apply_event(state, event)
    
    return {
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "state": state,
        "events_replayed": len(events),
        "last_sequence": events[-1].sequence if events else start_seq,
        "snapshot_used": snapshot is not None,
    }


def _apply_event(state: dict, event: Event) -> dict:
    """
    Bitta event'ni state ga qo'llash.
    Event turlari bo'yicha turli logika.
    """
    data = event.event_data
    event_type = event.event_type
    
    if event_type == "SaleCreated":
        state["id"] = event.aggregate_id
        state["product"] = data.get("product")
        state["quantity"] = data.get("quantity", 0)
        state["unit_price"] = data.get("unit_price", 0)
        state["total_amount"] = data.get("total", 0)
        state["customer"] = data.get("customer")
        state["status"] = "completed"
        state["created_at"] = str(event.occurred_at)
        
    elif event_type == "SaleCancelled":
        state["status"] = "cancelled"
        
    elif event_type == "ReturnCreated":
        state["returned_qty"] = data.get("quantity", 0)
        state["returned_amount"] = data.get("amount", 0)
        state["return_reason"] = data.get("reason")
        
    elif event_type == "PaymentReceived":
        paid = state.get("paid_amount", 0) + data.get("amount", 0)
        state["paid_amount"] = paid
        if paid >= state.get("total_amount", 0):
            state["credit_status"] = "toliq_tolangan"
        else:
            state["credit_status"] = "qisman"
            
    elif event_type == "StockIncreased":
        current = state.get("current_stock", 0)
        state["current_stock"] = current + data.get("quantity", 0)
        
    elif event_type == "StockDecreased":
        current = state.get("current_stock", 0)
        state["current_stock"] = current - data.get("quantity", 0)
        
    elif event_type == "PriceChanged":
        state["old_price"] = data.get("old_price")
        state["new_price"] = data.get("new_price")
        
    elif event_type == "CustomerCreated":
        state["id"] = event.aggregate_id
        state["name"] = data.get("name")
        state["phone"] = data.get("phone")
        state["credit_limit"] = data.get("credit_limit", 0)
        state["total_purchases"] = 0
        state["status"] = "faol"
        
    elif event_type == "ReservationCreated":
        state["reservation_id"] = data.get("reservation_id")
        state["reserved_qty"] = data.get("quantity", 0)
        state["expires_at"] = data.get("expires_at")
        
    elif event_type == "ReservationReleased":
        state["reserved_qty"] = 0
        state["status"] = "yechilgan"
    
    # Umumiy: event_data'dagi barcha maydonlarni state ga qo'shish
    # (overlay — oxirgi event ustunlik qiladi)
    for key, value in data.items():
        if key not in ("quantity", "amount"):  # raqamli maydonlarni qo'shmaslik
            state[key] = value
    
    return state


# ============================================================
# SNAPSHOT — vaqtinchalik holat "rasm"lari
# ============================================================

def save_snapshot(
    db: Session,
    aggregate_type: str,
    aggregate_id: int,
    state: dict,
    last_event_id: int,
    last_sequence: int,
    event_count: int,
):
    """Snapshot saqlash"""
    snapshot = EventSnapshot(
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        snapshot_data=state,
        last_event_id=last_event_id,
        last_sequence=last_sequence,
        event_count=event_count,
    )
    db.add(snapshot)
    db.flush()
    logger.info(f"Snapshot saqlandi: {aggregate_type}/{aggregate_id} seq={last_sequence}")
    return snapshot


def maybe_snapshot(db: Session, aggregate_type: str, aggregate_id: int):
    """
    Agar event soni SNAPSHOT_INTERVAL dan oshsa, yangi snapshot olish.
    Har bir publish_event dan keyin chaqiriladi.
    """
    event_count = db.query(Event).filter(
        Event.aggregate_type == aggregate_type,
        Event.aggregate_id == aggregate_id
    ).count()
    
    if event_count > 0 and event_count % SNAPSHOT_INTERVAL == 0:
        # Replay qilib snapshot olish
        result = replay_events(db, aggregate_type, aggregate_id)
        last_event = db.query(Event).filter(
            Event.aggregate_type == aggregate_type,
            Event.aggregate_id == aggregate_id
        ).order_by(Event.id.desc()).first()
        
        if last_event:
            save_snapshot(
                db,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                state=result["state"],
                last_event_id=last_event.id,
                last_sequence=last_event.sequence,
                event_count=event_count,
            )


# ============================================================
# CQRS — Read Model yangilash
# ============================================================

def update_read_model(
    db: Session,
    model_type: str,
    entity_id: Optional[int],
    model_data: dict,
    last_event_id: Optional[int] = None,
):
    """
    Read model'ni yangilash (CQRS: write → event store → read model).
    
    Misol:
        update_read_model(db, "dashboard_stats", None, {
            "total_sales_today": 1500000,
            "active_orders": 12,
            "low_stock_products": 3,
        })
    """
    existing = db.query(ReadModel).filter(
        ReadModel.model_type == model_type,
        ReadModel.entity_id == entity_id,
    ).first()
    
    if existing:
        existing.model_data = model_data
        existing.last_event_id = last_event_id
        existing.updated_at = datetime.utcnow()
    else:
        existing = ReadModel(
            model_type=model_type,
            entity_id=entity_id,
            model_data=model_data,
            last_event_id=last_event_id,
        )
        db.add(existing)
    
    db.flush()
    return existing


def get_read_model(db: Session, model_type: str, entity_id: Optional[int] = None) -> Optional[dict]:
    """Read model'dan ma'lumot olish"""
    q = db.query(ReadModel).filter(ReadModel.model_type == model_type)
    if entity_id is not None:
        q = q.filter(ReadModel.entity_id == entity_id)
    rm = q.first()
    return rm.model_data if rm else None


def refresh_read_models(db: Session):
    """
    Barcha read model'larni event store'dan qayta hisoblash.
    Dashboard yangilanganda yoki scheduler orqali chaqiriladi.
    """
    logger.info("Read model'larni yangilash boshlandi...")
    
    # 1. Dashboard statistikasi
    total_events = db.query(Event).count()
    total_sales_events = db.query(Event).filter(Event.event_type == "SaleCreated").count()
    total_customers = db.query(Event).filter(Event.event_type == "CustomerCreated").count()
    total_returns = db.query(Event).filter(Event.event_type == "ReturnCreated").count()
    
    update_read_model(db, "dashboard_stats", None, {
        "total_events": total_events,
        "total_sales_events": total_sales_events,
        "total_customers_created": total_customers,
        "total_returns": total_returns,
        "last_refreshed": str(datetime.utcnow()),
    })
    
    # 2. Event turlari bo'yicha statistika
    event_types = db.execute(text(
        "SELECT event_type, COUNT(*) as cnt FROM events GROUP BY event_type ORDER BY cnt DESC"
    )).fetchall()
    
    update_read_model(db, "event_type_stats", None, {
        "event_types": {row[0]: row[1] for row in event_types},
        "total": total_events,
    })
    
    # 3. Aggregate'lar bo'yicha statistika
    aggregates = db.execute(text(
        "SELECT aggregate_type, COUNT(DISTINCT aggregate_id) as cnt FROM events GROUP BY aggregate_type"
    )).fetchall()
    
    update_read_model(db, "aggregate_stats", None, {
        "aggregates": {row[0]: row[1] for row in aggregates},
    })
    
    # 4. Vaqtli seriyalar (soatlik event soni — oxirgi 24 soat)
    hourly = db.execute(text(
        """SELECT strftime('%Y-%m-%d %H:00', occurred_at) as hour, COUNT(*) as cnt 
           FROM events 
           WHERE occurred_at > datetime('now', '-24 hours')
           GROUP BY hour ORDER BY hour"""
    )).fetchall()
    
    update_read_model(db, "hourly_events", None, {
        "hours": [{"hour": row[0], "count": row[1]} for row in hourly],
    })
    
    db.commit()
    logger.info(f"Read model'larni yangilash tugadi: {total_events} ta event")


# ============================================================
# EVENT INTEGRITY TEKSHIRISH
# ============================================================

def verify_event_integrity(db: Session, from_seq: int = 0, to_seq: Optional[int] = None) -> dict:
    """
    Event'larning integrity'sini tekshirish (chain of hashes).
    Har bir event'ning checksum'i oldingi checksum + event_data dan hosil bo'lishi kerak.
    """
    q = db.query(Event).filter(Event.sequence >= from_seq)
    if to_seq:
        q = q.filter(Event.sequence <= to_seq)
    
    events = q.order_by(Event.sequence.asc()).all()
    
    broken = []
    prev_checksum = None
    
    for event in events:
        expected = _compute_checksum(event.event_data, prev_checksum)
        if event.checksum != expected:
            broken.append({
                "event_id": event.id,
                "sequence": event.sequence,
                "expected": expected[:16] + "...",
                "actual": (event.checksum or "")[:16] + "...",
            })
        prev_checksum = event.checksum
    
    return {
        "total_checked": len(events),
        "broken_count": len(broken),
        "broken_events": broken[:20],  # faqat birinchi 20 ta
        "is_valid": len(broken) == 0,
    }
