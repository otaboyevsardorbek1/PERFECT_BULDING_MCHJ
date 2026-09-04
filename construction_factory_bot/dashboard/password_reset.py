"""
Web dashboard parol tiklash (self-service flow)

Xodim o'z parolini unutganda:
  1) So'rov beradi (telefon + sabab) — POST /api/password-reset/request
  2) Admin so'rovni ko'rib chiqadi — POST /api/password-reset/{id}/approve
     (tasdiqlangach bir martalik kod hosil bo'ladi, kod adminda ko'rinadi)
  3) Xodim kodni admin'dan olib, yangi parol o'rnatadi — POST /api/password-reset/complete

Xavfsizlik:
  - Kod bir martalik, cheklangan muddatga (RESET_CODE_TTL_HOURS, default 2 soat)
  - Kod ochiq saqlanmaydi — sha256 xeshi saqlanadi
  - Parol o'rnatilgach barcha web sessiyalar revoke qilinadi
"""
from datetime import datetime, timedelta
import hashlib
import os
import secrets

from sqlalchemy.orm import Session

from dashboard.auth import find_employee_by_phone, normalize_phone_digits, set_employee_password


RESET_CODE_TTL_HOURS = int(os.getenv("RESET_CODE_TTL_HOURS", "2"))
RESET_CODE_LENGTH = 10
PASSWORD_MIN_LENGTH = int(os.getenv("WEB_PASSWORD_MIN_LENGTH", "8"))


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def generate_reset_code() -> str:
    """O'qish oson, katta-kichik harf va raqamdan iborat kod"""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 0/O, 1/I kabi chalkashlarsiz
    return "".join(secrets.choice(alphabet) for _ in range(RESET_CODE_LENGTH))


