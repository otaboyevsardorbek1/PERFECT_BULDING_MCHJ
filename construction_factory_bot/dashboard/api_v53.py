"""
REST API v5.3 — construction_factory_bot.md "TIZIM MUKAMMALLIGI" qoldiq
funksiyalari: Transport vositalari (ERD vehicles), rangli ombor xaritasi,
xodim smenasi kalendari, ochiq operatsiyalar va "Nima bo'lsa?" tahlili.

Alohida modul — eski tizimga (v3/v5) halaqit bermaydi.
(over-stock va expiring endpointlari dashboard/api_v5.py'da joylashgan.)
"""
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import models, crud_v5
from database.session import get_db
from dashboard.auth import AuthUser, get_current_user, require_any_edit

router = APIRouter(prefix="/api", tags=["v5.3"])


def require_any_view_v53(modules):
    """Kamida bitta modulni ko'rish huquqini talab qiluvchi dependency."""
    def dep(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        from config import role_can_view
        if not any(role_can_view(user.role, m) for m in modules):
            raise HTTPException(
                status_code=403,
                detail=f"Ruxsat yo'q: ({', '.join(modules)}) huquqlaridan biri kerak.",
            )
        return user
    return dep


# ================= TRANSPORT VOSITALARI (TZ ERD: vehicles) =================
@router.get("/vehicles")
def api_vehicles(status: Optional[str] = None, db: Session = Depends(get_db),
                 user: AuthUser = Depends(require_any_view_v53(["vehicles", "admin"]))):
    """TZ ERD: GET /api/vehicles — transport vositalari ro'yxati."""
    vehicles = crud_v5.list_vehicles(db, status=status)
    return {"vehicles": [crud_v5.vehicle_to_dict(v) for v in vehicles]}


@router.post("/vehicles")
def api_create_vehicle(data: dict, db: Session = Depends(get_db),
                       user: AuthUser = Depends(require_any_edit(["vehicles", "admin"]))):
    """TZ ERD: POST /api/vehicles — yangi transport vositasi (Direktor)."""
    number = str(data.get("number", "")).strip()
    if not number:
        raise HTTPException(400, "number kerak")
    if db.query(models.Vehicle).filter(models.Vehicle.number == number).first():
        raise HTTPException(400, "Bunday davlat raqami mavjud")
    v = crud_v5.create_vehicle(db, data)
    return {"vehicle": crud_v5.vehicle_to_dict(v)}


@router.put("/vehicles/{vehicle_id}")
def api_update_vehicle(vehicle_id: int, data: dict, db: Session = Depends(get_db),
                       user: AuthUser = Depends(require_any_edit(["vehicles", "admin"]))):
    """TZ ERD: PUT /api/vehicles/{id} — transport vositasini tahrirlash."""
    v = crud_v5.update_vehicle(db, vehicle_id, data)
    if not v:
        raise HTTPException(404, "Transport topilmadi")
    return {"vehicle": crud_v5.vehicle_to_dict(v)}


@router.delete("/vehicles/{vehicle_id}")
def api_delete_vehicle(vehicle_id: int, db: Session = Depends(get_db),
                       user: AuthUser = Depends(require_any_edit(["vehicles", "admin"]))):
    """TZ ERD: DELETE /api/vehicles/{id} — transport vositasini o'chirish."""
    if not crud_v5.delete_vehicle(db, vehicle_id):
        raise HTTPException(404, "Transport topilmadi")
    return {"success": True}


# ================= RANGLI OMBOR XARITASI (TZ B-bo'lim) =================
@router.get("/warehouses/fill-levels")
def api_warehouses_fill_levels(db: Session = Depends(get_db),
                               user: AuthUser = Depends(require_any_view_v53(["warehouse", "admin"]))):
    """TZ B-bo'lim: Rangli ombor xaritasi - har omborning to'liqlik darajasi.

    level: yashil (normal) / sariq (70%+) / qizil (to'la).
    """
    return {"warehouses": crud_v5.get_warehouse_fill_levels(db)}


# ================= XODIM SMENASI KALENDARI (TZ E-bo'lim) =================
@router.get("/work-schedule")
def api_work_schedule(month: Optional[str] = None, db: Session = Depends(get_db),
                      user: AuthUser = Depends(require_any_view_v53(["schedule", "admin"]))):
    """TZ E-bo'lim: Xodimlar smenasi kalendari (month=YYYY-MM)."""
    return crud_v5.get_work_schedule(db, month=month)


# ================= XODIM OCHIQ OPERATSIYALARI (TZ H-bo'lim) =================
@router.get("/employees/{employee_id}/open-operations")
def api_employee_open_operations(employee_id: int, db: Session = Depends(get_db),
                                 user: AuthUser = Depends(require_any_view_v53(["employees", "admin"]))):
    """TZ H-bo'lim: Xodim ishdan ketmoqchi - ochiq operatsiyalari ro'yxati."""
    data = crud_v5.get_employee_open_operations(db, employee_id)
    if data is None:
        raise HTTPException(404, "Xodim topilmadi")
    return data


# ================= "NIMA BO'LSA?" TAHLILI (TZ E-bo'lim) =================
@router.get("/analytics/what-if")
def api_what_if(scenario: str = Query("price_down", pattern="^(price_down|price_up|discount)$"),
                percent: float = Query(5.0, ge=0.1, le=90),
                product_id: Optional[int] = None, days: int = Query(90, ge=7, le=3650),
                db: Session = Depends(get_db),
                user: AuthUser = Depends(require_any_view_v53(["analytics", "admin"]))):
    """TZ E-bo'lim: "Nima bo'lsa?" tahlili - narx/chegirma o'zgarishi prognozi."""
    return crud_v5.what_if_analysis(db, scenario=scenario, percent=percent,
                                    product_id=product_id, days=days)