"""
REST API v3 — Node.js frontend va bot uchun JSON endpointlar
CRM (mijozlar), yetkazib beruvchilar, qabul aktlari, o'lchov birliklari,
rezervatsiya, ko'chirish, inventarizatsiya, moliya (P&L, soliq, qarz)
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import models, crud, crud_v54
from database.session import get_db
from dashboard.password_reset import (
    approve_password_reset, complete_password_reset, list_password_resets,
    reject_password_reset, request_password_reset,
)
from dashboard.auth import (
    AuthUser, PASSWORD_MIN_LENGTH, create_web_session, effective_role,
    employee_2fa_enabled, find_employee_by_phone, get_current_user, mask_customer_dict,
    refresh_session, require_any_edit, require_role, revoke_all_employee_sessions,
    revoke_session, session_to_dict, set_employee_password, touch_session,
    user_to_dict, verify_2fa_code, verify_password,
)
from config import SESSION_IDLE_MINUTES, SESSION_MINUTES, role_can_view

router = APIRouter(prefix="/api", tags=["v3"])


def require_any_view(modules):
    """Kamida bitta modulni ko'rish huquqini talab qiluvchi dependency"""
    def dep(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if not any(role_can_view(user.role, m) for m in modules):
            raise HTTPException(
                status_code=403,
                detail=f"Ruxsat yo'q: bu amal uchun ({', '.join(modules)}) huquqlaridan biri kerak.",
            )
        return user
    return dep


# =============== AVTORIZATSIYA ===============
def _token_response(data: dict, user: dict) -> dict:
    """Login/refresh javobini yagona shaklda qaytaradi"""
    return {
        "token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_in": data.get("expires_in", 0),
        "user": user,
    }


@router.post("/login")
def api_login(request: Request, data: dict, db: Session = Depends(get_db)):
    """Xodim telefoni va paroli bilan kirish -> access + refresh token.

    Muvaffaqiyatli kirishda foydalanuvchiga rol darajalari (ruxsatlar) beriladi.
    Sessiya muddati: SESSION_MINUTES (5-30 daqiqa); SESSION_IDLE_MINUTES dan uzoq
    harakatsizlik yoki logout bo'lsa barcha darajalar bekor qilinadi.
    """
    phone = str(data.get("phone", "")).strip()
    password = str(data.get("password", ""))
    if not phone or not password:
        raise HTTPException(400, "Telefon va parolni kiriting")
    employee = find_employee_by_phone(db, phone)
    if not employee or not employee.password_hash or not verify_password(password, employee.password_hash):
        raise HTTPException(401, "Telefon yoki parol noto'g'ri")
    # 2FA (Google Authenticator): parol to'g'ri bo'lsa ham kod talab qilinadi
    if employee_2fa_enabled(employee):
        otp_code = str(data.get("otp_code", "")).strip()
        if not otp_code:
            raise HTTPException(428, "Google Authenticator kodini kiriting (otp_code)")
        if not verify_2fa_code(employee, otp_code):
            raise HTTPException(401, "Google Authenticator kodi noto'g'ri")
    token_data = create_web_session(
        db, employee,
        user_agent=request.headers.get("user-agent", "") or "",
    )
    try:
        crud.create_system_log(db, user_id=employee.telegram_id,
                               user_name=employee.full_name,
                               action="Web dashboardga kirish (login)",
                               module="security")
    except Exception:
        pass
    return _token_response(token_data, user_to_dict(employee))


@router.post("/refresh")
def api_refresh(data: dict, db: Session = Depends(get_db)):
    """Refresh token bilan yangi access token olish (sliding sessiya)"""
    refresh_token = str(data.get("refresh_token", ""))
    token_data = refresh_session(db, refresh_token)
    if token_data is None:
        raise HTTPException(401, "Refresh token yaroqsiz yoki muddati o'tgan")
    employee = db.query(models.Employee).filter(
        models.Employee.id == token_data["session"].employee_id
    ).first()
    if not employee:
        raise HTTPException(401, "Xodim topilmadi")
    return _token_response(token_data, user_to_dict(employee))


@router.post("/logout")
def api_logout(request: Request, data: dict = None, db: Session = Depends(get_db)):
    """Sessiyani revoke qiladi — o'sha sessiyaga berilgan barcha darajalar bekor bo'ladi.

    Sessiya o'lganda access token ham refresh token ham ishlamay qoladi:
    keyingi so'rov 401 qaytaradi va foydalanuvchi qayta login qiladi.
    """
    data = data or {}
    refresh_token = str(data.get("refresh_token", ""))
    # 1) Refresh token berilgan bo'lsa shu sessiyani revoke qilamiz
    if refresh_token:
        revoke_session(db, refresh_token=refresh_token, reason="logout")
        return {"success": True}
    # 2) Bo'lmasa access token'dagi sid orqali revoke qilamiz
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        from dashboard.auth import decode_token
        payload = decode_token(auth[7:].strip())
        if payload and payload.get("sid") is not None:
            revoke_session(db, session_id=payload["sid"], reason="logout")
            return {"success": True}
    raise HTTPException(401, "Token topilmadi")


# =============== 2FA (Google Authenticator) BOSHQARISH ===============
@router.post("/auth/2fa/setup")
def api_2fa_setup(user: AuthUser = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """Yangi TOTP secret + QR kod yaratadi (hali yoqilmagan — faqat tayyorlanadi).

    Direktor/kassir o'z hisobida 2FA'ni yoqishni boshlaganda ishlatiladi.
    Kod verify qilinmaguncha otp_enabled=False bo'ladi.
    """
    from utils.totp import generate_secret, provisioning_uri, qr_data_url
    employee = db.query(models.Employee).filter(models.Employee.id == user.id).first()
    if employee is None:
        raise HTTPException(404, "Xodim topilmadi")
    secret = generate_secret()
    employee.otp_secret = secret
    employee.otp_enabled = False
    db.commit()
    return {
        "secret": secret,
        "provisioning_uri": provisioning_uri(secret, employee.full_name),
        "qr_data_url": qr_data_url(secret, employee.full_name),
        "enabled": False,
    }


@router.post("/auth/2fa/enable")
def api_2fa_enable(data: dict, user: AuthUser = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """Tayyorlangan secret'ni kod bilan tasdiqlab 2FA'ni yoqadi"""
    employee = db.query(models.Employee).filter(models.Employee.id == user.id).first()
    if employee is None:
        raise HTTPException(404, "Xodim topilmadi")
    if not getattr(employee, "otp_secret", None):
        raise HTTPException(400, "Avval /auth/2fa/setup chaqiring")
    if employee_2fa_enabled(employee):
        return {"enabled": True, "message": "2FA allaqachon yoqilgan"}
    code = str(data.get("code", "")).strip()
    if not code:
        raise HTTPException(400, "Google Authenticator kodini kiriting")
    from utils.totp import verify_totp
    if not verify_totp(employee.otp_secret, code):
        raise HTTPException(400, "Kod noto'g'ri — Google Authenticator'dagi joriy 6 xonali kodni kiriting")
    employee.otp_enabled = True
    db.commit()
    try:
        crud.create_system_log(db, user_id=user.telegram_id, user_name=user.full_name,
                               action="2FA yoqildi (Google Authenticator)", module="security")
    except Exception:
        pass
    return {"enabled": True}


@router.post("/auth/2fa/disable")
def api_2fa_disable(data: dict, user: AuthUser = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """2FA'ni o'chirish — joriy kodni so'rab, keyin secret'ni tozalaydi"""
    employee = db.query(models.Employee).filter(models.Employee.id == user.id).first()
    if employee is None:
        raise HTTPException(404, "Xodim topilmadi")
    if not employee_2fa_enabled(employee):
        return {"enabled": False, "message": "2FA o'chirilgan"}
    code = str(data.get("code", "")).strip()
    if not code:
        raise HTTPException(400, "Google Authenticator kodini kiriting")
    if not verify_2fa_code(employee, code):
        raise HTTPException(400, "Kod noto'g'ri")
    employee.otp_secret = None
    employee.otp_enabled = False
    # Xavfsizlik: 2FA o'chirilgach barcha sessiyalarni yangilash talab qilamiz
    try:
        revoke_all_employee_sessions(db, employee.id, reason="2fa_disabled")
    except Exception:
        db.rollback()
    db.commit()
    try:
        crud.create_system_log(db, user_id=user.telegram_id, user_name=user.full_name,
                               action="2FA o'chirildi", module="security")
    except Exception:
        pass
    return {"enabled": False}


@router.get("/me")
def api_me(request: Request, db: Session = Depends(get_db),
           user: AuthUser = Depends(get_current_user)):
    """Joriy foydalanuvchi profili, ruxsatlari (berilgan darajalar) va sessiya holati"""
    result = {"user": user.to_dict()}
    # Sessiya holati: muddat va harakatsizlik taymeri UI avto-logout uchun ishlatiladi
    auth = request.headers.get("authorization", "")
    sid = None
    if auth.lower().startswith("bearer "):
        from dashboard.auth import decode_token
        payload = decode_token(auth[7:].strip())
        if payload:
            sid = payload.get("sid")
    if sid is not None:
        ws = db.query(models.WebSession).filter(models.WebSession.id == sid).first()
        if ws is not None:
            result["session"] = session_to_dict(ws)
    result["session_policy"] = {
        "access_ttl_seconds": SESSION_MINUTES * 60,
        "idle_timeout_seconds": SESSION_IDLE_MINUTES * 60,
    }
    return result


@router.post("/roles/{employee_id}/password")
def api_set_employee_password(employee_id: int, data: dict,
                             db: Session = Depends(get_db),
                             actor: AuthUser = Depends(require_role("admin", edit=True))):
    """Xodim web-parolini o'rnatish (faqat admin/direktor)"""
    employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(404, "Xodim topilmadi")
    password = str(data.get("password", ""))
    try:
        set_employee_password(db, employee, password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        crud.create_system_log(db, user_id=actor.telegram_id,
                               user_name=actor.full_name,
                               action=f"Web parol o'rnatildi: {employee.full_name}",
                               module="admin")
    except Exception:
        pass
    return {"success": True}


# =============== BOT SESSIYALARI BOSHQARUVI (v4) ===============
@router.get("/bot-sessions")
def api_bot_sessions(db: Session = Depends(get_db),
                     limit: int = Query(100, le=500),
                     actor: AuthUser = Depends(require_role("admin", edit=False))):
    """Xodimlarning bot sessiyalari ro'yxati (faqat admin/direktor).

    TZ xavfsizlik: direktor kim qachon login qilgani, sessiya qolgan vaqti
    va sessiya qanday tugaganini (logout/idle/expired) kuzatadi.
    """
    from utils.bot_auth import session_to_dict as bot_session_to_dict

    sessions = db.query(models.EmployeeAuthSession).order_by(
        models.EmployeeAuthSession.created_at.desc()
    ).limit(limit).all()

    result = []
    for s in sessions:
        info = bot_session_to_dict(s)
        emp = db.query(models.Employee).filter(models.Employee.id == s.employee_id).first()
        info["employee_name"] = emp.full_name if emp else "?"
        result.append(info)
    return {"sessions": result, "count": len(result)}


@router.get("/bot-sessions/policy")
def api_bot_sessions_policy(actor: AuthUser = Depends(require_role("admin", edit=False))):
    """Bot sessiya siyosati (TZ: 5-30 daqiqa sessiya, idle timeout, blok qoidalari)"""
    from config import (
        BOT_AUTH_ENABLED, BOT_SESSION_MINUTES, BOT_SESSION_IDLE_MINUTES,
        BOT_LOGIN_MAX_ATTEMPTS, BOT_LOGIN_LOCKOUT_MINUTES,
    )
    return {
        "auth_enabled": BOT_AUTH_ENABLED,
        "session_minutes": BOT_SESSION_MINUTES,
        "idle_timeout_minutes": BOT_SESSION_IDLE_MINUTES,
        "max_login_attempts": BOT_LOGIN_MAX_ATTEMPTS,
        "lockout_minutes": BOT_LOGIN_LOCKOUT_MINUTES,
    }


@router.post("/bot-sessions/revoke")
def api_revoke_bot_sessions(data: dict, db: Session = Depends(get_db),
                            actor: AuthUser = Depends(require_role("admin", edit=True))):
    """Xodimning barcha faol bot sessiyalarini bekor qilish (darajalarni olib tashlash).

    Body: {"employee_id": 5} yoki {"telegram_id": 123456789}
    """
    from utils.bot_auth import (
        revoke_all_employee_bot_sessions,
        revoke_employee_bot_sessions_by_telegram_id,
    )

    employee_id = data.get("employee_id")
    telegram_id = data.get("telegram_id")
    if employee_id is None and telegram_id is None:
        raise HTTPException(400, "employee_id yoki telegram_id kerak")

    if employee_id is not None:
        revoked = revoke_all_employee_bot_sessions(db, int(employee_id), reason="admin")
        emp = db.query(models.Employee).filter(models.Employee.id == int(employee_id)).first()
        name = emp.full_name if emp else str(employee_id)
    else:
        revoked = revoke_employee_bot_sessions_by_telegram_id(db, int(telegram_id), reason="admin")
        emp = db.query(models.Employee).filter(
            models.Employee.telegram_id == int(telegram_id)
        ).first()
        name = emp.full_name if emp else str(telegram_id)

    try:
        crud.create_system_log(db, user_id=actor.telegram_id, user_name=actor.full_name,
                               action=f"Bot sessiyalari bekor qilindi: {name} ({revoked} ta)",
                               module="admin")
    except Exception:
        pass
    return {"success": True, "revoked": revoked, "employee": name}


# =============== MIJOZLAR (CRM) ===============
@router.get("/customers")
def api_customers(db: Session = Depends(get_db),
                  q: Optional[str] = None,
                  skip: int = 0, limit: int = 100,
                  user: AuthUser = Depends(require_role("crm"))):
    try:
        if q:
            customers = crud.search_customers(db, q, limit=limit)
        else:
            customers = crud.list_customers(db, skip=skip, limit=limit)
        return {"customers": [
            mask_customer_dict(crud.customer_to_dict(db, c), user)
            for c in customers
        ]}
    except Exception as e:
        return {"error": str(e), "customers": []}


@router.get("/customers/segmentation")
def api_customer_segmentation(db: Session = Depends(get_db),
                              user: AuthUser = Depends(require_role("crm"))):
    """Mijoz triaji — Oltin/Kumush/Bronza segmentatsiya statistikasi (TZ)"""
    try:
        seg = crud.get_customer_segmentation(db)
        # Har bir toifadagi mijozlar ro'yxati (qisqacha)
        tiers = {}
        for tier in ("gold", "silver", "bronze"):
            tiers[tier] = [
                {"id": c.id, "name": c.name,
                 "total_purchases": c.total_purchases or 0,
                 "total_debt": c.total_debt or 0}
                for c in crud.list_customers_by_tier(db, tier, limit=20)
            ]
        return {"segmentation": seg, "tiers": tiers}
    except Exception as e:
        return {"error": str(e), "segmentation": {"total": 0}}


@router.post("/customers")
def api_create_customer(data: dict, db: Session = Depends(get_db),
                        user: AuthUser = Depends(require_role("crm", edit=True))):
    try:
        allowed = {c.name for c in models.Customer.__table__.columns}
        payload = {k: v for k, v in data.items() if k in allowed}
        customer = crud.create_customer(db, payload)
        crud.create_system_log(db, action="API: mijoz qo'shildi",
                               details=customer.name, module="crm")
        return {"customer": mask_customer_dict(crud.customer_to_dict(db, customer), user)}
    except Exception as e:
        return {"error": str(e)}


@router.get("/customers/{customer_id}")
def api_customer(customer_id: int, db: Session = Depends(get_db),
                 user: AuthUser = Depends(require_role("crm"))):
    c = crud.get_customer(db, customer_id)
    if not c:
        raise HTTPException(404, "Mijoz topilmadi")
    sales = db.query(models.Sale).filter(models.Sale.customer_id == customer_id).order_by(
        models.Sale.sale_date.desc()
    ).limit(20).all()
    payments = db.query(models.Payment).filter(models.Payment.customer_id == customer_id).order_by(
        models.Payment.created_at.desc()
    ).limit(20).all()
    return {
        "customer": mask_customer_dict(crud.customer_to_dict(db, c), user),
        "sales": [{
            "id": s.id, "invoice_number": s.invoice_number,
            "total_amount": s.total_amount, "paid_amount": s.paid_amount,
            "is_credit": s.is_credit, "credit_status": s.credit_status,
            "payment_method": s.payment_method,
            "sale_date": s.sale_date.isoformat() if s.sale_date else None,
            "due_date": s.due_date.isoformat() if s.due_date else None,
        } for s in sales],
        "payments": [{
            "id": p.id, "amount": p.amount, "method": p.method,
            "payment_type": p.payment_type, "note": p.note,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        } for p in payments],
    }


@router.post("/customers/{customer_id}/pay")
def api_pay_debt(customer_id: int, data: dict, db: Session = Depends(get_db),
                 user: AuthUser = Depends(require_any_edit(["crm", "finance"]))):
    try:
        amount = float(data.get("amount", 0))
        method = data.get("method", "cash")
        result = crud.pay_customer_debt(
            db, customer_id, amount, method=method,
            note=data.get("note"), created_by=data.get("created_by", "API"),
        )
        if result is None:
            raise HTTPException(404, "Mijoz topilmadi")
        return {"success": True, **result}
    except HTTPException:
        raise
    except Exception as e:
        return {"error": str(e)}


# =============== YETKAZIB BERUVCHILAR ===============
@router.get("/suppliers")
def api_suppliers(db: Session = Depends(get_db),
                   user: AuthUser = Depends(require_role("supplier"))):
    try:
        return {"suppliers": [crud.supplier_to_dict(s) for s in crud.list_suppliers(db)]}
    except Exception as e:
        return {"error": str(e), "suppliers": []}


@router.post("/suppliers")
def api_create_supplier(data: dict, db: Session = Depends(get_db),
                        user: AuthUser = Depends(require_role("supplier", edit=True))):
    try:
        allowed = {c.name for c in models.Supplier.__table__.columns}
        payload = {k: v for k, v in data.items() if k in allowed}
        supplier = crud.create_supplier(db, payload)
        return {"supplier": crud.supplier_to_dict(supplier)}
    except Exception as e:
        return {"error": str(e)}


@router.get("/suppliers/reorder-suggestions")
def api_reorder_suggestions(db: Session = Depends(get_db),
                             user: AuthUser = Depends(require_role("supplier"))):
    try:
        return {"suggestions": crud.get_supplier_reorder_suggestions(db)}
    except Exception as e:
        return {"error": str(e), "suggestions": []}


@router.get("/receipts")
def api_receipts(db: Session = Depends(get_db), limit: int = 100,
                 user: AuthUser = Depends(require_role("supplier"))):
    try:
        receipts = db.query(models.SupplierDelivery).order_by(
            models.SupplierDelivery.created_at.desc()
        ).limit(limit).all()
        return {"receipts": [{
            "id": r.id, "act_number": r.act_number,
            "supplier_id": r.supplier_id,
            "supplier_name": r.supplier.name if r.supplier else "?",
            "raw_material_id": r.raw_material_id,
            "material_name": r.raw_material.name if r.raw_material else "?",
            "quantity_ordered": r.quantity_ordered,
            "quantity_received": r.quantity_received,
            "quality_status": r.quality_status,
            "price_per_unit": r.price_per_unit,
            "deficiency_amount": r.deficiency_amount,
            "batch_number": r.raw_material.batch_number if r.raw_material else None,
            "certificate_number": r.raw_material.certificate_number if r.raw_material else None,
            "expiry_date": r.raw_material.expiry_date.isoformat() if r.raw_material and r.raw_material.expiry_date else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in receipts]}
    except Exception as e:
        return {"error": str(e), "receipts": []}


@router.post("/receipts")
def api_create_receipt(data: dict, db: Session = Depends(get_db),
                       user: AuthUser = Depends(require_role("supplier", edit=True))):
    try:
        delivery = crud.create_supplier_delivery(
            db,
            supplier_id=int(data["supplier_id"]),
            raw_material_id=int(data["raw_material_id"]),
            quantity_ordered=float(data["quantity_ordered"]),
            quantity_received=float(data.get("quantity_received", data["quantity_ordered"])),
            quality_status=data.get("quality_status", "qabul_qilingan"),
            price_per_unit=float(data.get("price_per_unit", 0)),
            notes=data.get("notes"),
            created_by=data.get("created_by", "API"),
            batch_number=data.get("batch_number"),
            certificate_number=data.get("certificate_number"),
            expiry_date=data.get("expiry_date"),
        )
        return {"receipt": {
            "id": delivery.id, "act_number": delivery.act_number,
            "deficiency_amount": delivery.deficiency_amount,
        }}
    except Exception as e:
        return {"error": str(e)}


# =============== O'LCHOV BIRLIKLARI / KONVERTATSIYA ===============
@router.get("/products/{product_id}/units")
def api_product_units(product_id: int, db: Session = Depends(get_db),
                      user: AuthUser = Depends(require_role("production"))):
    try:
        units = crud.get_product_units(db, product_id)
        product = db.query(models.Product).filter(models.Product.id == product_id).first()
        base = product.unit if product else None
        data = [{"id": u.id, "unit": u.unit, "factor": u.factor,
                 "base_unit": u.base_unit, "price": u.price} for u in units]
        return {"product_id": product_id, "base_unit": base, "units": data}
    except Exception as e:
        return {"error": str(e), "units": []}


@router.post("/products/{product_id}/units")
def api_add_product_unit(product_id: int, data: dict, db: Session = Depends(get_db),
                         user: AuthUser = Depends(require_role("production", edit=True))):
    try:
        pu = crud.add_product_unit(
            db, product_id,
            unit=data["unit"],
            factor=float(data["factor"]),
            base_unit=data.get("base_unit", "dona"),
            price=float(data["price"]) if data.get("price") else None,
        )
        return {"unit": {"id": pu.id, "unit": pu.unit, "factor": pu.factor,
                         "base_unit": pu.base_unit, "price": pu.price}}
    except Exception as e:
        return {"error": str(e)}


@router.get("/convert")
def api_convert(product_id: int, from_unit: str, to_unit: str,
                quantity: float, db: Session = Depends(get_db),
                user: AuthUser = Depends(require_role("production"))):
    result = crud.convert_quantity(db, product_id, from_unit, quantity, to_unit)
    if not result:
        raise HTTPException(404, "Mahsulot topilmadi")
    return result


# =============== O'XSHASH MAHSULOT TAKLIFI (TZ: cross-sell) ===============
@router.get("/products/{product_id}/related")
def api_related_products(product_id: int, db: Session = Depends(get_db),
                         user: AuthUser = Depends(require_role("production"))):
    """
    Tanlangan mahsulotga o'xshash (bir xil kategoriya, omborda bor) mahsulotlar.
    TZ: "Mijoz g'isht sotib olsa, tizim bu g'ishtga mos sement va armatura"ni
    tavsiya qiladi — o'rtacha chek oshadi.
    """
    try:
        related = crud.get_related_products(db, product_id, limit=5)
        items = []
        for p in related:
            items.append({
                "id": p.id,
                "name": p.name,
                "category": p.category,
                "unit": p.unit,
                "selling_price": p.selling_price,
                "available_qty": crud.get_available_product_qty(db, p.id) or 0,
            })
        return {"product_id": product_id, "related": items}
    except Exception as e:
        return {"error": str(e), "related": []}


# =============== REZERVATSIYA ===============
@router.get("/reservations")
def api_reservations(db: Session = Depends(get_db),
                     user: AuthUser = Depends(require_role("stock_ops"))):
    try:
        reservations = crud.list_active_reservations(db)
        return {"reservations": [{
            "id": r.id, "reservation_code": r.reservation_code,
            "product_id": r.product_id,
            "product_name": r.product.name if r.product else "?",
            "quantity": r.quantity,
            "customer_name": r.customer_name,
            "customer_phone": r.customer_phone,
            "status": r.status,
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
        } for r in reservations]}
    except Exception as e:
        return {"error": str(e), "reservations": []}


@router.post("/reservations")
def api_create_reservation(data: dict, db: Session = Depends(get_db),
                           user: AuthUser = Depends(require_role("stock_ops", edit=True))):
    try:
        result = crud.create_reservation(
            db,
            product_id=int(data["product_id"]),
            quantity=float(data["quantity"]),
            expires_in_hours=float(data.get("expires_in_hours", 2)),
            customer_id=data.get("customer_id"),
            customer_name=data.get("customer_name"),
            customer_phone=data.get("customer_phone"),
            notes=data.get("notes"),
            created_by=data.get("created_by", "API"),
        )
        if "error" in result:
            raise HTTPException(400, result["error"])
        r = result["reservation"]
        return {"reservation": {
            "id": r.id, "reservation_code": r.reservation_code,
            "quantity": r.quantity, "status": r.status,
            "expires_at": r.expires_at.isoformat(),
        }}
    except HTTPException:
        raise
    except Exception as e:
        return {"error": str(e)}


@router.post("/reservations/{reservation_id}/cancel")
def api_cancel_reservation(reservation_id: int, db: Session = Depends(get_db),
                           user: AuthUser = Depends(require_role("stock_ops", edit=True))):
    if not crud.cancel_reservation(db, reservation_id):
        raise HTTPException(404, "Rezervatsiya topilmadi")
    return {"success": True}


@router.post("/reservations/{reservation_id}/complete")
def api_complete_reservation(reservation_id: int, db: Session = Depends(get_db),
                             user: AuthUser = Depends(require_role("stock_ops", edit=True))):
    if not crud.complete_reservation(db, reservation_id):
        raise HTTPException(404, "Rezervatsiya topilmadi yoki faol emas")
    return {"success": True}


# =============== KO'CHIRISH ===============
@router.get("/transfers")
def api_transfers(db: Session = Depends(get_db),
                  user: AuthUser = Depends(require_role("stock_ops"))):
    try:
        transfers = crud.list_transfers(db)
        return {"transfers": [{
            "id": t.id, "source": t.source_warehouse, "target": t.target_warehouse,
            "product_id": t.product_id, "raw_material_id": t.raw_material_id,
            "quantity": t.quantity,
            "name": (t.product.name if t.product else
                     (t.raw_material.name if t.raw_material else "?")),
            "user_name": t.user_name, "notes": t.notes,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        } for t in transfers]}
    except Exception as e:
        return {"error": str(e), "transfers": []}


@router.post("/transfers")
def api_create_transfer(data: dict, db: Session = Depends(get_db),
                        user: AuthUser = Depends(require_role("stock_ops", edit=True))):
    try:
        result = crud.create_transfer(
            db,
            item_type=data["item_type"], item_id=int(data["item_id"]),
            quantity=float(data["quantity"]),
            source_warehouse=data["source_warehouse"],
            target_warehouse=data["target_warehouse"],
            notes=data.get("notes"),
            user_id=data.get("user_id", 0),
            user_name=data.get("user_name", "API"),
        )
        if "error" in result:
            raise HTTPException(400, result["error"])
        return {"success": True, "transfer_id": result["transfer"].id}
    except HTTPException:
        raise
    except Exception as e:
        return {"error": str(e)}


# =============== INVENTARIZATSIYA ===============
@router.get("/inventory-checks")
def api_inventory_checks(db: Session = Depends(get_db),
                         user: AuthUser = Depends(require_role("stock_ops"))):
    try:
        checks = crud.list_inventory_checks(db)
        return {"checks": [{
            "id": c.id, "check_number": c.check_number, "warehouse": c.warehouse,
            "raw_material_id": c.raw_material_id, "product_id": c.product_id,
            "name": (c.raw_material.name if c.raw_material else
                     (c.product.name if c.product else "?")),
            "system_quantity": c.system_quantity,
            "actual_quantity": c.actual_quantity,
            "difference": c.difference, "reason": c.reason,
            "act_created": c.act_created,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        } for c in checks]}
    except Exception as e:
        return {"error": str(e), "checks": []}


@router.post("/inventory-checks")
def api_create_inventory_check(data: dict, db: Session = Depends(get_db),
                               user: AuthUser = Depends(require_role("stock_ops", edit=True))):
    try:
        check = crud.create_inventory_check(
            db,
            warehouse=data.get("warehouse", "asosiy"),
            item_type=data["item_type"],
            item_id=int(data["item_id"]),
            actual_quantity=float(data["actual_quantity"]),
            reason=data.get("reason"),
            notes=data.get("notes"),
            created_by=data.get("created_by", "API"),
        )
        return {"check": {
            "id": check.id, "check_number": check.check_number,
            "system_quantity": check.system_quantity,
            "actual_quantity": check.actual_quantity,
            "difference": check.difference,
            "act_created": check.act_created,
        }}
    except Exception as e:
        return {"error": str(e)}


# =============== MOLIYA ===============
def _parse_period(start: Optional[str], end: Optional[str]):
    today = datetime.utcnow().date()
    if end:
        end_d = datetime.fromisoformat(end).date()
    else:
        end_d = today
    if start:
        start_d = datetime.fromisoformat(start).date()
    else:
        start_d = end_d.replace(day=1)  # oy boshi
    return start_d, end_d


@router.get("/finance/pl")
def api_pl(start: Optional[str] = None, end: Optional[str] = None,
           db: Session = Depends(get_db),
           user: AuthUser = Depends(require_role("finance"))):
    try:
        start_d, end_d = _parse_period(start, end)
        return {"report": crud.get_pl_report(db, start_d, end_d)}
    except Exception as e:
        return {"error": str(e)}


@router.get("/finance/tax")
def api_tax(amount: float = Query(0), rate: float = Query(12),
            start: Optional[str] = None, end: Optional[str] = None,
            db: Session = Depends(get_db),
            user: AuthUser = Depends(require_role("finance"))):
    try:
        if not amount and start:
            start_d, end_d = _parse_period(start, end)
            amount = crud.get_pl_report(db, start_d, end_d)["revenue"]
        return {"tax": crud.calculate_tax(amount, rate)}
    except Exception as e:
        return {"error": str(e)}


@router.get("/finance/debts")
def api_debts(db: Session = Depends(get_db),
              user: AuthUser = Depends(require_role("finance"))):
    try:
        report = crud.get_customer_debts_report(db)
        credit_sales = crud.get_credit_sales(db, limit=100)
        report["credit_sales"] = [{
            "id": s.id, "invoice_number": s.invoice_number,
            "customer_name": s.customer_name,
            "total_amount": s.total_amount, "paid_amount": s.paid_amount,
            "remaining": (s.total_amount or 0) - (s.paid_amount or 0),
            "credit_status": s.credit_status,
            "due_date": s.due_date.isoformat() if s.due_date else None,
        } for s in credit_sales]
        return report
    except Exception as e:
        return {"error": str(e)}


# =============== PAROL TIKLASH (self-service: so'rov -> admin tasdig'i) ===============
@router.post("/password-reset/request")
def api_password_reset_request(data: dict, db: Session = Depends(get_db)):
    """Xodim parol tiklash so'rovini beradi (auth shart emas — parol unutilgan)"""
    try:
        result = request_password_reset(
            db, str(data.get("phone", "")), reason=str(data.get("reason", ""))
        )
        if not result.get("success"):
            raise HTTPException(400, result.get("error", "So'rov yuborilmadi"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        return {"error": str(e)}


@router.post("/password-reset/complete")
def api_password_reset_complete(data: dict, db: Session = Depends(get_db)):
    """Kodni kiritib, yangi parol o'rnatadi (auth shart emas)"""
    try:
        result = complete_password_reset(
            db,
            phone_number=str(data.get("phone", "")),
            code=str(data.get("code", "")),
            new_password=str(data.get("new_password", "")),
        )
        if not result.get("success"):
            raise HTTPException(400, result.get("error", "Parol o'rnatilmadi"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        return {"error": str(e)}


@router.get("/password-reset/requests")
def api_password_reset_requests(db: Session = Depends(get_db),
                                include_done: bool = False,
                                user: AuthUser = Depends(require_role("admin"))):
    """Parol tiklash so'rovlari ro'yxati (faqat admin/direktor)"""
    try:
        return {"requests": list_password_resets(db, include_done=include_done)}
    except Exception as e:
        return {"error": str(e), "requests": []}


@router.post("/password-reset/{reset_id}/approve")
def api_password_reset_approve(reset_id: int, db: Session = Depends(get_db),
                               user: AuthUser = Depends(require_role("admin", edit=True))):
    """So'rovni tasdiqlaydi -> bir martalik kod qaytaradi (admin ko'radi)"""
    result = approve_password_reset(db, reset_id, reviewer_id=user.id)
    if not result.get("success"):
        raise HTTPException(400, result.get("error", "Tasdiqlanmadi"))
    try:
        crud.create_system_log(db, user_id=user.telegram_id, user_name=user.full_name,
                               action=f"Parol tiklash tasdiqlandi (so'rov #{reset_id})",
                               module="admin")
    except Exception:
        pass
    return result


@router.post("/password-reset/{reset_id}/reject")
def api_password_reset_reject(reset_id: int, db: Session = Depends(get_db),
                              user: AuthUser = Depends(require_role("admin", edit=True))):
    """So'rovni rad etadi (xodim qayta so'rashi mumkin)"""
    result = reject_password_reset(db, reset_id, reviewer_id=user.id)
    if not result.get("success"):
        raise HTTPException(400, result.get("error", "Rad etilmadi"))
    try:
        crud.create_system_log(db, user_id=user.telegram_id, user_name=user.full_name,
                               action=f"Parol tiklash rad etildi (so'rov #{reset_id})",
                               module="admin")
    except Exception:
        pass
    return result


# =============== ROLLAR ===============
@router.get("/roles")
def api_roles(db: Session = Depends(get_db),
              user: AuthUser = Depends(require_role("admin"))):
    try:
        employees = db.query(models.Employee).order_by(models.Employee.full_name).all()
        return {"roles": [{
            "id": e.id, "full_name": e.full_name,
            "role": effective_role(e),
            "phone_number": e.phone_number,
            "is_admin": e.is_admin,
            "has_password": bool(e.password_hash),
            "telegram_id": e.telegram_id,
        } for e in employees]}
    except Exception as e:
        return {"error": str(e), "roles": []}


# =============== ONLAYN TO'LOVLAR (Click / Payme) ===============
@router.post("/payments/invoice")
def api_create_payment_invoice(data: dict, db: Session = Depends(get_db),
                               user: AuthUser = Depends(require_any_edit(["crm", "finance"]))):
    """Mijoz qarzi uchun onlayn to'lov schyot-fakturasi yaratish -> Click/Payme havolasi"""
    try:
        from dashboard.payments import create_payment_invoice, build_payment_links, invoice_to_dict

        gateway = str(data.get("gateway", "click")).lower()
        amount = float(data.get("amount", 0))
        customer_id = data.get("customer_id")
        customer = crud.get_customer(db, customer_id) if customer_id else None
        invoice = create_payment_invoice(
            db, gateway=gateway, amount=amount,
            customer_id=customer.id if customer else None,
            customer_name=customer.name if customer else data.get("customer_name"),
            note=data.get("note"),
        )
        links = build_payment_links(invoice)
        return {"invoice": invoice_to_dict(invoice), "links": links}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        return {"error": str(e)}


@router.get("/payments/invoices")
def api_payment_invoices(db: Session = Depends(get_db),
                         status: Optional[str] = None, limit: int = 100,
                         user: AuthUser = Depends(require_role("finance"))):
    """Onlayn to'lov schyot-fakturalari ro'yxati"""
    try:
        from dashboard.payments import invoice_to_dict
        q = db.query(models.PaymentInvoice).order_by(
            models.PaymentInvoice.created_at.desc()
        ).limit(limit)
        if status:
            q = q.filter(models.PaymentInvoice.status == status)
        return {"invoices": [invoice_to_dict(i) for i in q.all()]}
    except Exception as e:
        return {"error": str(e), "invoices": []}


# =============== WEB-DO'KON BUYURTMALARI (boshqaruv) ===============
@router.get("/shop-orders")
def api_shop_orders(db: Session = Depends(get_db), status: Optional[str] = None,
                    limit: int = 50,
                    user: AuthUser = Depends(require_any_view(["finance", "admin"]))):
    """Do'kon buyurtmalari ro'yxati (buxgalter/direktor)"""
    try:
        orders = crud.list_shop_orders(db, status=status, limit=limit)
        return {"orders": [crud.shop_order_to_dict(o) for o in orders]}
    except Exception as e:
        return {"error": str(e), "orders": []}


@router.post("/shop-orders/{order_id}/cancel")
def api_cancel_shop_order(order_id: int, db: Session = Depends(get_db),
                          user: AuthUser = Depends(require_role("admin", edit=True))):
    """Do'kon buyurtmasini bekor qilish (faqat direktor/admin)"""
    try:
        order = crud.cancel_shop_order(db, order_id)
        return {"order": crud.shop_order_to_dict(order)}
    except ValueError as e:
        raise HTTPException(400, str(e))


# =============== KASSIR SMENASI (cash shift) ===============
@router.get("/cash-shifts")
def api_cash_shifts(db: Session = Depends(get_db), status: Optional[str] = None,
                    limit: int = 50,
                    user: AuthUser = Depends(require_any_view(["cash_shift", "finance", "admin"]))):
    """Smenalar ro'yxati (kassir/buxgalter/direktor)"""
    try:
        shifts = crud.list_cash_shifts(db, status=status, limit=limit)
        return {"shifts": [crud.cash_shift_to_dict(s) for s in shifts]}
    except Exception as e:
        return {"error": str(e), "shifts": []}


@router.get("/cash-shifts/current")
def api_cash_shift_current(db: Session = Depends(get_db),
                           user: AuthUser = Depends(require_any_view(["cash_shift", "finance", "admin"]))):
    """Joriy ochiq smena + kutilgan naqd hisob"""
    shift = crud.get_open_cash_shift(db)
    if not shift:
        return {"shift": None}
    summary = crud.cash_shift_summary(db, shift)
    return {"shift": crud.cash_shift_to_dict(shift), "summary": summary}


@router.post("/cash-shifts/open")
def api_cash_shift_open(data: dict, db: Session = Depends(get_db),
                        user: AuthUser = Depends(require_role("cash_shift", edit=True))):
    """Smena boshlash (joriy foydalanuvchi kassir sifatida)"""
    try:
        employee = db.query(models.Employee).filter(models.Employee.id == user.id).first()
        shift = crud.create_cash_shift(
            db,
            employee_id=user.id if employee else None,
            employee_name=employee.full_name if employee else user.full_name,
            opening_balance=float(data.get("opening_balance", 0)),
            note=data.get("note"),
        )
        return {"shift": crud.cash_shift_to_dict(shift)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/cash-shifts/{shift_id}/close")
def api_cash_shift_close(shift_id: int, data: dict, db: Session = Depends(get_db),
                         user: AuthUser = Depends(require_role("cash_shift", edit=True))):
    """Smena yopish — haqiqiy naqd kiritiladi, farq hisoblanadi"""
    try:
        shift = crud.close_cash_shift(db, shift_id,
                                      actual_cash=float(data.get("actual_cash", 0)),
                                      note=data.get("note"))
        return {"shift": crud.cash_shift_to_dict(shift)}
    except ValueError as e:
        raise HTTPException(400, str(e))


# =============== QAYTARISH AKTI (RETURN) ===============
@router.get("/returns/candidates")
def api_return_candidates(db: Session = Depends(get_db),
                          limit: int = 20,
                          user: AuthUser = Depends(require_any_view(["sales", "finance", "crm"]))):
    """Qaytarishga yaroqli (7 kun ichidagi, qoldig'i bor) sotuvlar ro'yxati"""
    try:
        sales = db.query(models.Sale).order_by(
            models.Sale.sale_date.desc()
        ).limit(max(limit, 1)).all()
        result = []
        for s in sales:
            remaining = (s.quantity or 0) - (s.returned_qty or 0)
            if remaining <= 0:
                continue
            elig = crud.check_return_eligibility(db, s.id, None)
            product = db.query(models.Product).filter(models.Product.id == s.product_id).first()
            result.append({
                "id": s.id,
                "invoice_number": s.invoice_number,
                "product_id": s.product_id,
                "product_name": product.name if product else "Noma'lum",
                "unit": product.unit if product else "",
                "quantity": s.quantity,
                "remaining": remaining,
                "unit_price": s.unit_price,
                "total_amount": s.total_amount,
                "customer_id": s.customer_id,
                "customer_name": s.customer_name,
                "sale_date": s.sale_date.isoformat() if s.sale_date else None,
                "eligible": elig["allowed"],
                "eligibility_reason": None if elig["allowed"] else elig["reason"],
            })
        return {"candidates": result}
    except Exception as e:
        return {"error": str(e), "candidates": []}


@router.get("/returns")
def api_returns(db: Session = Depends(get_db), limit: int = 50,
                sale_id: Optional[int] = None, customer_id: Optional[int] = None,
                user: AuthUser = Depends(require_any_view(["sales", "finance", "crm"]))):
    """Qaytarish aktlari ro'yxati"""
    try:
        acts = crud.list_return_acts(db, limit=limit, sale_id=sale_id, customer_id=customer_id)
        return {"returns": [crud.return_act_to_dict(a) for a in acts]}
    except Exception as e:
        return {"error": str(e), "returns": []}


@router.get("/returns/{return_id}")
def api_return_detail(return_id: int, db: Session = Depends(get_db),
                      user: AuthUser = Depends(require_any_view(["sales", "finance", "crm"]))):
    """Bitta qaytarish akti tafsilotlari"""
    act = crud.get_return_act(db, return_id)
    if not act:
        raise HTTPException(404, "Qaytarish akti topilmadi")
    return {"return_act": crud.return_act_to_dict(act)}


@router.post("/returns")
def api_create_return(data: dict, db: Session = Depends(get_db),
                      user: AuthUser = Depends(require_any_edit(["sales", "crm"]))):
    """Yangi qaytarish akti yaratish (pul qaytarish / almashtirish / bonus)"""
    try:
        act = crud.create_return_act(
            db,
            sale_id=int(data.get("sale_id", 0)),
            quantity=float(data.get("quantity", 0)),
            reason=str(data.get("reason", "mijoz_istagi")),
            refund_type=str(data.get("refund_type", "cash")),
            exchange_product_id=int(data["exchange_product_id"]) if data.get("exchange_product_id") else None,
            exchange_quantity=float(data["exchange_quantity"]) if data.get("exchange_quantity") else None,
            refund_method=str(data.get("refund_method")) if data.get("refund_method") else None,
            note=data.get("note"),
            user_id=user.telegram_id or user.id,
            user_name=user.full_name,
        )
        return {"return_act": crud.return_act_to_dict(act)}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        return {"error": str(e)}


# =============== YETKAZIB BERISH (DELIVERY + GPS) ===============
@router.get("/deliveries")
def api_deliveries(db: Session = Depends(get_db), status: Optional[str] = None,
                   driver_id: Optional[int] = None, limit: int = 50,
                   user: AuthUser = Depends(require_any_view(["delivery", "sales", "crm"]))):
    """Yetkazish topshiriqlari ro'yxati"""
    try:
        items = crud.list_deliveries(db, driver_id=driver_id, status=status, limit=limit)
        return {"deliveries": [crud_v54.delivery_with_vehicle_dict(db, d) for d in items]}
    except Exception as e:
        return {"error": str(e), "deliveries": []}


@router.get("/deliveries/deliverable-sales")
def api_deliverable_sales(db: Session = Depends(get_db), limit: int = 20,
                          user: AuthUser = Depends(require_any_view(["delivery", "sales"]))):
    """Yetkazish topshirig'i yaratish mumkin bo'lgan sotuvlar"""
    try:
        sales = crud.list_deliverable_sales(db, limit=limit)
        result = []
        for s in sales:
            product = db.query(models.Product).filter(models.Product.id == s.product_id).first()
            result.append({
                "id": s.id,
                "invoice_number": s.invoice_number,
                "product_name": product.name if product else "Noma'lum",
                "unit": product.unit if product else "",
                "remaining": crud.get_sale_delivery_remaining(db, s),
                "customer_name": s.customer_name,
                "customer_phone": s.customer_phone,
                "sale_date": s.sale_date.isoformat() if s.sale_date else None,
            })
        return {"sales": result}
    except Exception as e:
        return {"error": str(e), "sales": []}


@router.get("/deliveries/{delivery_id}")
def api_delivery_detail(delivery_id: int, db: Session = Depends(get_db),
                        user: AuthUser = Depends(require_any_view(["delivery", "sales", "crm"]))):
    """Bitta yetkazish tafsilotlari + GPS nuqtalari"""
    d = crud.get_delivery(db, delivery_id)
    if not d:
        raise HTTPException(404, "Yetkazish topilmadi")
    points = crud.list_delivery_locations(db, delivery_id)
    return {
        "delivery": crud_v54.delivery_with_vehicle_dict(db, d),
        "tracking": [{
            "latitude": p.latitude, "longitude": p.longitude,
            "accuracy": p.accuracy, "source": p.source,
            "recorded_at": p.recorded_at.isoformat() if p.recorded_at else None,
        } for p in points],
    }


@router.post("/deliveries")
def api_create_delivery(data: dict, db: Session = Depends(get_db),
                        user: AuthUser = Depends(require_any_edit(["delivery", "sales"]))):
    """Yangi yetkazish topshirig'i yaratish (haydovchiga biriktirish)"""
    try:
        vehicle_id = int(data["vehicle_id"]) if data.get("vehicle_id") else None
        d = crud_v54.create_delivery_with_vehicle(
            db,
            sale_id=int(data.get("sale_id", 0)),
            driver_id=int(data.get("driver_id", 0)),
            quantity=float(data["quantity"]) if data.get("quantity") else None,
            address=data.get("address"),
            note=data.get("note"),
            created_by=user.full_name,
            vehicle_id=vehicle_id,
        )
        return {"delivery": crud_v54.delivery_with_vehicle_dict(db, d)}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        return {"error": str(e)}


@router.post("/deliveries/{delivery_id}/start")
def api_start_delivery(delivery_id: int, db: Session = Depends(get_db),
                       user: AuthUser = Depends(require_any_edit(["delivery", "sales"]))):
    """Yetkazishni boshlash (yo'lda)"""
    try:
        d = crud.start_delivery(db, delivery_id)
        return {"delivery": crud.delivery_to_dict(d)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/deliveries/{delivery_id}/location")
def api_record_delivery_location(delivery_id: int, data: dict, db: Session = Depends(get_db),
                                 user: AuthUser = Depends(require_any_edit(["delivery", "sales"]))):
    """GPS nuqtasini qayd qilish (haydovchi joylashuvi)"""
    try:
        p = crud.record_delivery_location(
            db, delivery_id,
            latitude=float(data.get("latitude", 0)),
            longitude=float(data.get("longitude", 0)),
            accuracy=float(data["accuracy"]) if data.get("accuracy") else None,
            source="api",
        )
        return {"ok": True, "point": {
            "id": p.id, "latitude": p.latitude, "longitude": p.longitude,
            "accuracy": p.accuracy, "recorded_at": p.recorded_at.isoformat() if p.recorded_at else None,
        }}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/deliveries/{delivery_id}/complete")
def api_complete_delivery(delivery_id: int, db: Session = Depends(get_db),
                          data: dict = None,
                          user: AuthUser = Depends(require_any_edit(["delivery", "sales"]))):
    """Yetkazib berishni yakunlash"""
    try:
        note = (data or {}).get("note")
        d = crud.complete_delivery(db, delivery_id, note=note)
        return {"delivery": crud.delivery_to_dict(d)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/deliveries/{delivery_id}/cancel")
def api_cancel_delivery(delivery_id: int, db: Session = Depends(get_db),
                        data: dict = None,
                        user: AuthUser = Depends(require_any_edit(["delivery", "sales"]))):
    """Yetkazishni bekor qilish"""
    try:
        note = (data or {}).get("note")
        d = crud.cancel_delivery(db, delivery_id, note=note)
        return {"delivery": crud.delivery_to_dict(d)}
    except ValueError as e:
        raise HTTPException(400, str(e))


# =============== ISHLAB CHIQARISH SIFAT NAZORATI (QC) ===============
@router.get("/production/quality")
def api_production_qc_list(db: Session = Depends(get_db),
                           user: AuthUser = Depends(require_role("production"))):
    """QC kutilayotgan buyurtmalar + sifat nazorati aktlari"""
    try:
        pending = crud.list_production_orders_pending_qc(db, limit=50)
        pending_data = []
        for o in pending:
            product = db.query(models.Product).filter(
                models.Product.id == o.product_id
            ).first()
            pending_data.append({
                "id": o.id,
                "order_number": o.order_number,
                "product_id": o.product_id,
                "product_name": product.name if product else None,
                "unit": product.unit if product else None,
                "quantity": o.quantity,
                "actual_end": o.actual_end.isoformat() if o.actual_end else None,
            })
        acts = crud.list_production_qc_acts(db, limit=50)
        return {
            "pending": pending_data,
            "acts": [crud.production_qc_to_dict(db, qc) for qc in acts],
        }
    except Exception as e:
        raise HTTPException(400, str(e))


@router.post("/production/{order_id}/quality")
def api_create_production_qc(order_id: int, data: dict,
                             db: Session = Depends(get_db),
                             user: AuthUser = Depends(require_role("production", edit=True))):
    """Tayyor mahsulotga sifat nazorati akti yozish (raqamli dalolatnoma)

    body: {"quality_status": "qabul_qilingan|qisman|rad_etilgan",
           "rejected_qty": 12,          # qisman uchun zarur
           "notes": "...", "photo_path": "..."}
    """
    try:
        qc = crud.create_production_qc(
            db,
            order_id=order_id,
            quality_status=(data or {}).get("quality_status", "qabul_qilingan"),
            rejected_qty=(data or {}).get("rejected_qty"),
            notes=(data or {}).get("notes"),
            photo_path=(data or {}).get("photo_path"),
            created_by=(data or {}).get("created_by") or user.full_name,
            user_id=user.id,
        )
        return {"qc": crud.production_qc_to_dict(db, qc)}
    except ValueError as e:
        raise HTTPException(400, str(e))


# =============== DATABASE BACKUP / RESTORE (admin) ===============
def _backup_settings_dict() -> dict:
    """Web UI'ga ko'rsatish uchun backup sozlamalari (maxfiy kalitlarsiz)"""
    try:
        from config import (BACKUP_SETTINGS, BACKUP_UPLOAD_SETTINGS,
                            BACKUP_ENCRYPTION_PASSWORD, BACKUP_DIR)
        from utils.backup import _upload_targets, _s3_config
        targets = _upload_targets()
        cfg = _s3_config()
        return {
            "enabled": bool(BACKUP_SETTINGS.get("enabled", True)),
            "schedule": BACKUP_SETTINGS.get("schedule", "daily"),
            "time": BACKUP_SETTINGS.get("time", "02:00"),
            "keep_days": BACKUP_SETTINGS.get("keep_days", 30),
            "remote_keep_days": int(BACKUP_UPLOAD_SETTINGS.get("remote_keep_days", 0) or 0),
            "remote_upload": str(BACKUP_UPLOAD_SETTINGS.get("remote", "none")),
            "upload_targets": targets,
            "s3_bucket": cfg["s3_bucket"] if cfg else None,
            "remote_upload_active": bool(targets),
            "encryption_enabled": bool((BACKUP_ENCRYPTION_PASSWORD or "").strip()),
            "backup_dir": str(BACKUP_DIR),
        }
    except Exception:
        return {}


@router.get("/backups")
def api_backup_list(db: Session = Depends(get_db),
                    limit: int = 100,
                    user: AuthUser = Depends(require_role("admin"))):
    """Backup tarixi — fayllar, hajmlar, sana + yuklash holatlari (faqat direktor/admin)"""
    try:
        from utils.backup import list_backup_files, list_backup_run_logs
        files = list_backup_files(limit=max(min(limit, 500), 1))
        total_bytes = sum(f["size_bytes"] for f in files)
        return {
            "backups": files,
            "count": len(files),
            "total_size_mb": round(total_bytes / (1024 * 1024), 2),
            "upload_logs": list_backup_run_logs(db, limit=50),
            "settings": _backup_settings_dict(),
        }
    except Exception as e:
        return {"error": str(e), "backups": [], "count": 0,
                "total_size_mb": 0, "upload_logs": [], "settings": {}}


@router.post("/backups")
async def api_backup_create(db: Session = Depends(get_db),
                            user: AuthUser = Depends(require_role("admin", edit=True))):
    """Qo'lda backup olish (web paneldan) — konsistent nusxa + uzoq joyga yuklash

    Uzoq joyga yuklash yoqilgan bo'lsa (telegram/s3) fayl yuboriladi, eski uzoq
    nusxalar tozalanadi (BACKUP_REMOTE_KEEP_DAYS) va natija SystemLog'ga
    struktur (JSON) holatda yoziladi — web sahifa ko'rsatadi.
    """
    try:
        from utils.backup import (take_database_backup, prune_old_backups,
                                  prune_remote_backups, upload_backup_to_remote,
                                  backup_run_details_json, build_backup_log_action,
                                  _upload_targets)
        created = take_database_backup()
        if not created:
            raise HTTPException(500, "Backup olinmadi — loglarga qarang")
        pruned = prune_old_backups()

        # Faylni barcha yoqilgan manzillarga yuborish (telegram/s3)
        uploaded: dict = {}
        upload_errors: dict = {}
        encrypted = False
        try:
            up = await upload_backup_to_remote(str(created))
            uploaded = up.get("targets", {})
            upload_errors = up.get("errors", {})
            encrypted = bool(up.get("encrypted"))
        except Exception as e:
            upload_errors = {t: str(e) for t in (uploaded or {})}

        remote_pruned = await prune_remote_backups()
        try:
            targets_configured = bool(_upload_targets())
            log_action = build_backup_log_action(
                created=str(created), pruned=pruned,
                uploaded=uploaded, targets_configured=targets_configured,
                remote_pruned=remote_pruned, encrypted=encrypted)
            details = backup_run_details_json(
                filename=created.name, created=True, pruned=pruned,
                remote_pruned=remote_pruned, encrypted=encrypted,
                uploaded=uploaded, upload_errors=upload_errors,
                targets_configured=targets_configured,
                source="web", error=None)
            crud.create_system_log(
                db, user_id=user.telegram_id or user.id, user_name=user.full_name,
                action=f"Web paneldan backup olindi: {created.name} — "
                       f"{log_action.split(' -> ', 1)[-1] if ' -> ' in log_action else log_action}",
                module="backup",
                details=details,
            )
        except Exception:
            pass
        return {"success": True, "filename": created.name,
                "size_mb": round(created.stat().st_size / (1024 * 1024), 2),
                "pruned": pruned,
                "uploads": uploaded,
                "upload_errors": upload_errors,
                "encrypted": encrypted,
                "remote_pruned": remote_pruned}
    except HTTPException:
        raise
    except Exception as e:
        return {"error": str(e)}


@router.post("/backups/restore")
def api_backup_restore(data: dict = None, db: Session = Depends(get_db),
                       user: AuthUser = Depends(require_role("admin", edit=True))):
    """Backup'dan databaseni tiklash (faqat direktor) — xavfsizlik nusxasi avtomatik

    body: {"filename": "backup_20260101_020000.db"}
    Tiklash atomik (os.replace): joriy ochiq ulanishlar eski faylni ko'rishda
davom etadi, keyingi so'rovlar tiklangan faylni o'qiydi. Engine dispose qilinadi.
    """
    filename = str((data or {}).get("filename", "")).strip()
    if not filename:
        raise HTTPException(400, "filename ko'rsatilishi shart")
    try:
        from utils.backup import restore_database
        result = restore_database(filename)
        if not result.get("success"):
            raise HTTPException(400, result.get("error", "Tiklash bajarilmadi"))
        try:
            crud.create_system_log(
                db, user_id=user.telegram_id or user.id, user_name=user.full_name,
                action=f"Web paneldan database tiklandi: {filename}",
                module="backup",
            )
        except Exception:
            pass
        safety = result.get("safety_backup")
        return {"success": True, "filename": filename,
                "safety_backup": safety.split("/")[-1].split("\\")[-1] if safety else None}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, str(e))


@router.get("/backups/s3")
def api_backup_s3_list(db: Session = Depends(get_db),
                       user: AuthUser = Depends(require_role("admin"))):
    """S3 bucket'dagi backup ob'ektlari ro'yxati (bulutdan tiklash uchun)"""
    try:
        from utils.backup import _s3_config, list_s3_remote_backups
        return {
            "enabled": bool(_s3_config()),
            "objects": list_s3_remote_backups(limit=100),
        }
    except Exception as e:
        return {"enabled": False, "objects": [], "error": str(e)}


@router.post("/backups/restore/s3")
def api_backup_restore_s3(data: dict = None, db: Session = Depends(get_db),
                          user: AuthUser = Depends(require_role("admin", edit=True))):
    """S3 bucket'dagi backup'dan tiklash — yuklab olib, databaseni almashtirish

    body: {"key": "backups/2026/09/backup_20260904_020000.db[.enc]"}
    Shifrlangan nusxa uchun BACKUP_ENCRYPTION_PASSWORD kerak.
    """
    key = str((data or {}).get("key", "")).strip()
    if not key:
        raise HTTPException(400, "key ko'rsatilishi shart")
    try:
        from utils.backup import restore_database_from_s3
        result = restore_database_from_s3(key)
        if not result.get("success"):
            raise HTTPException(400, result.get("error", "S3'dan tiklash bajarilmadi"))
        encrypted = bool(result.get("encrypted"))
        action = (f"Web paneldan S3'dan database tiklandi: "
                  f"{key} (shifrlangan)" if encrypted else
                  f"Web paneldan S3'dan database tiklandi: {key}")
        try:
            crud.create_system_log(
                db, user_id=user.telegram_id or user.id, user_name=user.full_name,
                action=action, module="backup",
            )
        except Exception:
            pass
        safety = result.get("safety_backup")
        return {"success": True, "key": key,
                "filename": key.split("/")[-1],
                "encrypted": encrypted,
                "safety_backup": safety.split("/")[-1].split("\\")[-1] if safety else None}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, str(e))


# =============== YOQILG'I NAZORATI (TZ: D-bo'lim) ===============
@router.get("/fuel/logs")
def api_fuel_logs(db: Session = Depends(get_db), limit: int = 100,
                  user: AuthUser = Depends(require_any_view(["fuel", "delivery"]))):
    logs = crud.list_fuel_logs(db, limit=limit)
    return [{
        "id": l.id, "driver_id": l.driver_id, "driver_name": l.driver_name,
        "vehicle": l.vehicle, "odometer_km": l.odometer_km,
        "prev_odometer_km": l.prev_odometer_km, "liters": l.liters,
        "price_per_liter": l.price_per_liter, "total_cost": l.total_cost,
        "note": l.note, "created_by": l.created_by,
        "created_at": l.created_at.isoformat() if l.created_at else None,
    } for l in logs]


@router.post("/fuel/logs")
def api_create_fuel_log(data: dict, db: Session = Depends(get_db),
                        user: AuthUser = Depends(require_any_edit(["fuel", "delivery"]))):
    liters = float(data.get("liters", 0))
    if liters <= 0:
        raise HTTPException(400, "Litrlar soni noto'g'ri")
    entry = crud.create_fuel_log(db, {
        "driver_id": data.get("driver_id"),
        "driver_name": str(data.get("driver_name", user.full_name or "")).strip() or None,
        "vehicle": str(data.get("vehicle", "")).strip() or None,
        "odometer_km": float(data["odometer_km"]) if data.get("odometer_km") else None,
        "liters": liters,
        "price_per_liter": float(data["price_per_liter"]) if data.get("price_per_liter") else None,
        "note": str(data.get("note", "")).strip() or None,
        "created_by": user.full_name or user.username or "",
    })
    return {"success": True, "id": entry.id, "total_cost": entry.total_cost}


@router.get("/fuel/efficiency")
def api_fuel_efficiency(driver_id: Optional[int] = Query(None), days: int = 30,
                        db: Session = Depends(get_db),
                        user: AuthUser = Depends(require_any_view(["fuel", "delivery"]))):
    return crud.get_fuel_efficiency(db, driver_id=driver_id, days=days)


# =============== AVANS HISOBOti / XARAJAT (TZ: Avans) ===============
@router.get("/expenses")
def api_expenses(status: Optional[str] = None, limit: int = 100,
                 db: Session = Depends(get_db),
                 user: AuthUser = Depends(require_any_view(["expenses", "finance"]))):
    reports = crud.list_expense_reports(db, status=status, limit=limit)
    return [{
        "id": r.id, "report_number": r.report_number, "employee_id": r.employee_id,
        "employee_name": r.employee_name, "category": r.category, "amount": r.amount,
        "description": r.description, "status": r.status, "reviewed_by": r.reviewed_by,
        "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        "note": r.note, "created_by": r.created_by,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in reports]


@router.get("/expenses/totals")
def api_expense_totals(days: int = 30, db: Session = Depends(get_db),
                       user: AuthUser = Depends(require_any_view(["expenses", "finance"]))):
    return crud.get_expense_totals(db, days=days)


@router.post("/expenses")
def api_create_expense(data: dict, db: Session = Depends(get_db),
                       user: AuthUser = Depends(require_any_edit(["expenses", "finance"]))):
    amount = float(data.get("amount", 0))
    if amount <= 0:
        raise HTTPException(400, "Summa noto'g'ri")
    report = crud.create_expense_report(db, {
        "employee_id": data.get("employee_id"),
        "employee_name": str(data.get("employee_name", "")).strip() or user.full_name or None,
        "category": str(data.get("category", "boshqa")).strip(),
        "amount": amount,
        "description": str(data.get("description", "")).strip() or None,
        "created_by": user.full_name or user.username or "",
    })
    return {"success": True, "id": report.id, "report_number": report.report_number}


@router.post("/expenses/{report_id}/review")
def api_review_expense(report_id: int, data: dict, db: Session = Depends(get_db),
                       user: AuthUser = Depends(require_role("finance", edit=True))):
    status = str(data.get("status", "")).strip()
    if status not in ("tasdiqlangan", "rad_etilgan"):
        raise HTTPException(400, "status: tasdiqlangan yoki rad_etilgan bo'lishi kerak")
    report = crud.review_expense_report(
        db, report_id, status,
        reviewed_by=user.full_name or user.username, note=str(data.get("note", "")).strip() or None,
    )
    if not report:
        raise HTTPException(404, "Avans hisoboti topilmadi")
    return {"success": True, "status": report.status}


# =============== YIG'ISH VARAQASI (Picking list, TZ: 4-modul) ===============
@router.get("/picking")
def api_picking(status: Optional[str] = None, limit: int = 100,
                db: Session = Depends(get_db),
                user: AuthUser = Depends(require_any_view(["picking", "warehouse"]))):
    items = crud.list_picking_lists(db, status=status, limit=limit)
    return [{
        "id": p.id, "picking_number": p.picking_number, "sale_id": p.sale_id,
        "shop_order_id": p.shop_order_id, "product_id": p.product_id,
        "product_name": p.product_name, "unit": p.unit, "quantity": p.quantity,
        "sector": p.sector, "status": p.status, "picked_by": p.picked_by,
        "picked_at": p.picked_at.isoformat() if p.picked_at else None,
        "created_by": p.created_by,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    } for p in items]


@router.post("/picking")
def api_create_picking(data: dict, db: Session = Depends(get_db),
                       user: AuthUser = Depends(require_any_edit(["picking", "warehouse"]))):
    qty = float(data.get("quantity", 0))
    if qty <= 0:
        raise HTTPException(400, "Miqdor noto'g'ri")
    product = db.query(models.Product).filter(models.Product.id == data.get("product_id")).first()
    item = crud.create_picking_list(db, {
        "sale_id": data.get("sale_id"),
        "shop_order_id": data.get("shop_order_id"),
        "product_id": data.get("product_id"),
        "product_name": product.name if product else str(data.get("product_name", "")).strip() or None,
        "unit": product.unit if product else str(data.get("unit", "")).strip() or None,
        "quantity": qty,
        "sector": product.sector if hasattr(product, "sector") and product.sector else str(data.get("sector", "")).strip() or None,
        "created_by": user.full_name or user.username or "",
    })
    return {"success": True, "id": item.id, "picking_number": item.picking_number}


@router.post("/picking/{picking_id}/status")
def api_update_picking(picking_id: int, data: dict, db: Session = Depends(get_db),
                       user: AuthUser = Depends(require_any_edit(["picking", "warehouse"]))):
    status = str(data.get("status", "")).strip()
    if status not in ("yangi", "tayyor", "yuborilgan"):
        raise HTTPException(400, "status: yangi, tayyor yoki yuborilgan bo'lishi kerak")
    item = crud.update_picking_status(
        db, picking_id, status, picked_by=user.full_name or user.username,
    )
    if not item:
        raise HTTPException(404, "Yig'ish varaqasi topilmadi")
    return {"success": True, "status": item.status}


# =============== SOTUVCHILAR REYTINGI (TZ: "Sotuvchi reytingi") ===============
@router.get("/sellers/ratings")
def api_seller_ratings(days: int = 30, limit: int = 20,
                       db: Session = Depends(get_db),
                       user: AuthUser = Depends(require_any_view(["ratings", "reports"]))):
    return crud.get_seller_ratings(db, days=days, limit=limit)


# =============== SHUBHALI HARAKAT DETEKTORI (TZ: Xavfsizlik) ===============
@router.get("/security/alerts")
def api_security_alerts(status: Optional[str] = None, limit: int = 100,
                        db: Session = Depends(get_db),
                        user: AuthUser = Depends(require_any_view(["security", "admin"]))):
    acts = crud.list_suspicious_activities(db, status=status, limit=limit)
    return [{
        "id": a.id, "activity_type": a.activity_type, "severity": a.severity,
        "description": a.description, "user_name": a.user_name, "user_id": a.user_id,
        "entity_id": a.entity_id, "status": a.status,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    } for a in acts]


@router.post("/security/alerts/{act_id}/status")
def api_update_security_alert(act_id: int, data: dict, db: Session = Depends(get_db),
                              user: AuthUser = Depends(require_any_edit(["security", "admin"]))):
    status = str(data.get("status", "")).strip()
    if status not in ("yangi", "ko'rib_chiqilgan", "hal_qilingan"):
        raise HTTPException(400, "status: yangi, ko'rib_chiqilgan yoki hal_qilingan bo'lishi kerak")
    act = crud.update_suspicious_status(db, act_id, status)
    if not act:
        raise HTTPException(404, "Ogohlantirish topilmadi")
    return {"success": True, "status": act.status}