def request_password_reset(db: Session, phone_number: str, reason: str = None) -> dict:
    """Xodim uchun parol tiklash so'rovini yaratadi.

    Xavfsizlik: telefon ro'yxatda bo'lmasa ham bir xil javob qaytadi
    (raqam bor/yo'qligi oshkor bo'lmaydi).
    """
    from database import models
    phone = (phone_number or "").strip()
    if not phone:
        return {"success": False, "error": "Telefon raqamini kiriting"}

    employee = find_employee_by_phone(db, phone)

    if employee is None:
        return {"success": True, "message": "So'rov qabul qilindi. Direktor tasdiqlagach, yangi parol o'rnatishingiz mumkin."}

    # Faol so'rov bo'lmasa yangisini yaratamiz (spamdan himoya)
    active = db.query(models.PasswordResetRequest).filter(
        models.PasswordResetRequest.employee_id == employee.id,
        models.PasswordResetRequest.status.in_(["pending", "approved"]),
    ).first()
    if active is not None:
        return {"success": True, "message": "So'rov qabul qilindi. Direktor tasdiqlagach, yangi parol o'rnatishingiz mumkin."}

    req = models.PasswordResetRequest(
        employee_id=employee.id,
        phone_number=phone,
        reason=(reason or "").strip()[:500] or None,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return {
        "success": True,
        "request_id": req.id,
        "message": "So'rov qabul qilindi. Direktor tasdiqlagach, yangi parol o'rnatishingiz mumkin.",
    }


def list_password_resets(db: Session, include_done: bool = False) -> list:
    """Barcha so'rovlarni (admin paneli uchun), eng yangilari tepada"""
    from database import models
    query = db.query(models.PasswordResetRequest)
    if not include_done:
        query = query.filter(models.PasswordResetRequest.status != "done")
    rows = query.order_by(models.PasswordResetRequest.requested_at.desc()).limit(100).all()
    result = []
    for r in rows:
        emp = r.employee
        result.append({
            "id": r.id,
            "employee_id": r.employee_id,
            "full_name": emp.full_name if emp else "?",
            "role": emp.role if emp else "ishchi",
            "phone_number": r.phone_number,
            "reason": r.reason,
            "status": r.status,
            "requested_at": r.requested_at.isoformat() if r.requested_at else None,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            "code_expires_at": r.code_expires_at.isoformat() if r.code_expires_at else None,
            "has_code": bool(r.reset_hash),
        })
    return result


def _mark_reviewed(db: Session, reset_id: int, reviewer_id: int) -> None:
    from database import models
    req = db.query(models.PasswordResetRequest).filter(
        models.PasswordResetRequest.id == reset_id
    ).first()
    if req is None:
        return
    req.reviewed_at = datetime.utcnow()
    req.reviewed_by = reviewer_id


def approve_password_reset(db: Session, reset_id: int, reviewer_id: int) -> dict:
    """So'rovni tasdiqlaydi va bir martalik kod beradi (faqat admin ko'radi)."""
    from database import models
    req = db.query(models.PasswordResetRequest).filter(
        models.PasswordResetRequest.id == reset_id
    ).first()
    if req is None:
        return {"success": False, "error": "So'rov topilmadi"}
    if req.status == "rejected":
        return {"success": False, "error": "So'rov avval rad etilgan"}
    if req.status == "done":
        return {"success": False, "error": "So'rov allaqachon bajarilgan"}

    code = generate_reset_code()
    req.reset_hash = _hash_code(code)
    req.code_expires_at = datetime.utcnow() + timedelta(hours=RESET_CODE_TTL_HOURS)
    req.status = "approved"
    _mark_reviewed(db, reset_id, reviewer_id)
    db.commit()
    return {
        "success": True,
        "reset_code": code,
        "expires_in_hours": RESET_CODE_TTL_HOURS,
        "employee_name": req.employee.full_name if req.employee else "?",
    }


def reject_password_reset(db: Session, reset_id: int, reviewer_id: int) -> dict:
    """So'rovni rad etadi (yangi so'rov berish mumkin bo'lib qoladi)."""
    from database import models
    req = db.query(models.PasswordResetRequest).filter(
        models.PasswordResetRequest.id == reset_id
    ).first()
    if req is None:
        return {"success": False, "error": "So'rov topilmadi"}
    if req.status == "done":
        return {"success": False, "error": "So'rov allaqachon bajarilgan"}
    req.status = "rejected"
    _mark_reviewed(db, reset_id, reviewer_id)
    db.commit()
    return {"success": True}


def complete_password_reset(db: Session, phone_number: str, code: str,
                            new_password: str) -> dict:
    """Kodni tekshirib, xodimga yangi parol o'rnatadi va sessiyalarni revoke qiladi."""
    from database import models
    from dashboard.auth import find_employee_by_phone, revoke_session
    phone = (phone_number or "").strip()
    code = (code or "").strip().upper()
    if not phone or not code:
        return {"success": False, "error": "Telefon va kodni kiriting"}
    if not new_password or len(new_password) < PASSWORD_MIN_LENGTH:
        return {"success": False, "error": f"Yangi parol kamida {PASSWORD_MIN_LENGTH} belgidan iborat bo'lishi kerak"}

    employee = find_employee_by_phone(db, phone)
    if employee is None:
        return {"success": False, "error": "Kod noto'g'ri yoki muddati o'tgan"}

    req = db.query(models.PasswordResetRequest).filter(
        models.PasswordResetRequest.employee_id == employee.id,
        models.PasswordResetRequest.status == "approved",
    ).order_by(models.PasswordResetRequest.code_expires_at.desc()).first()
    if req is None or not req.reset_hash:
        return {"success": False, "error": "Kod noto'g'ri yoki muddati o'tgan"}
    if not secrets.compare_digest(req.reset_hash, _hash_code(code)):
        return {"success": False, "error": "Kod noto'g'ri yoki muddati o'tgan"}
    if req.code_expires_at is None or req.code_expires_at < datetime.utcnow():
        return {"success": False, "error": "Kodning muddati o'tgan. Yangi so'rov bering."}

    # Yangi parolni o'rnatamiz
    try:
        set_employee_password(db, employee, new_password)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    req.status = "done"
    req.completed_at = datetime.utcnow()
    req.reset_hash = None  # kod bir marta ishlatiladi
    db.commit()

    # Xavfsizlik: barcha web sessiyalarini revoke qilamiz
    sessions = db.query(models.WebSession).filter(
        models.WebSession.employee_id == employee.id,
        models.WebSession.revoked_at.is_(None),
    ).all()
    for s in sessions:
        revoke_session(db, session_id=s.id)

    return {
        "success": True,
        "message": "Parol yangilandi. Endi yangi parol bilan kiring.",
    }
