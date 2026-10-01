"""
REST API v5.5 — TZ 3-bo'limdagi qolgan funksional bo'shliqlar:

- 3.9  AI/ML: sotuv prognozi, mijoz segmentatsiyasi, dinamik narxlash,
       mijozga mahsulot tavsiyasi, yetkazib berish ETA
- 3.10 IoT sensorlar: o'lchov qabul qilish, buzilgan saqlash shartlari
- 3.11 Audit log: kim, qachon, nima qilgani (SystemLog asosida)
- 3.12 Feature Flags: CRUD, tekshirish, xatoda avto-o'chirish

Alohida modul — eski v3/v5 endpointlariga tegmaydi. Router tartibi:
api_v5 → api_v53 → api_v55 → api_v3 (literal yo'llar parametrli yo'llardan
oldinga ro'yxatdan o'tadi).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import crud_v55, models
from database.session import get_db
from dashboard.auth import AuthUser, get_current_user, require_any_edit
from utils.feature_flags import clear_cache

router = APIRouter(prefix="/api", tags=["v5.5"])


def require_view(modules):
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


# ================= 3.9.1 SOTUV PROGNOZI =================
@router.get("/ai/sales-forecast")
def api_sales_forecast(days: int = Query(30, ge=7, le=365),
                       product_id: Optional[int] = None,
                       category: Optional[str] = None,
                       db: Session = Depends(get_db),
                       user: AuthUser = Depends(require_view(["analytics", "finance", "reports", "admin"]))):
    """TZ 3.9: "Sotuv prognozi — keyingi hafta/oy uchun sotuv hajmini oldindan aytish."""
    return crud_v55.sales_forecast(db, days=days, product_id=product_id, category=category)


# ================= 3.9.2 MIJOZ SEGMENTATSIYASI (AI klasterlash) =================
@router.get("/ai/customer-segments")
def api_customer_segments(min_purchases: float = 0.0,
                          db: Session = Depends(get_db),
                          user: AuthUser = Depends(require_view(["crm", "analytics", "admin"]))):
    """TZ 3.9: "Mijoz segmentatsiyasi — klasterlash algoritmlari yordamida guruhlarga ajratish."""
    return crud_v55.customer_segments(db, min_purchases=min_purchases)


# ================= 3.9.3 DINAMIK NARXLASH =================
@router.get("/ai/dynamic-pricing")
def api_dynamic_pricing(product_id: Optional[int] = None,
                        db: Session = Depends(get_db),
                        user: AuthUser = Depends(require_view(["analytics", "finance", "admin"]))):
    """TZ 3.1/3.9: "Dinamik narxlash — talab, mavsum, ombor qoldig'iga qarab narxlarni optimallashtirish."""
    return crud_v55.dynamic_pricing_suggestion(db, product_id=product_id)


# ================= 3.9.4 MIJOZGA MAHSULOT TAVSIYASI =================
@router.get("/ai/recommend/{customer_id}")
def api_recommend_products(customer_id: int, limit: int = Query(5, ge=1, le=20),
                           db: Session = Depends(get_db),
                           user: AuthUser = Depends(require_view(["crm", "sales", "admin"]))):
    """TZ 3.6/3.9: "AI tavsiyalar — mijozning xarid tarixiga asoslanib mahsulot taklif qilish."""
    return crud_v55.recommend_products_for_customer(db, customer_id, limit=limit)


# ================= 3.9.5 YETKAZIB BERISH ETA =================
@router.get("/ai/delivery-eta")
def api_delivery_eta(distance_km: float = Query(10.0, ge=0.1, le=2000),
                     vehicle_id: Optional[int] = None,
                     db: Session = Depends(get_db),
                     user: AuthUser = Depends(require_view(["delivery", "analytics", "admin"]))):
    """TZ 3.9: "Yetkazib berish vaqtini bashorat qilish (AI) — aniq ETA."""
    return crud_v55.delivery_eta(db, distance_km=distance_km, vehicle_id=vehicle_id)


# ================= 3.10 IOT SENSORLAR =================
@router.get("/sensors")
def api_sensor_readings(sensor_type: Optional[str] = Query(None, pattern="^(temperature|humidity|weight|other)$"),
                        warehouse: Optional[str] = None,
                        out_of_range_only: bool = False,
                        limit: int = Query(100, ge=1, le=500),
                        db: Session = Depends(get_db),
                        user: AuthUser = Depends(require_view(["warehouse", "production", "admin"]))):
    """TZ 3.10: "Harorat/namlik sensorlari — saqlash shartlari buzilsa ogohlantirish."""
    return {"readings": crud_v55.list_sensor_readings(
        db, sensor_type=sensor_type, warehouse=warehouse,
        out_of_range_only=out_of_range_only, limit=limit)}


