"""
REST API v6.0 — Event Sourcing + CQRS (TZ 3.11)

- GET  /api/events              Event'larni olish (filter bilan)
- GET  /api/events/{id}         Bitta event tafsilotlari
- GET  /api/events/aggregate/{type}/{id}  Obyekt event'lari
- POST /api/events/replay       Event replay (obyekt holatini tiklash)
- POST /api/events/integrity    Event integrity tekshirish
- GET  /api/events/stats        Event statistikasi
- POST /api/cqrs/refresh        Read model'larni yangilash
- GET  /api/cqrs/{model_type}   Read model'dan ma'lumot olish
- GET  /api/snapshots           Snapshot ro'yxati
- POST /api/snapshots/create    Snapshot yaratish
"""
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from database.session import get_db
from database import models
from dashboard.auth import AuthUser, get_current_user
from utils.event_store import (
    get_events, replay_events, verify_event_integrity,
    save_snapshot, maybe_snapshot, update_read_model,
    get_read_model, refresh_read_models, Event, EventSnapshot, ReadModel,
    publish_event, SNAPSHOT_INTERVAL,
)

router = APIRouter(prefix="/api", tags=["v6.0 Event Sourcing"])


def require_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    """Faqat direktor/buxgalter (event'lar — audit ma'lumotlari)"""
    if user.role not in ("direktor", "buxgalter"):
        raise HTTPException(status_code=403, detail="Faqat direktor yoki buxgalter")
    return user


# ================= EVENT STORE ENDPOINTLARI =================

@router.get("/events")
def api_list_events(
    aggregate_type: Optional[str] = None,
    aggregate_id: Optional[int] = None,
    event_type: Optional[str] = None,
    after_sequence: Optional[int] = None,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_admin),
):
    """
    Event'larni olish — turli filtrlar bilan.
    
    Misollar:
      GET /api/events?aggregate_type=sale
      GET /api/events?event_type=SaleCreated&limit=10
      GET /api/events?after_sequence=1000
    """
    events = get_events(
        db,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event_type,
        after_sequence=after_sequence,
        limit=limit,
    )
    
    return {
        "count": len(events),
        "events": [
            {
                "id": e.id,
                "aggregate_type": e.aggregate_type,
                "aggregate_id": e.aggregate_id,
                "event_type": e.event_type,
                "event_data": e.event_data,
                "metadata": e.metadata_json,
                "sequence": e.sequence,
                "checksum": (e.checksum or "")[:16] + "..." if e.checksum else None,
                "occurred_at": str(e.occurred_at) if e.occurred_at else None,
            }
            for e in events
        ],
    }


