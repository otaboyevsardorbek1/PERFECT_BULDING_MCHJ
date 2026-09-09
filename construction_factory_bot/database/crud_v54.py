"""
CRUD v5.4 — Yetkazib berishda transport vositasini bog'lash (TZ ERD:
deliveries.vehicle_id). Alohida modul — eski crud.py'ga halaqit bermaydi.

- create_delivery_with_vehicle: topshiriq yaratish + vehicle_id
- set_delivery_vehicle: mavjud topshiriqqa mashina tayinlash (haydovchi tanlaydi)
- delivery_with_vehicle_dict: API javobiga mashina ma'lumotini qo'shadi
"""
from typing import Dict, Optional

from sqlalchemy.orm import Session

from database import models


def _get_active_vehicle(db: Session, vehicle_id: int) -> Optional[models.Vehicle]:
    """Faol transport vositasini qaytaradi (topilmasa None)."""
    v = db.query(models.Vehicle).filter(models.Vehicle.id == vehicle_id).first()
    if not v or v.status != "faol":
        return None
    return v


def vehicle_to_label(v: models.Vehicle) -> str:
    """Mashina ko'rinishi: '01 A 123 BB (MAN TGS)'"""
    brand = f" ({v.brand})" if v.brand else ""
    return f"{v.number}{brand}"


def create_delivery_with_vehicle(db: Session, *, sale_id: int, driver_id: int,
                                 quantity: float = None, address: str = None,
                                 note: str = None, created_by: str = None,
                                 vehicle_id: int = None) -> models.Delivery:
    """Topshiriq yaratish va (berilsa) transport vositasini bog'lash.

    vehicle_id berilgan bo'lsa faol mashina bo'lishi shart, aks holda ValueError.
    """
    if vehicle_id:
        vehicle = _get_active_vehicle(db, vehicle_id)
        if not vehicle:
            raise ValueError("Transport vositasi topilmadi yoki faol emas")
    from database import crud
    d = crud.create_delivery(
        db,
        sale_id=sale_id,
        driver_id=driver_id,
        quantity=quantity,
        address=address,
        note=note,
        created_by=created_by,
    )
    if vehicle_id:
        d.vehicle_id = vehicle_id
        db.commit()
        db.refresh(d)
    return d


def set_delivery_vehicle(db: Session, delivery_id: int, vehicle_id: int) -> models.Delivery:
    """Mavjud topshiriqqa transport vositasini tayinlash (haydovchi tanlaydi)."""
    from database import crud
    d = crud.get_delivery(db, delivery_id)
    if not d:
        raise ValueError("Yetkazish topilmadi")
    if d.status in ("yetkazildi", "bekor"):
        raise ValueError("Yakunlangan yetkazishga mashina tayinlab bo'lmaydi")
    vehicle = _get_active_vehicle(db, vehicle_id)
    if not vehicle:
        raise ValueError("Transport vositasi topilmadi yoki faol emas")
    d.vehicle_id = vehicle.id
    db.commit()
    db.refresh(d)
    return d


def delivery_with_vehicle_dict(db: Session, delivery: models.Delivery) -> Dict:
    """crud.delivery_to_dict + vehicle_id/vehicle_number maydonlari."""
    from database import crud
    data = crud.delivery_to_dict(delivery)
    vehicle = None
    if delivery.vehicle_id:
        vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == delivery.vehicle_id).first()
    data["vehicle_id"] = delivery.vehicle_id
    data["vehicle_number"] = vehicle_to_label(vehicle) if vehicle else None
    return data