@router.post("/sensors")
def api_add_sensor_reading(data: dict, db: Session = Depends(get_db),
                           user: AuthUser = Depends(require_any_edit(["warehouse", "production", "admin"]))):
    """Yangi sensor o'lchovi (qo'lda yoki IoT gateway'dan)."""
    sensor_type = str(data.get("sensor_type", "")).strip()
    if sensor_type not in ("temperature", "humidity", "weight", "other"):
        raise HTTPException(400, "sensor_type: temperature|humidity|weight|other bo'lishi kerak")
    if data.get("value") is None:
        raise HTTPException(400, "value kerak (raqam)")
    try:
        value = float(data["value"])
    except (TypeError, ValueError):
        raise HTTPException(400, "value raqam bo'lishi kerak")

    reading = crud_v55.add_sensor_reading(db, {
        "sensor_type": sensor_type,
        "value": value,
        "device_name": data.get("device_name"),
        "warehouse": data.get("warehouse"),
        "unit": data.get("unit"),
        "notes": data.get("notes"),
        "recorded_by": data.get("recorded_by") or user.full_name,
    })

    # Me'yordan chiqqan o'lchov — SystemLog audit'ga yoziladi (3.11)
    if reading.is_out_of_range:
        db.add(models.SystemLog(
            user_id=user.id, user_name=user.full_name,
            action="sensor_violation", module="warehouse",
            details=f"{reading.sensor_type}={reading.value}{reading.unit or ''} "
                    f"({reading.device_name or 'sensor'}) — saqlash sharti buzildi",
        ))
        db.commit()

    return {"reading": {
        "id": reading.id,
        "sensor_type": reading.sensor_type,
        "value": reading.value,
        "unit": reading.unit,
        "is_out_of_range": reading.is_out_of_range,
    }, "alert": reading.is_out_of_range}


@router.get("/sensors/alerts")
def api_sensor_alerts(db: Session = Depends(get_db),
                      user: AuthUser = Depends(require_view(["warehouse", "production", "admin"]))):
    """Buzilgan saqlash shartlari xulosasi."""
    return crud_v55.sensor_alerts_summary(db)


# ================= 3.11 AUDIT LOG =================
@router.get("/audit-log")
def api_audit_log(module: Optional[str] = None,
                  action: Optional[str] = None,
                  limit: int = Query(200, ge=1, le=500),
                  offset: int = Query(0, ge=0),
                  db: Session = Depends(get_db),
                  user: AuthUser = Depends(require_view(["admin", "reports", "finance"]))):
    """TZ 3.11: "Audit log — kim, qachon, nima qilgani to'liq yoziladi" (faqat direktor/buxgalter)."""
    return crud_v55.audit_log(db, module=module, action=action, limit=limit, offset=offset)


# ================= 3.12 FEATURE FLAGS =================
@router.get("/feature-flags")
def api_feature_flags(db: Session = Depends(get_db),
                      user: AuthUser = Depends(require_view(["admin"]))):
    """TZ 3.12: barcha feature flags ro'yxati (direktor)."""
    flags = crud_v55.list_feature_flags(db)
    return {"flags": [{
        "id": f.id, "key": f.key, "name": f.name,
        "is_enabled": f.is_enabled,
        "rollout_percent": f.rollout_percent,
        "auto_disable_on_error": f.auto_disable_on_error,
        "error_count": f.error_count,
        "created_by": f.created_by,
        "updated_at": f.updated_at.isoformat() if f.updated_at else None,
    } for f in flags]}


@router.post("/feature-flags")
def api_create_feature_flag(data: dict, db: Session = Depends(get_db),
                            user: AuthUser = Depends(require_any_edit(["admin"]))):
    """Yangi flag yaratish: {"key": "ai_chatbot", "name": "...", "rollout_percent": 10}."""
    key = str(data.get("key", "")).strip()
    if not key:
        raise HTTPException(400, "key kerak")
    if db.query(models.FeatureFlag).filter(models.FeatureFlag.key == key).first():
        raise HTTPException(400, "Bunday flag mavjud")
    flag = crud_v55.create_feature_flag(
        db, key=key, name=data.get("name"),
        is_enabled=bool(data.get("is_enabled", False)),
        rollout_percent=int(data.get("rollout_percent", 100)),
        auto_disable_on_error=bool(data.get("auto_disable_on_error", False)),
        created_by=user.full_name,
    )
    clear_cache()
    return {"flag": {"id": flag.id, "key": flag.key, "is_enabled": flag.is_enabled,
                     "rollout_percent": flag.rollout_percent}}


@router.patch("/feature-flags/{flag_id}")
def api_update_feature_flag(flag_id: int, data: dict, db: Session = Depends(get_db),
                            user: AuthUser = Depends(require_any_edit(["admin"]))):
    """Flagni yoqish/o'chirish, rollout % o'zgartirish (TZ: "Foiz bo'yicha tarqatish")."""
    flag = crud_v55.update_feature_flag(db, flag_id, data)
    if not flag:
        raise HTTPException(404, "Flag topilmadi")
    clear_cache()
    return {"flag": {"id": flag.id, "key": flag.key, "is_enabled": flag.is_enabled,
                     "rollout_percent": flag.rollout_percent}}


@router.delete("/feature-flags/{flag_id}")
def api_delete_feature_flag(flag_id: int, db: Session = Depends(get_db),
                            user: AuthUser = Depends(require_any_edit(["admin"]))):
    if not crud_v55.delete_feature_flag(db, flag_id):
        raise HTTPException(404, "Flag topilmadi")
    clear_cache()
    return {"success": True}


@router.get("/feature-flags/{key}/check")
def api_check_feature_flag(key: str, user_seed: int = 0,
                           db: Session = Depends(get_db),
                           user: AuthUser = Depends(get_current_user)):
    """TZ 3.12: flag holatini tekshirish (har bir xodim o'z seed'i bilan)."""
    return crud_v55.is_feature_enabled(db, key, user_seed=user_seed)


@router.post("/feature-flags/{key}/error")
def api_feature_flag_error(key: str, threshold: int = Query(5, ge=1, le=100),
                           db: Session = Depends(get_db),
                           user: AuthUser = Depends(get_current_user)):
    """TZ 3.12: "Xato yuz bersa, xususiyatni avtomatik o'chirish"."""
    result = crud_v55.record_feature_error(db, key, threshold=threshold)
    clear_cache()
    if not result.get("exists"):
        raise HTTPException(404, "Flag topilmadi")
    return result