@router.get("/events/{event_id}")
def api_get_event(
    event_id: int,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_admin),
):
    """Bitta event'ning to'liq tafsilotlari"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event topilmadi")
    
    return {
        "id": event.id,
        "aggregate_type": event.aggregate_type,
        "aggregate_id": event.aggregate_id,
        "event_type": event.event_type,
        "event_data": event.event_data,
        "metadata": event.metadata_json,
        "sequence": event.sequence,
        "version": event.version,
        "checksum": event.checksum,
        "occurred_at": str(event.occurred_at),
        "recorded_at": str(event.recorded_at),
    }


@router.get("/events/aggregate/{aggregate_type}/{aggregate_id}")
def api_aggregate_events(
    aggregate_type: str,
    aggregate_id: int,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_admin),
):
    """
    Bitta obyektning barcha event'lari (tarixi).
    
    Misol: sotuv #42 ning barcha o'zgarishlari
      GET /api/events/aggregate/sale/42
    """
    events = get_events(
        db,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        limit=limit,
    )
    
    return {
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "total_events": len(events),
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "event_data": e.event_data,
                "sequence": e.sequence,
                "occurred_at": str(e.occurred_at) if e.occurred_at else None,
            }
            for e in events
        ],
    }


# ================= EVENT REPLAY =================

class ReplayRequest(BaseModel):
    aggregate_type: str
    aggregate_id: int
    from_sequence: Optional[int] = None


@router.post("/events/replay")
def api_replay_events(
    req: ReplayRequest,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_admin),
):
    """
    Event replay — obyektning joriy holatini event'lardan qayta tiklash.
    
    Bu funksiya:
    1. Snapshot'ni tekshiradi (tezlashtrish uchun)
    2. Keyingi event'larni qo'llaydi
    3. Joriy holatni qaytaradi
    """
    result = replay_events(
        db,
        aggregate_type=req.aggregate_type,
        aggregate_id=req.aggregate_id,
        from_sequence=req.from_sequence,
    )
    
    return result


# ================= EVENT INTEGRITY =================

class IntegrityRequest(BaseModel):
    from_sequence: int = 0
    to_sequence: Optional[int] = None


@router.post("/events/integrity")
def api_verify_integrity(
    req: IntegrityRequest,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_admin),
):
    """
    Event integrity tekshirish — chain of hashes.
    Har bir event'ning checksum'i to'g'ri ekanligini tekshiradi.
    """
    result = verify_event_integrity(
        db,
        from_seq=req.from_sequence,
        to_seq=req.to_sequence,
    )
    return result


# ================= EVENT STATISTIKASI =================

@router.get("/events/stats")
def api_event_stats(
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_admin),
):
    """
    Event store statistikasi:
    - Umumiy event soni
    - Event turlari bo'yicha
    - Aggregate'lar bo'yicha
    - So'nggi event
    - Sequence raqami
    """
    total = db.query(Event).count()
    
    # Event turlari bo'yicha
    type_stats = db.execute(text(
        "SELECT event_type, COUNT(*) as cnt FROM events GROUP BY event_type ORDER BY cnt DESC LIMIT 20"
    )).fetchall()
    
    # Aggregate turlari bo'yicha
    agg_stats = db.execute(text(
        "SELECT aggregate_type, COUNT(DISTINCT aggregate_id) as entities, COUNT(*) as events "
        "FROM events GROUP BY aggregate_type ORDER BY events DESC"
    )).fetchall()
    
    # So'nggi event
    last_event = db.query(Event).order_by(Event.id.desc()).first()
    
    # Snapshot soni
    snapshot_count = db.query(EventSnapshot).count()
    
    # Read model soni
    read_model_count = db.query(ReadModel).count()
    
    return {
        "total_events": total,
        "snapshot_count": snapshot_count,
        "read_model_count": read_model_count,
        "last_event": {
            "id": last_event.id if last_event else None,
            "sequence": last_event.sequence if last_event else None,
            "type": last_event.event_type if last_event else None,
            "occurred_at": str(last_event.occurred_at) if last_event and last_event.occurred_at else None,
        } if last_event else None,
        "event_types": [{"type": r[0], "count": r[1]} for r in type_stats],
        "aggregates": [
            {"type": r[0], "entities": r[1], "events": r[2]}
            for r in agg_stats
        ],
    }


# ================= CQRS READ MODEL =================

@router.post("/cqrs/refresh")
def api_refresh_read_models(
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_admin),
):
    """
    Read model'larni event store'dan qayta hisoblash.
    Dashboard yangilanganda chaqiriladi.
    """
    refresh_read_models(db)
    return {"status": "ok", "message": "Read model'lar yangilandi"}


@router.get("/cqrs/{model_type}")
def api_get_read_model(
    model_type: str,
    entity_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_admin),
):
    """
    Read model'dan ma'lumot olish.
    
    Misollar:
      GET /api/cqrs/dashboard_stats
      GET /api/cqrs/event_type_stats
      GET /api/cqrs/aggregate_stats
      GET /api/cqrs/hourly_events
    """
    data = get_read_model(db, model_type=model_type, entity_id=entity_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Read model '{model_type}' topilmadi")
    
    return {
        "model_type": model_type,
        "entity_id": entity_id,
        "data": data,
    }


# ================= SNAPSHOT =================

@router.get("/snapshots")
def api_list_snapshots(
    aggregate_type: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_admin),
):
    """Snapshot'lar ro'yxati"""
    q = db.query(EventSnapshot)
    if aggregate_type:
        q = q.filter(EventSnapshot.aggregate_type == aggregate_type)
    
    snapshots = q.order_by(EventSnapshot.id.desc()).limit(limit).all()
    
    return {
        "count": len(snapshots),
        "snapshots": [
            {
                "id": s.id,
                "aggregate_type": s.aggregate_type,
                "aggregate_id": s.aggregate_id,
                "last_sequence": s.last_sequence,
                "event_count": s.event_count,
                "created_at": str(s.created_at) if s.created_at else None,
            }
            for s in snapshots
        ],
    }


class SnapshotRequest(BaseModel):
    aggregate_type: str
    aggregate_id: int


@router.post("/snapshots/create")
def api_create_snapshot(
    req: SnapshotRequest,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_admin),
):
    """
    Qo'lda snapshot yaratish (avtomatik emas).
    Katta event tarixi bo'lgan obyektlar uchun foydali.
    """
    # Avval replay qilib holatni olish
    result = replay_events(db, req.aggregate_type, req.aggregate_id)
    
    if not result["state"]:
        raise HTTPException(
            status_code=404,
            detail=f"{req.aggregate_type}/{req.aggregate_id} uchun ma'lumot topilmadi",
        )
    
    # So'nggi event'ni olish
    last_event = db.query(Event).filter(
        Event.aggregate_type == req.aggregate_type,
        Event.aggregate_id == req.aggregate_id,
    ).order_by(Event.id.desc()).first()
    
    if not last_event:
        raise HTTPException(status_code=404, detail="Event topilmadi")
    
    snapshot = save_snapshot(
        db,
        aggregate_type=req.aggregate_type,
        aggregate_id=req.aggregate_id,
        state=result["state"],
        last_event_id=last_event.id,
        last_sequence=last_event.sequence,
        event_count=result["events_replayed"],
    )
    db.commit()
    
    return {
        "status": "ok",
        "snapshot_id": snapshot.id,
        "aggregate": f"{req.aggregate_type}/{req.aggregate_id}",
        "event_count": result["events_replayed"],
        "last_sequence": last_event.sequence,
    }
